#!/usr/bin/env python3
"""
GyroAim - PC agent.

Serves the phone client over HTTP and listens for control packets over
WebSocket, translating them into mouse movement, clicks and key presses.

    pip install websockets pynput mss pillow ultralytics opencv-python-headless
    python server.py

Then open the printed URL on your phone (same Wi-Fi network).
"""

import argparse
import asyncio
import functools
import http.server
import io
import json
import os
import re
import socket
import sys
import threading
import time

import base64

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("YOLO_CONFIG_DIR", os.path.join(HERE, ".yolo-config"))
os.environ.setdefault("MPLCONFIGDIR", os.path.join(HERE, ".matplotlib"))
os.makedirs(os.environ["YOLO_CONFIG_DIR"], exist_ok=True)
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import mss
import numpy as np
import websockets
from PIL import Image
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Button, Controller as MouseController

# Optional at import time so the controller still starts if detection
# dependencies have not been installed yet.
try:
    import cv2
except ImportError:
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

CLIENT_DIR = os.path.join(HERE, "client")

mouse = MouseController()
keyboard = KeyboardController()

# ---------------------------------------------------------------- tuning ----
# sens_* is pixels of mouse travel per degree of phone rotation.
# Everything here can be changed live from the phone's tuning screen.
CFG = {
    "sens_x": 14.0,
    "sens_y": 14.0,
    "ads_scale": 0.55,   # sensitivity multiplier while ADS is held
}
DEFAULT_TUNING = dict(CFG)

# ------------------------------------------------------------ HUD mirror ----
# A rectangle of the PC screen, mirrored onto the phone. Stored normalised
# 0..1 rather than in pixels: mss reports the true 3840x2160 panel while the
# Windows metrics API reports the 2560x1440 DPI-scaled desktop, and normalised
# coordinates mean the two never have to be reconciled.
# Each region carries both halves of the mapping: s* is the rectangle grabbed
# from the monitor, d* is where it is drawn on the phone. Both normalised.
MAX_REGIONS = 3
DEFAULT_REGION = {"sx": 0.72, "sy": 0.72, "sw": 0.26, "sh": 0.26,
                  "dx": 0.04, "dy": 0.04, "dw": 0.34, "dh": 0.22}
MAX_MACROS = 10
DEFAULT_ENEMY_TRACKING = {
    "enabled": False,
    "detector": "yolo",
    "yolo_model": "yolov8n.pt",
    "scan_hz": 2.0,
    "max_width": 320,
    "confidence": 0.15,
}
PROFILE = {"game": "", "on": False, "regions": [dict(DEFAULT_REGION)],
           "rules": [], "macros": [],
           "enemy_tracking": dict(DEFAULT_ENEMY_TRACKING)}

# --------------------------------------------------------------- macros ----
# A macro is a label plus a key sequence: "r" for reload, "3,r" to switch to
# the third slot and reload. Named keys are spelled out so a macro is not
# limited to things that fit in one character.
NAMED_KEYS = {
    "space": Key.space, "tab": Key.tab, "esc": Key.esc, "escape": Key.esc,
    "enter": Key.enter, "shift": Key.shift, "ctrl": Key.ctrl, "alt": Key.alt,
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "backspace": Key.backspace, "delete": Key.delete,
    **{f"f{n}": getattr(Key, f"f{n}") for n in range(1, 13)},
}


def resolve_key(token: str):
    token = token.strip().lower()
    if token in NAMED_KEYS:
        return NAMED_KEYS[token]
    return token[:1] or None


def send_keys(sequence: str) -> None:
    """Tap each key in a comma-separated sequence, in order."""
    for token in str(sequence).split(",")[:8]:
        key = resolve_key(token)
        if key is None or key == "":
            continue
        keyboard.press(key)
        keyboard.release(key)
        time.sleep(0.03)      # some games drop keys sent in the same frame

# ---------------------------------------------------------------- rules ----
# A rule is "watch this box, tell me when it looks like this picture again".
# Nothing in here knows anything about any particular game: the reference is
# captured from the user's own screen, so a new game needs no new code.
#
# Matching is zero-normalised cross-correlation on a resized luminance patch
# plus an edge patch. The edge channel matters for small HUD text: a readable
# "Reload now" can vanish if the whole box is blurred into 64 grayscale pixels.
PATCH = (128, 128)
# Provisional only. A fixed default cannot be right: a fresh capture scores 1.0
# against a frozen screen, but the same state re-occurring over live footage
# may only reach 0.6, because the scene behind the marked text has moved.
# calibrate_rule() replaces this with a measured value moments after creation.
DEFAULT_RULE_THRESH = 0.70
RULE_HZ = 4.0
_rule_patches = []                # normalised reference arrays, parallel to rules
_last_full = None                 # last frame served to /snapshot.jpg
_last_full_lock = threading.Lock()
CLIENTS = set()
LOOP = None


def normalise_channel(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32)
    a -= a.mean()
    sd = a.std()
    return a / sd if sd > 1e-6 else np.zeros_like(a)


