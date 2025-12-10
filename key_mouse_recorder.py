import time
import threading
import os
from pynput import keyboard, mouse

# -----------------------------------------------------------------------------
# Global Configuration
# -----------------------------------------------------------------------------

# Speed options from 0.5 to 10.0 in increments of 0.5
SPEED_OPTIONS = [i * 0.5 for i in range(1, 21)]  # [0.5, 1.0, 1.5, ..., 10.0]
speed_index = 1  # Default index => 1.0x
REPLAY_SPEED_FACTOR = SPEED_OPTIONS[speed_index]

# Flags for controlling recording, replay, macro, etc.
recording = False        # Whether we are currently recording new events
events = []              # List to hold all recorded events
start_time = None        # Time at which current recording started
stop_all_actions = False # Global flag to forcibly stop replay or macro

# F2 spam detection to stop a replay/macro (but not the entire program)
f2_press_count = 0
F2_SPAM_THRESHOLD = 1

# Log file indexing
log_index = 0  # Will be set on startup to continue from existing logs

# Pynput controllers
kb_controller = keyboard.Controller()
ms_controller = mouse.Controller()

# -----------------------------------------------------------------------------
# Initialization: figure out the correct next log index on startup
# -----------------------------------------------------------------------------
def initialize_log_index():
    """
    Scan the current directory for existing event_log_#.txt files
    and set log_index so that the next log file is the next integer.
    """
    global log_index

    existing_numbers = []
    for fname in os.listdir('.'):
        if fname.startswith("event_log_") and fname.endswith(".txt"):
            parts = fname.split("_")
            if len(parts) == 3 and parts[2].lower().endswith(".txt"):
                number_part = parts[2][:-4]  # remove ".txt"
                try:
                    num = int(number_part)
                    existing_numbers.append(num)
                except ValueError:
                    pass

    log_index = max(existing_numbers) if existing_numbers else 0

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def current_offset():
    """
    Returns the current elapsed time (in seconds) since the start of recording.
    If we're not recording, returns 0.
    """
    if start_time is None:
        return 0
    return time.time() - start_time

def next_log_filename():
    """
    Increments the global log_index and returns the new filename:
    e.g. "event_log_1.txt", "event_log_2.txt", etc.
    """
    global log_index
    log_index += 1
    return f"event_log_{log_index}.txt"

def save_events_to_file(filename):
    """
    Saves all events in the 'events' list to the specified filename.
    """
    with open(filename, "w", encoding="utf-8") as f:
        for event in events:
            x = event.get("x", "")
            y = event.get("y", "")
            line = (
                f"{event['time']:.4f}\t"
                f"{event['type']}\t"
                f"{event['action']}\t"
                f"{_format_key_or_button(event['button_or_key'])}\t"
                f"{x}\t"
                f"{y}\n"
            )
            f.write(line)
    print(f"[INFO] Event log saved to '{filename}'.")

def update_latest_log_file(filename):
    """
    Saves the specified filename to latest_log.txt
    """
    with open("latest_log.txt", "w", encoding="utf-8") as f:
        f.write(filename)
    print(f"[INFO] 'latest_log.txt' updated to point to '{filename}'.")

def load_events_from_file(filename):
    """
    Loads events from a specified file into a list of event dicts.
    Returns the list of loaded events (could be empty).
    """
    loaded_events = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) < 4:
                    continue

                t = float(parts[0])
                etype = parts[1]
                action = parts[2]
                bk_string = parts[3]

                x_str = parts[4] if len(parts) >= 5 else ""
                y_str = parts[5] if len(parts) >= 6 else ""

                bk_object = _parse_key_or_button(etype, bk_string)

                if x_str.strip() and y_str.strip():
                    try:
                        x_val = float(x_str)
                        y_val = float(y_str)
                    except ValueError:
                        x_val = None
                        y_val = None
                else:
                    x_val = None
                    y_val = None

                event_dict = {
                    "time": t,
                    "type": etype,
                    "action": action,
                    "button_or_key": bk_object
                }
                if x_val is not None and y_val is not None:
                    event_dict["x"] = x_val
                    event_dict["y"] = y_val

                loaded_events.append(event_dict)

        if loaded_events:
            print(f"[INFO] Loaded {len(loaded_events)} events from '{filename}'.")
        else:
            print(f"[WARN] No valid events found in '{filename}'.")
    except FileNotFoundError:
        print(f"[WARN] File '{filename}' not found!")
    return loaded_events

