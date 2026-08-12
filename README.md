# SmartHammerController

Turn an Android phone into a wireless gyro controller and mouse for Windows PC games. SmartHammerController reads the phone's motion sensors in the browser, sends controls over your local Wi-Fi, and converts them into mouse movement, mouse buttons, and keyboard input on the PC.

> No Android app or APK is required. The phone controller runs in Chrome and is served directly by the PC.

## Features

- **Gyroscopic mouse aiming** with independent horizontal and vertical sensitivity.
- **Rifle Aim mode** for holding the phone like a rifle, with automatic still-position calibration and manual recalibration.
- **Touch controller in landscape mode** with fire, aim-down-sights, movement, look, recenter, freeze-aim, weapon switching, reload, jump, crouch, and melee controls.
- **Multi-touch controls** so aiming, firing, moving, and other actions can be used together.
- **Per-game profiles** that save tuning, HUD regions, alert rules, macros, cover images, and enemy-scan settings.
- **Built-in game library** for creating, selecting, importing, exporting, and deleting profiles.
- **Live aim tuning** for sensitivity, ADS multiplier, deadzone, smoothing, update rate, aim acceleration, axis inversion, haptics, and the look stick.
- **Live PC HUD mirroring** with up to three configurable regions streamed to the phone.
- **Visual alert rules** that watch a selected area of the game screen for a captured state, show an alert on the phone, and can offer a one-tap key action.
- **Custom macros** with up to ten buttons and comma-separated key sequences.
- **Optional enemy scanning** using YOLO, with an OpenCV HOG fallback, phone-screen warnings, and vibration feedback.
- **Game cover capture** directly from the PC screen.
- **Automatic session recording** for controller runs longer than three seconds.
- **Aim analysis reports** covering shots, scoped time, movement, turn rate, flick speed, settle time, overshoot, firing while turning, shake, directional balance, and more.
- **Sensor diagnostics page** for checking phone motion events, axes, rate, browser support, and the PC connection.
- **Safety cleanup** that releases held mouse and keyboard inputs if the phone disconnects.
- **Local-first operation**: the controller and reports are served by the PC and work across the local network without a cloud account.

## How It Works

```text
Android motion + touch
          |
          |  Local Wi-Fi (HTTP + WebSocket)
          v
Windows PC agent
          |
          +--> Relative mouse movement and clicks
          +--> Keyboard movement and actions
          +--> Screen capture, HUD alerts, and session reports
```

The web interface uses HTTP port `8000` and the control connection uses WebSocket port `8001` by default.

## Requirements

### PC

- Windows 10 or Windows 11
- Python 3 installed and available from `py` or `python`
- A Wi-Fi or local network connection
- Permission for Python through Windows Firewall on private networks
- A game running on the primary monitor for HUD capture, alerts, and enemy scanning

### Phone

- An Android phone with a gyroscope
- Google Chrome
- The same Wi-Fi or local network as the PC
- Vibration support if haptic feedback is desired

## How to Install

### On PC — Recommended