def edge_channel(a: np.ndarray) -> np.ndarray:
    """Simple gradient magnitude, enough to preserve small HUD lettering."""
    gx = np.zeros_like(a, dtype=np.float32)
    gy = np.zeros_like(a, dtype=np.float32)
    gx[:, 1:] = a[:, 1:] - a[:, :-1]
    gy[1:, :] = a[1:, :] - a[:-1, :]
    return np.hypot(gx, gy)


def to_patch(img) -> np.ndarray:
    """Luminance and edge channels, mean-removed and variance-normalised.

    The normalisation is what makes the score brightness- and contrast-
    independent, so a HUD that fades in and out still matches itself. Keeping
    an edge channel makes small text compare by its letter strokes rather than
    by the average colour of the marked box.
    """
    gray = img.convert("L").resize(PATCH, Image.LANCZOS)
    a = np.asarray(gray, dtype=np.float32)
    return np.stack((normalise_channel(a), normalise_channel(edge_channel(a))))


def encode_patch(img) -> str:
    small = img.convert("L").resize(PATCH, Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def decode_patch(data: str) -> np.ndarray:
    raw = base64.b64decode(data)
    return to_patch(Image.open(io.BytesIO(raw)))


def rebuild_patches() -> None:
    _rule_patches.clear()
    for rule in PROFILE["rules"]:
        try:
            _rule_patches.append(decode_patch(rule["ref"]))
        except Exception:
            _rule_patches.append(np.zeros(PATCH, dtype=np.float32))
_profile_lock = threading.Lock()
_tls = threading.local()          # mss is not safe to share between threads


def _sct():
    if not hasattr(_tls, "sct"):
        _tls.sct = mss.mss()
    return _tls.sct


# ------------------------------------------------------------ profiles ----
# One file per game rather than one blob: export is then just handing over a
# file, and a bad write can only damage the game it belongs to.
PROFILES_DIR = os.path.join(HERE, "profiles")
ACTIVE_PATH = os.path.join(HERE, "active.txt")

# ------------------------------------------------------------- sessions ----
# The phone records a run and uploads it when you leave the controller. It
# lands here rather than staying on the handset because the report has to be
# served to a browser on the PC, and the PC can only serve what it holds.
SESSIONS_DIR = os.path.join(HERE, "sessions")


def session_path(sid: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{slugify(sid)}.json")


def list_sessions() -> list:
    out = []
    if os.path.isdir(SESSIONS_DIR):
        for name in os.listdir(SESSIONS_DIR):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(SESSIONS_DIR, name), encoding="utf-8") as fh:
                    s = json.load(fh)
            except (OSError, ValueError):
                continue
            out.append({
                "id": s.get("id", name[:-5]),
                "game": s.get("game", ""),
                "started": s.get("started", 0),
                "seconds": round(s.get("seconds", 0), 1),
                "samples": len(s.get("trace", [])),
                "shots": s.get("summary", {}).get("shots", 0),
            })
    out.sort(key=lambda s: s["started"], reverse=True)
    return out


def save_session(data: dict) -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    started = float(data.get("started") or time.time() * 1000)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(started / 1000))
    sid = f"{slugify(data.get('game') or 'session')}-{stamp}"
    data["id"] = sid
    with open(session_path(sid), "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    print(f"session saved: {sid}  ({round(data.get('seconds', 0))}s, "
          f"{len(data.get('trace', []))} samples)")
    return sid


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return (slug or "game")[:40]


def profile_path(pid: str) -> str:
    return os.path.join(PROFILES_DIR, f"{slugify(pid)}.json")


def cover_path(pid: str) -> str:
    return os.path.join(PROFILES_DIR, f"{slugify(pid)}.jpg")


def blank_profile(game: str = "") -> dict:
    return {
        "id": slugify(game) or "game",
        "game": game,
        "on": False,
        "regions": [],
        "rules": [],
        "macros": [],
        "enemy_tracking": dict(DEFAULT_ENEMY_TRACKING),
        # Sensitivity belongs to the game, not the app: 16 px/deg in one title
        # is nothing like 16 in another, and picking a profile should bring its
        # feel with it rather than leaving you to re-tune by hand.
        "tuning": dict(DEFAULT_TUNING),
    }


def list_profiles() -> list:
    out = []
    for name in sorted(os.listdir(PROFILES_DIR)) if os.path.isdir(PROFILES_DIR) else []:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(PROFILES_DIR, name), encoding="utf-8") as fh:
                p = json.load(fh)
        except (OSError, ValueError):
            continue
        out.append({
            "id": p.get("id", name[:-5]),
            "game": p.get("game", name[:-5]),
            "regions": len(p.get("regions", [])),
            "rules": len(p.get("rules", [])),
            "macros": sum(1 for m in p.get("macros", []) if m.get("keys")),
            "cover": os.path.exists(cover_path(p.get("id", name[:-5]))),
        })
    return out