def replay_events(events_list=None):
    """
    Replay a list of recorded events at REPLAY_SPEED_FACTOR.
    If no list is provided, replays the in-memory 'events'.
    """
    global REPLAY_SPEED_FACTOR, stop_all_actions

    if events_list is None:
        events_list = events
    if not events_list:
        print("[INFO] No events to replay.")
        return

    print(f"[INFO] Replaying events at {REPLAY_SPEED_FACTOR}x speed...")
    stop_all_actions = False  # Reset before each new replay

    pressed_keys = set()          # Track which keys we've pressed
    pressed_mouse_buttons = set() # Track which mouse buttons we've pressed

    replay_start = time.time()
    first_event_time = events_list[0]["time"]

    for e in events_list:
        if stop_all_actions:
            print("[INFO] Replay forcibly stopped by F2.")
            break

        scaled_offset = (e["time"] - first_event_time) / REPLAY_SPEED_FACTOR
        wait_time = scaled_offset - (time.time() - replay_start)
        if wait_time > 0:
            time.sleep(wait_time)

        if e["type"] == "keyboard":
            if e["action"] == "press":
                kb_controller.press(e["button_or_key"])
                pressed_keys.add(e["button_or_key"])
            elif e["action"] == "release":
                kb_controller.release(e["button_or_key"])
                pressed_keys.discard(e["button_or_key"])
        elif e["type"] == "mouse":
            if "x" in e and "y" in e:
                ms_controller.position = (e["x"], e["y"])
            if e["action"] == "press":
                ms_controller.press(e["button_or_key"])
                pressed_mouse_buttons.add(e["button_or_key"])
            elif e["action"] == "release":
                ms_controller.release(e["button_or_key"])
                pressed_mouse_buttons.discard(e["button_or_key"])
            elif e["action"] == "click":
                ms_controller.click(e["button_or_key"])

    # If forced to stop, release anything still pressed
    if stop_all_actions:
        print("[INFO] Forcibly releasing any pressed keys/buttons...")
        for pk in pressed_keys:
            try:
                kb_controller.release(pk)
            except:
                pass
        for mb in pressed_mouse_buttons:
            try:
                ms_controller.release(mb)
            except:
                pass

    print("[INFO] Replay finished.")
    stop_all_actions = False

def _format_key_or_button(obj):
    """
    Converts a Key or Button object into a string representation
    suitable for saving in logs.
    """
    if isinstance(obj, keyboard.Key):
        return f"Key.{obj.name}"
    elif isinstance(obj, mouse.Button):
        return f"Button.{obj.name}"
    else:
        # For KeyCode or raw chars
        return str(obj)

def _parse_key_or_button(etype, string_repr):
    """
    Re-creates the keyboard or mouse object from a string representation.
    """


    string_repr = string_repr.strip()
    # Remove wrapping quotes if present
    if len(string_repr) >= 2 and string_repr.startswith("'") and string_repr.endswith("'"):
        string_repr = string_repr[1:-1]

    if etype == "keyboard":
        if string_repr.startswith("Key."):
            key_name = string_repr[4:]
            for k in keyboard.Key:
                if k.name == key_name:
                    return k
            return string_repr  # fallback
        else:
            # single character
            return keyboard.KeyCode.from_char(string_repr)
    elif etype == "mouse":
        if string_repr.startswith("Button."):
            btn_name = string_repr[7:]
            for b in mouse.Button:
                if b.name == btn_name:
                    return b
            return string_repr
        else:
            return string_repr
    return string_repr