1. Download or clone this repository to the Windows PC.
2. Install [Python](https://www.python.org/downloads/) if it is not already installed. During setup, enable **Add Python to PATH**.
3. Double-click **`Start GyroAim.bat`**.
4. On the first run, the launcher installs the required Python packages automatically:

   - `websockets`
   - `pynput`
   - `mss`
   - `numpy`
   - `pillow`
   - `opencv-python-headless`
   - `ultralytics`

5. If Windows Firewall asks for access, allow Python on **Private networks**.
6. Keep the terminal window open. It will display an address similar to:

   ```text
   Open on your phone:  http://192.168.1.42:8000
   Control channel:     ws://192.168.1.42:8001
   ```

The IP address will be different on your network.

### On PC — Manual Start

Open PowerShell or Command Prompt in the project folder and run:

```powershell
py -m pip install websockets pynput mss numpy pillow opencv-python-headless ultralytics
py server.py
```

If the `py` launcher is unavailable, replace `py` with `python`.

Optional custom ports:

```powershell
py server.py --http-port 8000 --ws-port 8001
```

### On Phone

1. Connect the phone to the **same Wi-Fi network** as the PC.
2. In Android Chrome, open the `http://...:8000` address printed by the PC agent.
3. Chrome normally blocks motion sensors on a plain HTTP local-network address. Open this page in Chrome:

   ```text
   chrome://flags/#unsafely-treat-insecure-origin-as-secure
   ```

4. Find **Insecure origins treated as secure**.
5. Add the exact controller origin shown by the PC, for example:

   ```text
   http://192.168.1.42:8000
   ```

6. Set the flag to **Enabled**, relaunch Chrome, and reopen the controller address.
7. Grant motion-sensor permission if Chrome asks for it.

> Use the PC's current address, including `http://` and port `8000`. If the PC's local IP changes later, update the saved origin in Chrome.

## First-Time Setup

1. Start the PC agent and open the controller on the phone.
2. Select an existing game profile or tap **New game**.
3. Hold the phone still and move it gently while watching the tuning reticle.
4. Adjust horizontal and vertical sensitivity, ADS scaling, deadzone, smoothing, axis direction, and optional aim acceleration.
5. If rightward phone movement sends the reticle left, use **Flip X**. Use **Flip Y** for reversed vertical movement.
6. Open **HUD setup** if you want mirrored screen regions, macros, or visual alerts.
7. Tap **Save & deploy**, then choose **Go live** or **Rifle aim**.

For predictable gyro response, disable mouse acceleration and mouse smoothing inside the game where possible.

## Default Controls

| Phone control | PC action |
|---|---|
| Rotate phone | Move mouse aim |
| Fire zone | Left mouse button |
| ADS zone | Right mouse button |
| Movement stick | `W`, `A`, `S`, `D` |
| Look stick | Mouse look |
| Primary / secondary weapon | `1` / `2` |
| Reload | `R` |
| Jump | `Space` |
| Crouch | `C` |
| Melee | `V` |
| Freeze aim | Temporarily stops gyro output |
| Recenter | Moves the Windows pointer to the center of the primary screen |

The fixed mappings can be changed in `KEYMAP` inside `server.py`. Profile macros can send letters, arrow keys, `Space`, `Tab`, `Enter`, `Shift`, `Ctrl`, `Alt`, `Esc`, `Backspace`, `Delete`, and `F1`–`F12`.

## Rifle Aim Mode

Hold the phone with its top edge pointing away from you, charging port toward you, display facing left, and rear cameras facing right. Keep it completely still during calibration. After calibration, swing the top edge left or right to aim horizontally and raise or lower it to aim vertically.

Rifle Aim only controls aiming; it does not activate the standard touch controller's fire, ADS, movement, or weapon controls. Use **Recalibrate** if the cursor moves while the phone is stationary.

## Game HUD, Alerts, and Macros

- **HUD regions:** Capture the primary PC display, select up to three source rectangles, and position their live mirrors on the phone.
- **Alert rules:** Capture a game state such as low ammo, select the matching area, set an alert name/message, and optionally assign a key. The PC compares the live region with the saved reference and notifies the phone when it matches.
- **Macros:** Create up to ten labelled buttons. Separate sequential keys with commas, for example `3,r` to select slot 3 and then reload.
- **Profiles:** Tuning and controller configuration are saved per game. Exported profile bundles include their cover and rule references and can be imported on another setup.

## Enemy Scan

Enemy Scan is optional and disabled by default. It captures a downscaled image from the primary display and looks for person-like objects. YOLO is preferred, with OpenCV HOG used as a fallback when available.

The default scan is CPU-oriented: approximately two scans per second on an image reduced to about 320 pixels wide. Results depend heavily on the game's art style, UI, camera view, and character design. A general person detector cannot reliably distinguish enemies from teammates, so treat it as an experimental warning system rather than a guaranteed detector.

## Sessions and Aim Reports

When you leave **Go live**, the phone uploads the run telemetry to the PC. Open **Past games** from the game library to see saved sessions and open a report in a browser on the PC.

Reports include a 3D aim path, timeline, action counts, aim-quality metrics, and plain-language observations. Session JSON files are stored in `sessions/`.

## Sensor Diagnostics

Open the following address from the phone to inspect live sensor readings and connection status:

```text
http://YOUR-PC-IP:8000/diag.html
```

Use this when the controller connects but the tuning reticle does not move. The most common cause is that Chrome's secure-origin flag has not been configured for the exact PC address.

## Troubleshooting

### The phone cannot open the controller

- Confirm both devices are on the same local network.
- Use the address printed by the PC agent rather than `localhost`.
- Keep the terminal open while using the controller.
- Allow Python through Windows Firewall on private networks.
- Check that ports `8000` and `8001` are not being used by another application.

### The page opens, but gyro aiming does not work

- Configure **Insecure origins treated as secure** using the exact current origin.
- Relaunch Chrome after changing the flag.
- Grant motion permission if prompted.
- Verify that the phone has a gyroscope.
- Open `/diag.html` to confirm motion events are arriving.

### Buttons work, but the game ignores mouse movement

- Run the project on Windows; its relative mouse path is designed for Windows raw-input games.
- Try the game in borderless-windowed mode.
- Test first in Windows or an offline aim trainer to separate game restrictions from connection problems.

### Enemy Scan is unavailable

Run `Start GyroAim.bat` again or manually install `ultralytics` and `opencv-python-headless`. The first YOLO use can take longer while the model loads.

## Important: Anti-Cheat and Fair Play

SmartHammerController injects synthetic mouse and keyboard input. Some multiplayer anti-cheat systems may detect or block synthetic input, and automation features such as macros or enemy scanning may violate a game's rules.

Use the project for development, accessibility experiments, offline games, private testing, or aim trainers unless the relevant game's rules explicitly allow it. You are responsible for how you use it.

## Privacy

The controller runs on the local network. HUD mirroring, visual alerts, cover capture, and enemy scanning capture the PC's primary display. Session telemetry and profile data are saved locally in the project folder. Do not expose ports `8000` or `8001` directly to the public internet.

## Hammer Respawn

I build **crazy gaming tech** and share it with the community.

- [YouTube — Hammer Respawn](https://www.youtube.com/@HammerRespawn)
- [Instagram — @hammerrespawn](https://www.instagram.com/hammerrespawn)

Follow along for gaming experiments, controller builds, and more community-shared tech.

---

Built by **Hammer Respawn**.