def write_profile(profile: dict) -> None:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    try:
        with open(profile_path(profile["id"]), "w", encoding="utf-8") as fh:
            json.dump(profile, fh, indent=2)
    except OSError as exc:
        print("could not save profile:", exc)


def save_profile() -> None:
    """Persist the active profile, and remember which one it was."""
    write_profile(PROFILE)
    try:
        with open(ACTIVE_PATH, "w", encoding="utf-8") as fh:
            fh.write(PROFILE["id"])
    except OSError:
        pass


def import_bundle(bundle: dict) -> str:
    """Take an exported bundle and land it as a new profile."""
    profile = blank_profile(str(bundle.get("game", "Imported"))[:80])
    for key in ("on", "regions", "rules", "macros", "tuning",
                "enemy_tracking"):
        if key in bundle:
            profile[key] = bundle[key]
    base, n = profile["id"], 2
    while os.path.exists(profile_path(profile["id"])):
        profile["id"] = f"{base}-{n}"
        n += 1
    write_profile(profile)
    if bundle.get("cover_data"):
        try:
            with open(cover_path(profile["id"]), "wb") as fh:
                fh.write(base64.b64decode(bundle["cover_data"]))
        except (OSError, ValueError):
            pass
    print("imported profile:", profile["id"])
    return profile["id"]


def activate(pid: str) -> bool:
    try:
        with open(profile_path(pid), encoding="utf-8") as fh:
            loaded = json.load(fh)
    except (OSError, ValueError):
        return False
    with _profile_lock:
        PROFILE.clear()
        PROFILE.update(blank_profile())
        PROFILE.update(loaded)
        PROFILE.setdefault("tuning", dict(DEFAULT_TUNING))
        enemy = dict(DEFAULT_ENEMY_TRACKING)
        enemy.update(PROFILE.get("enemy_tracking") or {})
        PROFILE["enemy_tracking"] = enemy
        CFG.update({k: float(v) for k, v in PROFILE["tuning"].items() if k in CFG})
        rebuild_patches()
    save_profile()
    print(f"profile active: {PROFILE.get('game') or PROFILE['id']}")
    return True


def load_profile() -> None:
    """Load the last active profile, migrating the old single-file one in."""
    os.makedirs(PROFILES_DIR, exist_ok=True)

    legacy = os.path.join(HERE, "profile.json")
    if os.path.exists(legacy) and not list_profiles():
        try:
            with open(legacy, encoding="utf-8") as fh:
                old = json.load(fh)
            migrated = blank_profile(old.get("game") or "My game")
            migrated.update({k: old[k] for k in
                             ("on", "regions", "rules", "macros") if k in old})
            migrated["id"] = slugify(migrated["game"])
            write_profile(migrated)
            os.replace(legacy, legacy + ".bak")
            print(f"migrated profile.json -> profiles/{migrated['id']}.json")
        except (OSError, ValueError) as exc:
            print("could not migrate profile.json:", exc)

    wanted = None
    try:
        with open(ACTIVE_PATH, encoding="utf-8") as fh:
            wanted = fh.read().strip()
    except OSError:
        pass
    known = [p["id"] for p in list_profiles()]
    if wanted not in known:
        wanted = known[0] if known else None

    if wanted:
        activate(wanted)
    else:
        PROFILE.update(blank_profile("My game"))
        rebuild_patches()


def grab_region(box) -> Image.Image:
    """A normalised rectangle of the live screen, as a PIL image."""
    sct = _sct()
    mon = sct.monitors[1]
    shot = sct.grab({
        "left":   mon["left"] + int(box["sx"] * mon["width"]),
        "top":    mon["top"]  + int(box["sy"] * mon["height"]),
        "width":  max(8, int(box["sw"] * mon["width"])),
        "height": max(8, int(box["sh"] * mon["height"])),
    })
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def grab_jpeg(box=None, max_w=0, quality=70) -> bytes:
    """Capture the whole screen, or a normalised sub-rectangle of it."""
    sct = _sct()
    mon = sct.monitors[1]
    if box:
        region = {
            "left":   mon["left"] + int(box["sx"] * mon["width"]),
            "top":    mon["top"]  + int(box["sy"] * mon["height"]),
            "width":  max(8, int(box["sw"] * mon["width"])),
            "height": max(8, int(box["sh"] * mon["height"])),
        }
    else:
        region = mon

    shot = sct.grab(region)
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if max_w and img.width > max_w:
        img = img.resize((max_w, max(1, round(img.height * max_w / img.width))))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


KEYMAP = {
    "weapon_primary": "1",
    "weapon_secondary": "2",
    "move_fwd": "w",
    "move_back": "s",
    "move_left": "a",
    "move_right": "d",
    "reload": "r",
    "jump": Key.space,
    "crouch": "c",
    "melee": "v",
}

# ------------------------------------------------------------- movement ----
# Mouse deltas must be integers. Truncating every packet would silently throw
# away all slow, precise aim, so fractional pixels are carried over instead.
_acc_x = 0.0
_acc_y = 0.0
_ads_held = False
_held_buttons = set()


