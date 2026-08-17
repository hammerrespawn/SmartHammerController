# SmartHammerController

**Play PC games by moving your phone.**

Tilt and turn your phone to aim. Tap the screen to shoot, move, and reload.
Your phone becomes the controller — no extra app to install, nothing to buy.

> On your phone the app is called **GyroAim**. Same thing.

---

## See it working

[![Watch the demo](https://img.youtube.com/vi/mRvs5K08orc/maxresdefault.jpg)](https://www.youtube.com/watch?v=mRvs5K08orc)

**▶ [Watch the demo on YouTube](https://www.youtube.com/watch?v=mRvs5K08orc)**

Two minutes, and it shows the whole thing in use — aiming by tilting, the
sticks, and the enemy warning going off.

---

## What it looks like

<table>
<tr>
<td width="50%">

![The controller screen](docs/screenshots/controller.png)

**The controller.** Move stick on the left, look stick on the right, fire
across the whole right side, and your macros along the top.

</td>
<td width="50%">

![Enemy detected warning](docs/screenshots/enemy-alert.png)

**A warning going off.** The whole screen turns red and buzzes, so you notice
it without looking away from your monitor.

</td>
</tr>
</table>

---

## What you need

- A **Windows PC** with your game on it
- An **Android phone** with **Chrome**
- Both on the **same Wi-Fi**

That's it. If you can open a website on your phone, you can use this.

---

## Installing it (about 10 minutes, once)

You need an internet connection for this part. After it's done, everything
works offline.

### Step 1 — Install Python on the PC

This is the only thing you have to install by hand. It's free and takes two
minutes.

1. Go to **[python.org/downloads](https://www.python.org/downloads/)**
2. Click the big yellow **Download Python** button
3. Open the file it downloads
4. **Before clicking anything else**, tick the box at the bottom that says
   **"Add python.exe to PATH"**
5. Click **Install Now** and wait
6. Restart your PC

> **That tick box is the whole thing.** If you miss it, the controller won't be
> able to find Python and will tell you it's missing. If that happens, just run
> the installer again and tick it.

Already have Python? Skip this step. Anything from 3.9 upwards is fine.

### Step 2 — Put the folder on your PC

**If you were given a ZIP file:**

1. Right-click it → **Extract All…**
2. Choose somewhere sensible like `C:\Games\SmartHammerController`
3. Click **Extract**

> **Don't skip the extracting.** Windows lets you double-click straight into a
> ZIP as though it were a folder, and things will half-work in confusing ways
> if you do. Make sure you're in a real folder before going on.

**If you use GitHub**, download the ZIP from the green **Code** button and
extract it the same way — or, if you know what `git` is:

```bash
git clone <repository-url>
```

Avoid putting it in **Downloads**, or in a synced folder like OneDrive.
Somewhere plain like `C:\Games\` saves trouble later.

### Step 3 — Start it on the PC

Open the folder and double-click **`Start GyroAim.bat`**.

**The first time only**, it spends a minute or two installing the pieces it
needs, and you'll see:

```
First run - installing dependencies, this takes a minute...
```

Let it finish. Every start after this takes a couple of seconds.

When it's ready you'll see:

```
GyroAim agent running
Open on your phone:  http://10.0.0.3:8000
```

**Write that address down.** You'll type it into your phone.

> **If Windows asks whether to allow Python through the firewall, click
> Allow.** Tick the **Private networks** box. If you accidentally click Cancel,
> your phone won't be able to connect — restart the PC and try again.

Leave that black window open while you play. Closing it stops the controller.

### Step 4 — Open it on the phone

Nothing to install on the phone. Open **Chrome** and type the address from
Step 3 into the address bar.

You should see a dark screen with **HAMMER RESPAWN** at the top.

> Add it to your home screen while you're there — Chrome menu **⋮** → **Add to
> Home screen** — and it opens with one tap next time.

### Step 5 — Turn on motion sensors

This is the one fiddly bit, and you only do it once.

Chrome hides your phone's motion sensors from pages like this one. The app will
show you an orange box telling you so, with two **copy** buttons.

1. Tap the first **copy** button
2. Open a new Chrome tab and paste it into the address bar, then press Go
3. Find the box on that page and tap the second **copy** button back in the app
4. Paste that into the box
5. Change the dropdown next to it to **Enabled**
6. Tap the blue **Relaunch** button at the bottom
7. Open the address from Step 3 again

The orange box should now be gone. If it says **Sensors live**, you're done.

> **Why can't the app just do this for you?** Chrome blocks pages from opening
> its own settings, for security. Nothing can get around that — copy and paste
> is genuinely the only way.

### Step 6 — Turn your phone sideways

The controller only works in **landscape**. Turn your phone sideways and turn
**off** the rotation lock so it stays that way.

---

## Playing

> **Ready-made setups.** The `profiles.example` folder has finished profiles for
> **Fortnite**, **Apex Legends** and **ARC Raiders** — correct keybinds, ten
> macros and screen-mirror regions already set up. On the phone tap **Import**
> and pick the file for your game. Saves doing it all by hand.

1. Pick your game from the list on the phone
2. Tap the **▶** button on its card
3. Hold the phone **flat in both hands**, screen up, top edge pointing away
   from you
4. **Tilt** the phone to aim up and down, **turn** it to aim left and right

### The controller screen

```
┌──────────────────┬────────┬──────────────────┐
│       ADS        │ FREEZE │       FIRE       │
│   (aim down      ├────────┤                  │
│    sights)       │ CENTRE │   ( ● ) look     │
│                  │        │        stick     │
│   ( ● ) move     │        │                  │
└──────────────────┴────────┴──────────────────┘
```

| Control | What it does |
|---|---|
| **Left side** | Hold anywhere to aim down sights |
| **Left circle** | Push to walk — works like a joystick |
| **Right side** | Hold anywhere to fire · swipe up/down to swap weapons |
| **Right circle** | Push to turn quickly, for big swings |
| **Freeze** | Hold it, reposition your hands, let go — your aim stays put |
| **Centre** | Puts the mouse back in the middle of the screen |
| **Top row** | Your macro buttons — reload, grenade, jump, whatever you set |

The screen edges glow while you're doing something — amber on the right when
firing, yellow on the left when scoped — so you can tell what's happening
without looking down at the phone.

**Freeze is the one worth remembering.** Turning your body only goes so far
before your arms are twisted. Hold Freeze, bring your hands back to
comfortable, let go, and carry on. Like lifting a mouse and putting it back in
the middle of the mat.

When you're finished, tap **TUNE** in the corner to come back out.

---

## Making it feel right

Tap a game's card (not the ▶) to open its settings.

Sliders that matter, in the order worth trying:

| Slider | Turn it up if... | Turn it down if... |
|---|---|---|
| **Horizontal** | turning feels sluggish | you keep overshooting targets |
| **Vertical** | looking up/down is slow | your aim jumps around |
| **Smoothing** | your aim feels shaky | your aim feels laggy |
| **Deadzone** | the crosshair drifts on its own | small movements do nothing |

**Change one thing at a time**, then play a round. Changing three at once tells
you nothing about which one helped.

Each game remembers its own settings. What you set for one won't affect
another.

---

## The extras

You don't need any of these to play. Add them when you want them.

### Macros — up to 10 buttons

Ten buttons along the top of the controller. Put reload, grenades, jump —
whatever you press often — where your thumb can reach.

In the game's settings, open **Macros**. For each one type a **label** (what
you see) and a **key** (what gets pressed). A key can be a letter like `r`,
something like `space` or `f5`, or two in a row like `3,r`.

### Show part of your PC screen on the phone

Mirror up to three bits of your monitor — minimap, ammo, health — onto the
controller, so you can glance down instead of across.

![Health and ammo mirrored onto the phone during a match](docs/screenshots/hud-mirror.png)

*Health bar and weapon panel pulled onto the controller mid-fight, with the
macro row along the top.*

In the game's settings, open **Game HUD**, then:

1. Tap **⤢ Edit** next to *What to capture* and drag a box over the part of
   your screen you want
2. Tap **⤢ Edit** next to *Where to put it* and drag it where you want it on
   the phone
3. **Save and go live**

The boxes never block your controls — you can tap straight through them.

### Alerts — get told when something happens

Have the phone flash **"RELOAD NOW"** when your game shows it.

1. Get into that state in the game — actually run your ammo down
2. On the phone, open the game's settings → **Alerts** → **+ Add**
3. It counts down from 3, then takes a picture of your screen
4. Draw a box **tightly around just the words** — not the scenery around them
5. Give it a name and a message, and a key if you want a button to press
6. Save

It works out its own sensitivity automatically. If an alert isn't showing up,
press **test** on it while the thing is on your screen and it'll re-measure.

### Enemy Scan — a warning when someone's on screen

The PC watches your game a couple of times a second and, when it spots a
person, the phone flashes a big red **ENEMY DETECTED** and buzzes. There's a
small **ENEMY SCAN ON** tag in the corner while it's running so you always know
whether it's active.

Switch it on from the game's settings.

Two honest notes on this one:

- **It won't catch everything, and it will sometimes cry wolf.** It's looking at
  the same pixels you are, so anything you can't see, it can't see either — and
  it can mistake a poster or a teammate for a threat. Treat it as a nudge, not
  a radar.
- **This is the feature most likely to upset an anti-cheat.** Read the section
  further down before using it in an online match.

### See how you played

Every session is recorded. Tap **◷ Past games**, pick a run, tap **analyse**,
and it gives you a web address.

Type that address into your **PC's** browser and you get a full breakdown: a 3D
picture of everywhere you aimed that you can spin and zoom, plus plain-English
notes on things like whether you're overshooting your targets and how long your
aim takes to settle after a fast turn.

---

## When something goes wrong

### The phone can't open the page

- Is the black window still open on the PC?
- Are both on the **same Wi-Fi**? Not one on Wi-Fi and one on mobile data.
- **Did the address change?** Your router hands out new numbers sometimes.
  Check the black window for the current one.
- Windows may be blocking it. Restart the PC and try again — and if Windows
  asks whether to allow Python through the firewall, say **yes**.

### The page opens but tilting does nothing

Motion sensors aren't switched on. Go back to **Step 5**.

The app tells you which problem you have: *"Sensors blocked"* means Step 5
isn't done. *"No motion data"* means Chrome has sensor permission switched off
for that site — check the padlock icon in the address bar.

### Buttons work but the game ignores my aiming

Set the game to **Borderless Window** instead of Fullscreen, in its display
settings. Some games ignore everything else while in true fullscreen.

### Everything worked yesterday and now nothing does

Almost always the address changed. Check the black window.

---

## Before you play online — please read

This sends fake mouse and keyboard input to your game. Games with anti-cheat —
**Call of Duty, Fortnite, Apex Legends** — can't tell the difference between
this and cheating software, because from the outside it looks identical.

**You could be banned.** Not warned. Banned.

Try it in **single player, a private match, or offline** first. Whether to risk
your account online is your decision, and worth making on purpose rather than
finding out afterwards.

Aiming by tilting is a normal, fair way to play — it's built into the Steam
Deck and PlayStation controllers. The risk isn't that it's unfair. It's that
automated software can't prove it isn't.

**Enemy Scan deserves a separate warning.** Aiming with a phone is an input
method. Software telling you where people are is a different thing, and it's
exactly what anti-cheat is built to find. Keep it off in online matches.

---

## Things it doesn't do

- **iPhone and iPad** — the buttons work, but tilting to aim doesn't. Apple
  requires a secure connection for motion sensors and there's no way around it
  yet.
- **Accuracy and kill stats** — the reports show how you *moved*, not how you
  *scored*. The controller sends input; it never sees the result.

---

## Your data stays yours

Everything lives on your PC, in this folder. Your settings, your recordings,
your screen captures. Nothing is uploaded, there's no account, and it works
with the internet unplugged as long as the phone and PC are on the same Wi-Fi.

---

<div align="center">

**HAMMER RESPAWN**
AI • AR • Hardware • Chaos

</div>
