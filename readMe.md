# Key & Mouse Recorder + Macro Tool (Python)

A desktop key & mouse recorder built with Python and `pynput`.  
It can record keyboard and mouse events, save them to a log file, replay them at different speeds, and run a simple Ctrl+click macro.

> ⚠️ This is a generic desktop automation tool.  
> Use it responsibly and respect the terms of service of any software or games you use it with.

---

## Features

- Record keyboard and mouse activity with timestamps.
- Save recordings to `event_log_X.txt` files.
- Load and replay the latest recording from disk.
- Adjustable replay speed from **0.5x to 10x**.
- Simple macro: hold **Ctrl** and perform **30 left-clicks**.
- Emergency stop: force-stop any replay/macro with **F2**.
- Automatically keeps track of the next log index on startup.

---

## Keybinds

When the script is running:

- **Delete** – Start / stop recording  
- **End** – Replay the current in-memory recording  
- **Page Down** – Save the current recording to `event_log_X.txt` and update `latest_log.txt`  
- **Home** – Load and replay the file referenced in `latest_log.txt`  
- **Insert** – Run the Ctrl + 30 left-click macro  
- **Middle Mouse Button (release)** – Also runs the Ctrl + 30 left-click macro  
- **= (equals)** – Increase replay speed (up to 10.0x)  
- **- (minus)** – Decrease replay speed (down to 0.5x)  
- **F2** – Force-stop any replay or macro  
- **F11** – Reset log index to 0 (next saved log is `event_log_1.txt` again)

---

## How It Works (Internals)

- Uses `pynput` to listen for keyboard and mouse events.
- Each event is stored as a dict with:
  - `time` (seconds offset from start)
  - `type` (`"keyboard"` or `"mouse"`)
  - `action` (`"press"`, `"release"`, `"click"`)
  - `button_or_key` (converted to/from strings for logging)
  - optional `x`, `y` for mouse position
- Records are written as tab-separated lines (TSV) to `event_log_X.txt`.
- On replay, events are scheduled using their timestamps and a **replay speed factor**, so you can slow down or speed up the sequence.
- F2 sets a global `stop_all_actions` flag and safely releases any keys or mouse buttons that might still be held.

---

## Installation

```bash
git clone https://github.com/<your-username>/key-mouse-recorder.git
cd key-mouse-recorder
pip install -r requirements.txt