# pynput's mouse.move() is SetCursorPos underneath: it repositions the Windows
# pointer but emits no WM_INPUT event. Games that read mouse look through Raw
# Input - most FPS titles - therefore see no movement at all, even though the
# clicks land, because pynput sends those via SendInput. Feed relative motion
# through SendInput so the raw input path carries real deltas.
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _ULONG_PTR = (ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8
                  else ctypes.c_ulong)

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG),
                    ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", _ULONG_PTR)]

    class _INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", _MOUSEINPUT)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    _INPUT_MOUSE = 0
    _MOUSEEVENTF_MOVE = 0x0001

    # A private WinDLL handle, NOT ctypes.windll.user32. That one is cached
    # process-wide and its SendInput is the same function object pynput uses -
    # setting argtypes on it makes every pynput click and keypress fail with
    # "expected LP__INPUT instance instead of pointer to INPUT".
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _SendInput = _user32.SendInput
    _SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    _SendInput.restype = wintypes.UINT

    def _move_raw(ix: int, iy: int) -> None:
        evt = _INPUT(type=_INPUT_MOUSE)
        evt.mi = _MOUSEINPUT(ix, iy, 0, _MOUSEEVENTF_MOVE, 0, 0)
        _SendInput(1, ctypes.byref(evt), ctypes.sizeof(_INPUT))
else:
    def _move_raw(ix: int, iy: int) -> None:
        mouse.move(ix, iy)


def move(dx: float, dy: float) -> None:
    global _acc_x, _acc_y
    _acc_x += dx
    _acc_y += dy
    ix, iy = int(_acc_x), int(_acc_y)   # truncates toward zero - correct here
    _acc_x -= ix
    _acc_y -= iy
    if ix or iy:
        _move_raw(ix, iy)


def broadcast(payload: dict) -> None:
    """Push to every connected phone from a non-async thread."""
    if not LOOP or not CLIENTS:
        return
    text = json.dumps(payload)

    async def _send():
        for ws in list(CLIENTS):
            try:
                await ws.send(text)
            except Exception:
                CLIENTS.discard(ws)

    try:
        asyncio.run_coroutine_threadsafe(_send(), LOOP)
    except RuntimeError:
        pass


def calibrate_rule(index: int, seconds: float = 2.5) -> None:
    """Watch a rule for a moment and set its threshold from what it actually
    scores.

    A fixed default cannot work: a fresh capture scores 1.0 against a frozen
    screen, but against live footage the scene behind the marked text keeps
    moving and the same state re-occurring might only reach 0.6. The only
    honest number is a measured one, so this samples the real score while the
    state is on screen and sits the threshold just under it.
    """
    def work():
        best = -1.0
        deadline = time.time() + seconds
        while time.time() < deadline:
            with _profile_lock:
                if not (0 <= index < len(PROFILE["rules"])):
                    return
                box = dict(PROFILE["rules"][index]["box"])
                patch = _rule_patches[index] if index < len(_rule_patches) else None
            if patch is None:
                return
            try:
                best = max(best, float((to_patch(grab_region(box)) * patch).mean()))
            except Exception:
                pass
            time.sleep(0.12)

        # Below ~0.45 the state has almost certainly left the screen between
        # capturing and saving, so trust a conservative default over a
        # measurement of the wrong thing.
        trustworthy = best >= 0.45
        thresh = round(max(0.40, min(0.92, best * 0.88)), 2) if trustworthy else 0.65
        with _profile_lock:
            if 0 <= index < len(PROFILE["rules"]):
                PROFILE["rules"][index]["thresh"] = thresh
        save_profile()
        print(f"calibrated rule {index}: best {best:.3f} -> threshold {thresh}")
        broadcast({"t": "calibrated", "i": index, "best": round(best, 3),
                   "thresh": thresh, "trusted": trustworthy})

    threading.Thread(target=work, daemon=True).start()


def rule_loop() -> None:
    """Score every rule a few times a second and report changes.

    Each rule's box is grabbed separately rather than cropping one full-screen
    capture: a 4K full grab measures 71 ms against 6 ms for a small region, so
    per-rule grabs are cheaper for any realistic number of rules.
    """
    state = {}
    while True:
        started = time.perf_counter()
        with _profile_lock:
            rules = list(PROFILE["rules"])
            patches = list(_rule_patches)

        scores = []
        for i, rule in enumerate(rules):
            try:
                live = to_patch(grab_region(rule["box"]))
                score = float((live * patches[i]).mean()) if i < len(patches) else 0.0
            except Exception:
                score = 0.0
            scores.append(round(score, 3))

            # Two consecutive agreeing samples before flipping, so a muzzle
            # flash or a single dropped frame cannot trigger an alert.
            was, streak = state.get(i, (False, 0))
            hit = score >= rule.get("thresh", DEFAULT_RULE_THRESH)
            streak = streak + 1 if hit != was else 0
            if streak >= 2:
                was, streak = hit, 0
                broadcast({"t": "alert", "i": i, "name": rule.get("name", ""),
                           "msg": rule.get("msg", ""), "key": rule.get("key", ""),
                           "dwell": rule.get("dwell", 3.0), "on": was})
            state[i] = (was, streak)

        if scores:
            broadcast({"t": "scores", "v": scores})
        time.sleep(max(0.0, 1.0 / RULE_HZ - (time.perf_counter() - started)))


