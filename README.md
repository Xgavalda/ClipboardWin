# ClipboardWin

ClipboardWin is a lightweight Windows clipboard history utility written in
Python. It keeps running in the system tray, watches for clipboard changes, and
stores every captured entry so that you can re-use it later—even after a system
reboot.

## Features

- 🖱️ Lives in the Windows system tray with quick access actions.
- 🧠 Remembers up to 100 clipboard entries (configurable in code).
- ⌨️ Global hotkey (`Ctrl` + `Shift` + `V`) to display a pop-up history window.
- 📋 Double-click or press `Enter` on any history item to place it back on the
  clipboard.
- 💾 Persists the history to `%APPDATA%\ClipboardWin\history.json`.

## Requirements

Install the dependencies in a virtual environment (recommended):

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

> **Note:** The [`keyboard`](https://github.com/boppreh/keyboard) package
> requires administrator privileges the first time it is used so that it can
> register global hotkeys.

## Running the utility

```bash
python -m clipboard_win
```

Once running you will see a tray icon. Use the context menu to clear the
history or quit. Press `Ctrl` + `Shift` + `V` at any time to show the history
window and pick an entry to reuse.

## Starting automatically with Windows

1. Create a shortcut (`ClipboardWin.lnk`) that launches
   `python -m clipboard_win` inside your virtual environment.
2. Place the shortcut in the Windows Startup folder. You can open it by
   pressing `Win` + `R`, typing `shell:startup`, and hitting `Enter`.
3. The app will start alongside Windows and keep recording the clipboard.

Alternatively, create a scheduled task that triggers **At log on** and runs the
same shortcut or command.

## Configuration tweaks

- Adjust the polling interval (`POLLING_INTERVAL_SECONDS`) or maximum stored
  entries (`DEFAULT_MAX_HISTORY`) inside `clipboard_win/app.py` if needed.
- The storage location defaults to `%APPDATA%\ClipboardWin`, falling back to
  `~/.clipboardwin/ClipboardWin` when `%APPDATA%` is unavailable.

## Limitations

- The polling approach captures text clipboard data. File or bitmap clipboard
  entries are ignored.
- The app targets Windows; other platforms are useful only for development and
  may require adapting hotkey or tray icon integrations.