# -----------------------------------------------------------------------------
# Macro Function
# -----------------------------------------------------------------------------
def ctrl_click_30_times():
    """
    Holds CTRL and performs 30 left mouse clicks in sequence.
    Checks 'stop_all_actions' to see if it should abort.
    """
    global stop_all_actions
    print("[MACRO] Holding CTRL and clicking left mouse 30 times...")

    kb_controller.press(keyboard.Key.ctrl)
    time.sleep(0.2)

    for i in range(30):
        if stop_all_actions:
            print("[MACRO] Macro forcibly stopped by F2.")
            break
        ms_controller.press(mouse.Button.left)
        ms_controller.release(mouse.Button.left)
        time.sleep(0.13)

    # Safely release Ctrl even if we break early
    kb_controller.release(keyboard.Key.ctrl)
    print("[MACRO] Completed (or stopped) 30 Ctrl+Left Clicks.")
    stop_all_actions = False

# -----------------------------------------------------------------------------
# Mouse Listener Callbacks
# -----------------------------------------------------------------------------
def on_click(x, y, button, pressed):
    """
    If recording, record press/release.
    If the middle button is *released*, start the 30-click macro in its own thread.
    """
    global recording
    if recording:
        events.append({
            "time": current_offset(),
            "type": "mouse",
            "action": "press" if pressed else "release",
            "button_or_key": button,
            "x": x,
            "y": y
        })

    # Fire macro on middle-mouse release
    if not pressed and button == mouse.Button.middle:
        threading.Thread(target=ctrl_click_30_times, daemon=True).start()

# -----------------------------------------------------------------------------
# Keyboard Listener Callbacks
# -----------------------------------------------------------------------------
def on_press(key):
    global recording, start_time
    global f2_press_count, F2_SPAM_THRESHOLD
    global REPLAY_SPEED_FACTOR, speed_index
    global stop_all_actions, log_index

    # F2 spam detection
    if key == keyboard.Key.f2:
        f2_press_count += 1
        if f2_press_count >= F2_SPAM_THRESHOLD:
            print("[ALERT] F2 pressed. Forcing any replay/macro to stop.")
            stop_all_actions = True
            f2_press_count = 0
        return  # don't log F2
    else:
        f2_press_count = 0

    # Start/stop recording on Delete
    if key == keyboard.Key.delete:
        recording = not recording
        if recording:
            print("[INFO] Recording started. Press Delete again to stop.")
            events.clear()
            start_time = time.time()
        else:
            print("[INFO] Recording stopped.")

    # Replay the in-memory events on End
    elif key == keyboard.Key.end:
        print("[INFO] End key pressed. Replaying current in-memory events...")
        threading.Thread(target=replay_events, daemon=True).start()

    # Save events to file on Page Down
    elif key == keyboard.Key.page_down:
        if recording:
            filename = next_log_filename()
            print(f"[INFO] Page Down pressed. Saving event log as '{filename}'...")
            save_events_to_file(filename)
            update_latest_log_file(filename)
        else:
            print("[WARN] You are NOT recording, so nothing to save.")

    # Load & replay latest_log.txt on Home
    elif key == keyboard.Key.home:
        print("[INFO] Home key pressed. Will load & replay 'latest_log.txt'.")
        if os.path.exists("latest_log.txt"):
            with open("latest_log.txt", "r", encoding="utf-8") as f:
                latest_file = f.read().strip()
            if latest_file and os.path.exists(latest_file):
                loaded = load_events_from_file(latest_file)
                if loaded:
                    threading.Thread(target=replay_events, args=(loaded,), daemon=True).start()
                else:
                    print("[WARN] Could not load events from file.")
            else:
                print("[WARN] 'latest_log.txt' found but not a valid file.")
        else:
            print("[WARN] 'latest_log.txt' not found, no logs yet.")

    # Run 30-click macro on Insert (in separate thread)
    elif key == keyboard.Key.insert:
        threading.Thread(target=ctrl_click_30_times, daemon=True).start()

    # Reset log index on F11
    elif key == keyboard.Key.f11:
        print("[INFO] F11 pressed. Log index has been reset to 0.")
        log_index = 0

    # Increase replay speed on '='
    elif hasattr(key, 'char') and key.char == '=':
        if speed_index < len(SPEED_OPTIONS) - 1:
            speed_index += 1
            REPLAY_SPEED_FACTOR = SPEED_OPTIONS[speed_index]
            print(f"[INFO] Replay speed changed to {REPLAY_SPEED_FACTOR}x")
        else:
            print(f"[INFO] Already at max speed: {SPEED_OPTIONS[speed_index]}x")

    # Decrease replay speed on '-'
    elif hasattr(key, 'char') and key.char == '-':
        if speed_index > 0:
            speed_index -= 1
            REPLAY_SPEED_FACTOR = SPEED_OPTIONS[speed_index]
            print(f"[INFO] Replay speed changed to {REPLAY_SPEED_FACTOR}x")
        else:
            print(f"[INFO] Already at min speed: {SPEED_OPTIONS[speed_index]}x")

    # Record pressed keys if we're recording (avoid special keys we handled above)
    if recording and key not in (
        keyboard.Key.delete,
        keyboard.Key.end,
        keyboard.Key.page_down,
        keyboard.Key.home,
        keyboard.Key.insert,
        keyboard.Key.f2,
        keyboard.Key.f11
    ):
        # Avoid logging '=' and '-' (used for speed control)
        if not (hasattr(key, 'char') and key.char in ('=', '-')):
            events.append({
                "time": current_offset(),
                "type": "keyboard",
                "action": "press",
                "button_or_key": key
            })