# ------------------------------------------------------ enemy tracking ----
_yolo_model = None
_yolo_model_name = None
_yolo_failed = False
_hog_detector = None
_enemy_backend = "none"


def resize_for_scan(frame: np.ndarray, max_w: int) -> np.ndarray:
    """Shrink a screen frame before detection to keep CPU cost predictable."""
    max_w = max(192, min(960, int(max_w)))
    if frame.shape[1] <= max_w:
        return frame
    scale = max_w / frame.shape[1]
    size = (max_w, max(128, round(frame.shape[0] * scale)))
    if cv2 is not None:
        return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    img = Image.fromarray(frame[:, :, ::-1])
    return np.asarray(img.resize(size, Image.BILINEAR))[:, :, ::-1]


def detector_available() -> bool:
    return (YOLO is not None and not _yolo_failed) or cv2 is not None


def load_hog_detector():
    global _hog_detector
    if cv2 is None:
        return None
    if _hog_detector is None:
        _hog_detector = cv2.HOGDescriptor()
        _hog_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return _hog_detector


def load_yolo_model(model_name: str):
    global _yolo_model, _yolo_model_name, _yolo_failed
    if YOLO is None or _yolo_failed:
        return None
    if _yolo_model is not None and _yolo_model_name == model_name:
        return _yolo_model
    try:
        print("enemy tracking: loading YOLO model", model_name)
        _yolo_model = YOLO(model_name)
        _yolo_model_name = model_name
        _yolo_failed = False
        return _yolo_model
    except Exception as exc:
        _yolo_failed = True
        print("enemy tracking: YOLO unavailable:", exc)
        return None


