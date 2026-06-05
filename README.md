# RuView RSSI TUI

A clean Textual terminal dashboard for experimenting with Wi-Fi RSSI motion detection on Linux.

This project wraps the RuView Linux RSSI collector with a custom terminal UI that supports:

- Live RSSI monitoring
- Baseline calibration
- Motion scoring
- Adjustable detection thresholds
- Tuning controls
- Explanation tab
- Support for `wlan0`

---

## Important Note

This is an experimental Wi-Fi RSSI motion detector.

It is **not** a security system, medical system, or guaranteed presence detector.

RSSI can change for many reasons, including:

- Router behavior
- Wi-Fi interference
- Adapter power saving
- Multipath reflections
- Distance from the router
- Normal wireless noise

Use this only on networks and devices you own or have permission to test.

---

# Requirements

You need:

- Ubuntu or another Linux distro
- Python 3
- Git
- A Wi-Fi adapter connected to a network
- A Wi-Fi interface such as `wlan0`
- `iw`

---

# Installation

## 1. Install system packages

Run:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip iw
```

These packages are used for:

| Package | Purpose |
|---|---|
| `git` | Clone this repo and the RuView submodule |
| `python3` | Run the app |
| `python3-venv` | Create a virtual environment |
| `python3-pip` | Install Python dependencies |
| `iw` | Check wireless interfaces |

---

## 2. Clone the repository

Clone the repo with submodules:

```bash
git clone --recurse-submodules https://github.com/anth-ny0/ruview-rssi-tui.git
cd ruview-rssi-tui
```

If you already cloned it without submodules, run:

```bash
git submodule update --init --recursive
```

You should have this folder after the submodule downloads:

```text
vendor/RuView/
```

---

## 3. Create a Python virtual environment

From inside the repo folder:

```bash
python3 -m venv .venv
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Your terminal prompt should now look something like this:

```text
(.venv) user@machine:~/ruview-rssi-tui$
```

The virtual environment keeps this app’s Python packages separate from your system Python install.

---

## 4. Install Python dependencies

With the virtual environment activated, install the required Python packages:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

This installs the Python libraries needed to run the TUI and the RuView RSSI code.

---

## 5. Check your Wi-Fi interface

Run:

```bash
iw dev
```

Look for your wireless interface name.

Common examples:

```text
wlan0
wlp2s0
wlp3s0
```

Also check:

```bash
cat /proc/net/wireless
```

If your interface is `wlan0`, you do not need to change anything.

If your interface is not `wlan0`, edit the app:

```bash
nano app/ruv_tui.py
```

Find this line:

```python
INTERFACE = "wlan0"
```

Change it to your real Wi-Fi interface.

Example:

```python
INTERFACE = "wlp2s0"
```

Save and exit:

```text
Ctrl + O
Enter
Ctrl + X
```

---

## 6. Make sure Wi-Fi is connected

List available Wi-Fi networks:

```bash
nmcli dev wifi list
```

Connect to Wi-Fi if needed:

```bash
nmcli dev wifi connect "YOUR_WIFI_NAME" password "YOUR_WIFI_PASSWORD" ifname wlan0
```

Replace `wlan0` if your interface has a different name.

Example:

```bash
nmcli dev wifi connect "HomeWiFi" password "password123" ifname wlp2s0
```

Confirm the interface is connected and reporting wireless signal data:

```bash
iw dev
cat /proc/net/wireless
```

You should see your wireless interface listed with signal information.

---

# How To Run The Program

Every time you want to run the app, go into the project folder, activate the virtual environment, and run the Python file.

```bash
cd ~/ruview-rssi-tui
source .venv/bin/activate
python3 app/ruv_tui.py
```

If you are already inside the repo folder, you can just run:

```bash
source .venv/bin/activate
python3 app/ruv_tui.py
```

If your virtual environment is already active, run:

```bash
python3 app/ruv_tui.py
```

The app will open directly in your terminal.

---

# First-Time Use

## 1. Start the app

Run:

```bash
python3 app/ruv_tui.py
```

The app starts on the Monitor tab.

---

## 2. Stay still during calibration

When the app starts, it collects a baseline.

During calibration:

- Do not walk around near the Wi-Fi adapter.
- Do not move between the computer and router.
- Do not block or cover the antenna.
- Let the signal settle.
- Wait until the baseline is complete.

The app collects a still-room baseline for about 20 seconds.

It calculates:

- Baseline mean RSSI
- Baseline signal noise
- Baseline RSSI range

After calibration finishes, the app switches to live motion detection.

---

## 3. Test motion

After calibration finishes, move around between the Ubuntu machine and the Wi-Fi router.

The app will classify the signal as one of these states:

```text
STILL
POSSIBLE
MOTION
```

---

# Controls

```text
q       Quit the app
r       Recalibrate baseline
l       Toggle live baseline tracking

click   Select a tuning setting
← / →   Decrease / increase selected setting
↑ / ↓   Move between tuning settings

1 / 2   Range threshold down / up
3 / 4   Std multiplier down / up
5 / 6   Shift threshold down / up
```

