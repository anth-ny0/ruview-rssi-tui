# RuView RSSI TUI

A Textual-based terminal dashboard for experimenting with Wi-Fi RSSI motion detection on Linux.

This project wraps the RuView Linux RSSI collector with a cleaner TUI that supports:

- live RSSI monitoring
- baseline calibration
- motion scoring
- adjustable detection thresholds
- tuning tab
- explanation tab
- support for `wlan0`

## Important note

This is an experimental Wi-Fi RSSI motion detector.

It is not a security system, medical system, or guaranteed presence detector. RSSI can change for many reasons, including router behavior, interference, adapter power saving, multipath, distance, and normal Wi-Fi noise.

## Requirements

- Ubuntu or another Linux distro
- Python 3
- Wi-Fi interface such as `wlan0`
- connected Wi-Fi adapter
- `iw`

Install system tools:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip iw