def detect_enemy(frame: np.ndarray, cfg: dict) -> tuple[bool, float, str]:
    """Return whether a character-like person was found, confidence, backend."""
    threshold = max(0.01, min(0.99, float(cfg["confidence"])))
    frame = resize_for_scan(frame, cfg["max_width"])

    if cfg.get("detector", "yolo") == "yolo":
        model = load_yolo_model(str(cfg.get("yolo_model") or "yolov8n.pt"))
        if model is not None:
            results = model.predict(frame, imgsz=max(256, min(960, int(cfg["max_width"]))),
                                    conf=threshold, classes=[0], verbose=False,
                                    device="cpu")
            best = 0.0
            for result in results:
                boxes = getattr(result, "boxes", None)
                if boxes is None or boxes.conf is None:
                    continue
                confs = boxes.conf.detach().cpu().numpy()
                if len(confs):
                    best = max(best, float(confs.max()))
            return best >= threshold, best, "yolo"

    detector = load_hog_detector()
    if detector is None:
        return False, 0.0, "none"

    _boxes, weights = detector.detectMultiScale(
        frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
    best = max((float(w) for w in np.asarray(weights).reshape(-1)), default=0.0)
    # HOG weights are not probabilities, so keep the old broad threshold range.
    hog_threshold = max(0.0, min(2.0, float(cfg["confidence"])))
    return best >= hog_threshold, best, "hog"


def enemy_status_payload(enabled: bool) -> dict:
    return {"t": "enemy_status", "enabled": enabled,
            "available": detector_available(), "backend": _enemy_backend}


def enemy_tracking_loop() -> None:
    """Detect person-shaped characters at low rate without using the GPU."""
    global _enemy_backend

    hit_streak = 0
    clear_streak = 0
    detected = False
    last_alert = 0.0
    last_enabled = False

    while True:
        with _profile_lock:
            cfg = dict(DEFAULT_ENEMY_TRACKING)
            cfg.update(PROFILE.get("enemy_tracking") or {})

        enabled = bool(cfg["enabled"])
        hz = max(0.5, min(4.0, float(cfg["scan_hz"])))
        if not enabled:
            if last_enabled:
                broadcast(enemy_status_payload(False))
                broadcast({"t": "enemy_clear"})
            last_enabled = False
            hit_streak = clear_streak = 0
            detected = False
            time.sleep(0.5)
            continue

        if not last_enabled:
            broadcast(enemy_status_payload(True))
            last_enabled = True

        if not detector_available():
            time.sleep(1.0)
            continue

        started = time.perf_counter()
        found = False
        best = 0.0
        try:
            sct = _sct()
            shot = sct.grab(sct.monitors[1])
            frame = np.asarray(shot, dtype=np.uint8)[:, :, :3]
            found, best, _enemy_backend = detect_enemy(frame, cfg)
        except Exception as exc:
            print("enemy tracking scan failed:", exc)

        if found:
            hit_streak += 1
            clear_streak = 0
        else:
            clear_streak += 1
            hit_streak = 0

        now = time.monotonic()
        if hit_streak >= 2 and (not detected or now - last_alert >= 4.0):
            detected = True
            last_alert = now
            broadcast({"t": "enemy_detected", "confidence": round(best, 2)})
        elif detected and clear_streak >= 2:
            detected = False
            broadcast({"t": "enemy_clear"})

        time.sleep(max(0.0, 1.0 / hz - (time.perf_counter() - started)))


def recenter() -> None:
    """Park the cursor in the middle of the primary screen.

    Absolute positioning is right here even though aiming is relative: the
    point is to land somewhere known, not to travel a distance. Pending
    sub-pixel remainders are dropped so the next aim packet starts clean.
    """
    global _acc_x, _acc_y
    _acc_x = _acc_y = 0.0
    if sys.platform == "win32":
        mouse.position = (_user32.GetSystemMetrics(0) // 2,
                          _user32.GetSystemMetrics(1) // 2)


def press(target) -> None:
    if target in ("fire", "ads"):
        mouse.press(Button.left if target == "fire" else Button.right)
    elif target in KEYMAP:
        keyboard.press(KEYMAP[target])


def release(target) -> None:
    if target in ("fire", "ads"):
        mouse.release(Button.left if target == "fire" else Button.right)
    elif target in KEYMAP:
        keyboard.release(KEYMAP[target])


def release_all() -> None:
    """Never leave a button stuck down if the phone drops off Wi-Fi."""
    global _ads_held
    for target in list(_held_buttons):
        try:
            release(target)
        except Exception:
            pass
    _held_buttons.clear()
    _ads_held = False


# ------------------------------------------------------------- dispatch ----
def dispatch(msg: dict) -> None:
    global _ads_held
    kind = msg.get("t")

    if kind == "aim":
        # Phone sends degrees rotated since the last packet, already
        # deadzoned and smoothed, so this stays independent of send rate.
        scale = CFG["ads_scale"] if _ads_held else 1.0
        move(-msg["yaw"] * CFG["sens_x"] * scale,
             -msg["pitch"] * CFG["sens_y"] * scale)

    elif kind == "btn":
        target, down = msg["id"], msg["down"]
        if down:
            if target in _held_buttons:
                return
            _held_buttons.add(target)
            press(target)
            if target == "ads":
                _ads_held = True
        else:
            _held_buttons.discard(target)
            release(target)
            if target == "ads":
                _ads_held = False

    elif kind == "tap":
        target = msg["id"]
        if target == "recenter":
            recenter()
        else:
            press(target)
            release(target)

    elif kind == "key":
        # A literal keystroke, for alert action buttons. Rules are configured
        # per game on the phone, so the key cannot come from a fixed KEYMAP.
        send_keys(str(msg.get("k", "")))

    elif kind == "macro":
        index = int(msg.get("i", -1))
        with _profile_lock:
            macro = PROFILE["macros"][index] if 0 <= index < len(PROFILE["macros"]) else None
        if macro and macro.get("keys"):
            send_keys(macro["keys"])

    elif kind == "macros":
        clean = []
        for raw in (msg.get("v") or [])[:MAX_MACROS]:
            label = str(raw.get("label", ""))[:10].strip()
            keys = str(raw.get("keys", ""))[:40].strip()
            clean.append({"label": label, "keys": keys})
        with _profile_lock:
            PROFILE["macros"] = clean
        save_profile()
        print(f"macros: {sum(1 for m in clean if m['keys'])} configured")

    elif kind == "rule_add":
        # The reference is cropped from the cached snapshot, not from a fresh
        # grab: the user marked the box on that frame, and the game has moved
        # on since.
        with _last_full_lock:
            full = _last_full
        if full is None:
            print("rule_add: no snapshot cached yet")
            return
        box = {k: max(0.0, min(1.0, float(msg.get(k, 0.0))))
               for k in ("sx", "sy", "sw", "sh")}
        box["sw"] = max(0.01, box["sw"])
        box["sh"] = max(0.01, box["sh"])
        crop = full.crop((
            int(box["sx"] * full.width), int(box["sy"] * full.height),
            int((box["sx"] + box["sw"]) * full.width),
            int((box["sy"] + box["sh"]) * full.height)))
        rule = {
            "name": str(msg.get("name", "Rule"))[:40],
            "msg":  str(msg.get("msg", ""))[:80],
            "key":  str(msg.get("key", ""))[:20],
            # Minimum seconds to keep the alert on screen. A kill or a knock
            # can flash for well under a second, which is long enough for the
            # matcher to catch and far too short for anyone to read.
            "dwell": max(0.5, min(60.0, float(msg.get("dwell", 3.0)))),
            "thresh": max(0.1, min(0.99, float(msg.get("thresh", DEFAULT_RULE_THRESH)))),
            "box": box,
            "ref": encode_patch(crop),
        }
        with _profile_lock:
            PROFILE["rules"].append(rule)
            rebuild_patches()
            index = len(PROFILE["rules"]) - 1
        save_profile()
        print("rule added:", rule["name"])
        # The state is still on screen right now, which is the one moment a
        # useful threshold can be measured.
        calibrate_rule(index)

    elif kind == "rule_test":
        calibrate_rule(int(msg.get("i", -1)), float(msg.get("seconds", 3.0)))

    elif kind == "rule_del":
        index = int(msg.get("i", -1))
        with _profile_lock:
            if 0 <= index < len(PROFILE["rules"]):
                PROFILE["rules"].pop(index)
                rebuild_patches()
        save_profile()

    elif kind == "rule_thresh":
        index = int(msg.get("i", -1))
        with _profile_lock:
            if 0 <= index < len(PROFILE["rules"]):
                PROFILE["rules"][index]["thresh"] = \
                    max(0.1, min(0.99, float(msg.get("thresh", DEFAULT_RULE_THRESH))))
        save_profile()

    elif kind == "profile":
        clean = []
        for raw in (msg.get("regions") or [])[:MAX_REGIONS]:
            region = dict(DEFAULT_REGION)
            for key in DEFAULT_REGION:
                if key in raw:
                    region[key] = max(0.0, min(1.0, float(raw[key])))
            # A zero-width grab would make mss raise on every frame.
            region["sw"] = max(0.01, region["sw"])
            region["sh"] = max(0.01, region["sh"])
            clean.append(region)
        with _profile_lock:
            # Assigned unconditionally: an empty list is a valid choice, and
            # keeping the old regions would resurrect panels the user deleted.
            PROFILE["regions"] = clean
            PROFILE["game"] = str(msg.get("game", PROFILE["game"]))[:80]
            PROFILE["on"] = bool(msg.get("on", True)) and bool(clean)
            snapshot = json.dumps(PROFILE)
        save_profile()
        print("profile:", snapshot)

    elif kind == "profile_new":
        fresh = blank_profile(str(msg.get("game", "New game"))[:80])
        # Never silently overwrite an existing game with the same slug.
        base, n = fresh["id"], 2
        while os.path.exists(profile_path(fresh["id"])):
            fresh["id"] = f"{base}-{n}"
            n += 1
        write_profile(fresh)
        activate(fresh["id"])
        broadcast({"t": "profiles", "v": list_profiles(), "active": PROFILE["id"]})

    elif kind == "profile_select":
        if activate(str(msg.get("id", ""))):
            broadcast({"t": "profiles", "v": list_profiles(),
                       "active": PROFILE["id"]})

    elif kind == "profile_delete":
        pid = slugify(str(msg.get("id", "")))
        for path in (profile_path(pid), cover_path(pid)):
            try:
                os.remove(path)
            except OSError:
                pass
        if PROFILE.get("id") == pid:
            load_profile()
        broadcast({"t": "profiles", "v": list_profiles(), "active": PROFILE.get("id")})

    elif kind == "cover_capture":
        # The cover comes from the game itself - one tap, always on theme, no
        # hunting for box art.
        try:
            img = Image.open(io.BytesIO(grab_jpeg(max_w=640, quality=76)))
            img.save(cover_path(PROFILE["id"]), "JPEG", quality=76)
            print("cover captured for", PROFILE["id"])
        except Exception as exc:
            print("cover capture failed:", exc)
        broadcast({"t": "profiles", "v": list_profiles(), "active": PROFILE["id"]})

    elif kind == "enemy_tracking":
        enabled = bool(msg.get("enabled", False))
        with _profile_lock:
            enemy = dict(DEFAULT_ENEMY_TRACKING)
            enemy.update(PROFILE.get("enemy_tracking") or {})
            enemy["enabled"] = enabled
            PROFILE["enemy_tracking"] = enemy
        save_profile()
        broadcast(enemy_status_payload(enabled))
        if not enabled:
            broadcast({"t": "enemy_clear"})
        print("enemy tracking:", "on" if enabled else "off")

    elif kind == "cfg":
        for key, value in msg.get("v", {}).items():
            if key in CFG:
                CFG[key] = float(value)
        # Tuning travels with the game, so persist it into the active profile.
        with _profile_lock:
            PROFILE["tuning"] = dict(CFG)
        save_profile()


async def handle(ws, path=None):
    peer = ws.remote_address[0] if ws.remote_address else "?"
    print(f"[ws] phone connected from {peer}")
    CLIENTS.add(ws)                # the rule matcher pushes alerts back here
    with _profile_lock:
        enemy_enabled = bool((PROFILE.get("enemy_tracking") or {}).get("enabled"))
    await ws.send(json.dumps(enemy_status_payload(enemy_enabled)))
    try:
        async for raw in ws:
            try:
                dispatch(json.loads(raw))
            except Exception as exc:
                print("[ws] bad packet:", exc)
    except websockets.ConnectionClosed:
        pass
    finally:
        CLIENTS.discard(ws)
        release_all()
        print("[ws] phone disconnected")


# ---------------------------------------------------------------- server ----
def lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/snapshot.jpg"):
            return self._snapshot()
        if self.path.startswith("/region.mjpg"):
            return self._region_stream()
        if self.path.startswith("/profile.json"):
            with _profile_lock:
                return self._json(dict(PROFILE))
        if self.path.startswith("/profiles.json"):
            return self._json({"v": list_profiles(), "active": PROFILE.get("id")})
        if self.path.startswith("/cover/"):
            return self._cover(self.path[7:].split("?")[0].replace(".jpg", ""))
        if self.path.startswith("/export/"):
            return self._export(self.path[8:].split("?")[0].replace(".json", ""))
        if self.path.startswith("/sessions.json"):
            return self._json({"v": list_sessions()})
        if self.path.startswith("/session/"):
            sid = self.path[9:].split("?")[0].replace(".json", "")
            try:
                with open(session_path(sid), encoding="utf-8") as fh:
                    return self._json(json.load(fh))
            except (OSError, ValueError):
                return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/session"):
            try:
                size = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(size).decode("utf-8"))
                sid = save_session(data)
            except Exception as exc:
                return self.send_error(400, f"bad session: {exc}")
            return self._json({"ok": True, "id": sid})
        if not self.path.startswith("/import"):
            return self.send_error(404)
        try:
            size = int(self.headers.get("Content-Length", 0))
            bundle = json.loads(self.rfile.read(size).decode("utf-8"))
            pid = import_bundle(bundle)
        except Exception as exc:
            return self.send_error(400, f"bad bundle: {exc}")
        broadcast({"t": "profiles", "v": list_profiles(), "active": PROFILE.get("id")})
        self._json({"ok": True, "id": pid})

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cover(self, pid):
        try:
            with open(cover_path(pid), "rb") as fh:
                body = fh.read()
        except OSError:
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _export(self, pid):
        """A self-contained bundle: cover and rule references travel inside it,
        so the file works on somebody else's machine."""
        try:
            with open(profile_path(pid), encoding="utf-8") as fh:
                bundle = json.load(fh)
        except (OSError, ValueError):
            return self.send_error(404)
        try:
            with open(cover_path(pid), "rb") as fh:
                bundle["cover_data"] = base64.b64encode(fh.read()).decode()
        except OSError:
            pass
        bundle["_format"] = "gyroaim.profile.1"
        body = json.dumps(bundle, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Disposition",
                         f'attachment; filename="{slugify(pid)}.gyroaim.json"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _snapshot(self):
        """One full-screen frame, for marking the region on the phone.

        The full-resolution original is kept in memory: a rule's reference has
        to be cropped from the very frame the user drew the box on, not from a
        fresh grab taken seconds later when the game has moved on.
        """
        global _last_full
        try:
            shot = _sct().grab(_sct().monitors[1])
            full = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            with _last_full_lock:
                _last_full = full
            body = grab_jpeg(max_w=1280, quality=72)
        except Exception as exc:                      # capture can fail
            self.send_error(500, f"capture failed: {exc}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _region_stream(self):
        """One marked region as MJPEG - an <img> tag is the whole client."""
        query = self.path.partition("?")[2]
        index = 0
        for part in query.split("&"):
            if part.startswith("i="):
                try:
                    index = int(part[2:])
                except ValueError:
                    index = 0
        self.send_response(200)
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        period = 1.0 / 20
        try:
            while True:
                start = time.perf_counter()
                with _profile_lock:
                    regions = PROFILE["regions"]
                    if index >= len(regions):
                        return                # region was removed; end stream
                    box = dict(regions[index])
                frame = grab_jpeg(box, max_w=480, quality=60)
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                 + b"Content-Length: "
                                 + str(len(frame)).encode() + b"\r\n\r\n"
                                 + frame + b"\r\n")
                # Pace to the target rate; the phone disconnecting shows up as
                # a broken pipe on the next write, which ends the thread.
                time.sleep(max(0, period - (time.perf_counter() - start)))
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def end_headers(self):
        # The client is edited constantly during tuning, and a phone quietly
        # serving a cached copy looks exactly like a change that did not work.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def serve_client(port: int) -> None:
    handler = functools.partial(QuietHandler, directory=CLIENT_DIR)
    http.server.ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http-port", type=int, default=8000)
    ap.add_argument("--ws-port", type=int, default=8001)
    args = ap.parse_args()

    global LOOP
    LOOP = asyncio.get_running_loop()

    load_profile()
    threading.Thread(target=serve_client, args=(args.http_port,),
                     daemon=True).start()
    threading.Thread(target=rule_loop, daemon=True).start()
    threading.Thread(target=enemy_tracking_loop, daemon=True).start()

    ip = lan_ip()
    print("\n  GyroAim agent running")
    print(f"  Open on your phone:  http://{ip}:{args.http_port}")
    print(f"  Control channel:     ws://{ip}:{args.ws_port}")
    print("  Ctrl-C to stop.\n")

    async with websockets.serve(handle, "0.0.0.0", args.ws_port,
                                ping_interval=5, ping_timeout=5):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        release_all()
        print("\nstopped.")