---

# Tabs

## Monitor

The Monitor tab shows:

- Current status
- Current RSSI
- Calibration progress
- Baseline information
- Detection logic
- Motion score

---

## Tuning

The Tuning tab lets you adjust the detector live.

You can tune:

- RSSI Range Threshold
- Std Multiplier
- Average Shift Threshold

Click a setting to select it, then use:

```text
← decrease
→ increase
```

You can also use:

```text
↑ / ↓
```

to move between settings.

The selected setting description appears in the Current Settings pane.

---

## How It Works

The How It Works tab explains:

- What RSSI is
- How calibration works
- What the live window is
- How motion scoring works
- What each tuning value means

---

# What The Tuning Values Mean

## RSSI Range Threshold

This controls how much RSSI must swing before it looks suspicious.

The app calculates:

```text
live_range = strongest RSSI - weakest RSSI
```

Example:

```text
Strongest RSSI: -25 dBm
Weakest RSSI:   -32 dBm

live_range = 7 dB
```

If your range threshold is `5.0 dB`, that would trigger the range check.

Higher value:

```text
Fewer false positives
Less sensitive to quick RSSI jumps
```

Lower value:

```text
More sensitive to small RSSI jumps
```

---

## Std Multiplier

This controls how much noisier the live signal must be compared to the baseline.

The app calculates:

```text
live_std >= baseline_std × std_multiplier
```

Example:

```text
baseline_std = 0.80
std_multiplier = 3.0

trigger level = 2.40
```

If live signal noise rises above that level, the std check triggers.

Higher value:

```text
Ignores more normal Wi-Fi noise
```

Lower value:

```text
Detects smaller signal instability
```

---

## Average Shift Threshold

This controls how far the live average RSSI must move away from the baseline average.

The app calculates:

```text
avg_shift = abs(live_average - baseline_average)
```

Example:

```text
baseline_average = -24 dBm
live_average     = -29 dBm

avg_shift = 5 dB
```

If your shift threshold is `3.0 dB`, that would trigger the shift check.

Higher value:

```text
Less sensitive to slow signal drift
```

Lower value:

```text
Detects smaller average signal changes
```

---

# Recommended Tuning

If the app gives too many false positives, try:

```text
RSSI Range Threshold:      7.0 dB
Std Multiplier:            4.0x
Average Shift Threshold:   4.0 dB
```

If the app is not sensitive enough, try:

```text
RSSI Range Threshold:      4.0 dB
Std Multiplier:            2.5x
Average Shift Threshold:   2.5 dB
```

---

# Live Baseline Tracking

Press:

```text
l
```

to toggle live baseline tracking.

When live baseline is ON, the baseline slowly adapts while the app thinks the environment is still.

This can help if the Wi-Fi signal drifts slowly over time.

Do not leave live baseline ON while testing repeated movement, because the detector may slowly learn that movement as normal.

---

# Troubleshooting

## `ModuleNotFoundError: No module named 'numpy'`

Activate the virtual environment and reinstall dependencies:

```bash
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

---

## `ModuleNotFoundError: No module named 'textual'`

Run:

```bash
source .venv/bin/activate
python3 -m pip install textual
```

---

## Wi-Fi interface not found

Check your interface:

```bash
iw dev
```

Then edit:

```bash
nano app/ruv_tui.py
```

Change:

```python
INTERFACE = "wlan0"
```

to your real interface name.

---

## `/proc/net/wireless` does not show your interface

Make sure your Wi-Fi adapter is up:

```bash
sudo ip link set wlan0 up
```

Make sure it is connected to Wi-Fi:

```bash
nmcli dev wifi list
nmcli dev wifi connect "YOUR_WIFI_NAME" password "YOUR_WIFI_PASSWORD" ifname wlan0
```

Replace `wlan0` if needed.

---

## Submodule folder is empty

Run:

```bash
git submodule update --init --recursive
```

You should have:

```text
vendor/RuView/
```

---

## App starts but detection is bad

Try recalibrating:

```text
r
```

Make sure you stay still during calibration.

Then adjust the tuning values.

For fewer false positives:

```text
Increase thresholds
```

For more sensitivity:

```text
Decrease thresholds
```

---

# Project Structure

```text
ruview-rssi-tui/
├── app/
│   └── ruv_tui.py
├── vendor/
│   └── RuView/
├── requirements.txt
├── README.md
├── LICENSE
└── THIRD_PARTY_NOTICES.md
```

---

# Updating The README

After editing this README, commit and push:

```bash
git add README.md
git commit -m "Add complete install and run instructions"
git push
```

---

# Credits

This project uses the RuView Linux RSSI collector.

RuView:

```text
https://github.com/ruvnet/RuView
```

See:

```text
THIRD_PARTY_NOTICES.md
```

---

# License

This project is licensed under the MIT License.

RuView is also MIT licensed. See `THIRD_PARTY_NOTICES.md`.