def on_release(key):
    # Log keyboard releases if recording (skip special control keys)
    if recording and key not in (
        keyboard.Key.delete,
        keyboard.Key.end,
        keyboard.Key.page_down,
        keyboard.Key.home,
        keyboard.Key.insert,
        keyboard.Key.f2,
        keyboard.Key.f11
    ):
        if not (hasattr(key, 'char') and key.char in ('=', '-')):
            events.append({
                "time": current_offset(),
                "type": "keyboard",
                "action": "release",
                "button_or_key": key
            })

# -----------------------------------------------------------------------------
# Main Routine
# -----------------------------------------------------------------------------
def main():
    """
    Entry point for the script. Sets up:
    - Log indexing from existing files
    - Keyboard & Mouse Listeners
    - Waits until the keyboard listener is stopped
    """
    initialize_log_index()

    print("\n"
          "=======================================================\n"
          "  Key & Mouse Recorder with Logs & 30-Click Macro\n"
          "=======================================================\n"
          "How it works:\n"
          " - Press [Delete] to START or STOP recording.\n"
          " - Press [End] to replay the in-memory events.\n"
          " - Press [Page Down] (while recording) to save to event_log_X.txt,\n"
          "   and update 'latest_log.txt'.\n"
          " - Press [Home] to load and replay 'latest_log.txt'.\n"
          " - Press [Insert] or Middle Mouse Button (on release) to run\n"
          "   a macro that holds Ctrl and clicks Left Mouse 30 times.\n"
          " - Press [=] or [-] to adjust replay speed (0.5 to 10.0 in steps of 0.5).\n"
          f" - Press [F2] {F2_SPAM_THRESHOLD} times rapidly to STOP any replay/macro.\n"
          " - Press [F11] to reset the log index to 0.\n"
          "=======================================================\n"
          f"Initial replay speed = {REPLAY_SPEED_FACTOR}x\n"
          "Note: High replay speeds may be too fast in some environments.\n")

    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    mouse_listener = mouse.Listener(on_click=on_click)

    keyboard_listener.start()
    mouse_listener.start()

    # Wait for the keyboard listener to exit
    keyboard_listener.join()
    mouse_listener.stop()

    print("[INFO] Program has exited gracefully.")

if __name__ == "__main__":
    main()
