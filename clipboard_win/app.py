"""ClipboardWin application entry point.

This module implements a Windows-oriented clipboard history utility that keeps
running in the system tray, stores the history on disk, and exposes a
keyboard-driven pop-up window to re-use past clipboard items.

Although the implementation relies on Windows friendly packages such as
``pystray`` and ``keyboard``, the code is written so that it can run on other
platforms for development purposes. The clipboard polling approach is used so
that we do not need platform-specific clipboard hooks.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

import pyperclip
from PIL import Image, ImageDraw
import pystray
import keyboard
import tkinter as tk
from tkinter import ttk


POLLING_INTERVAL_SECONDS = 0.5
DEFAULT_MAX_HISTORY = 100
HOTKEY = "ctrl+shift+v"


def _default_storage_path() -> Path:
    """Return the history storage path inside the user's roaming directory."""
    base = os.environ.get("APPDATA")
    if base:
        base_path = Path(base)
    else:
        base_path = Path.home() / ".clipboardwin"
    data_dir = base_path / "ClipboardWin"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "history.json"


@dataclass
class ClipboardHistory:
    """A thread-safe clipboard history manager."""

    storage_path: Path = field(default_factory=_default_storage_path)
    max_items: int = DEFAULT_MAX_HISTORY

    def __post_init__(self) -> None:
        self._items: List[str] = []
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        """Load the history from disk if available."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._items = [str(item) for item in data][-self.max_items :]
            except (OSError, json.JSONDecodeError):
                # If we cannot load the file we silently reset the history.
                self._items = []

    def save(self) -> None:
        """Persist the history to disk."""
        try:
            with self.storage_path.open("w", encoding="utf-8") as handle:
                json.dump(self._items, handle, ensure_ascii=False, indent=2)
        except OSError:
            # Persisting is best-effort; we simply ignore failures.
            pass

    def add(self, text: str) -> None:
        """Append an item to the history if it is not duplicated."""
        if not text:
            return
        with self._lock:
            if self._items and self._items[-1] == text:
                return
            self._items.append(text)
            if len(self._items) > self.max_items:
                self._items = self._items[-self.max_items :]
            self.save()

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.save()

    def items(self) -> List[str]:
        with self._lock:
            return list(reversed(self._items))


class ClipboardMonitor(threading.Thread):
    """Background clipboard polling thread."""

    daemon = True

    def __init__(self, history: ClipboardHistory):
        super().__init__(name="ClipboardMonitor")
        self.history = history
        self._stop_event = threading.Event()
        try:
            self._last_value = pyperclip.paste()
        except pyperclip.PyperclipException:
            self._last_value = ""

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                current = pyperclip.paste()
            except pyperclip.PyperclipException:
                current = ""
            if current and current != self._last_value:
                self.history.add(current)
                self._last_value = current
            elif not current:
                self._last_value = ""
            time.sleep(POLLING_INTERVAL_SECONDS)


class HistoryWindow:
    """Pop-up Tkinter window showing the clipboard history."""

    def __init__(self, root: tk.Tk, history: ClipboardHistory):
        self.root = root
        self.history = history
        self.window: tk.Toplevel | None = None
        self.listbox: tk.Listbox | None = None
        self._current_items: List[str] = []

    def show(self) -> None:
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.lift()
            return

        self.window = tk.Toplevel(self.root)
        self.window.title("ClipboardWin")
        self.window.attributes("-topmost", True)
        self.window.geometry("500x400")
        self.window.configure(bg="#1e1e1e")

        self.window.bind("<Escape>", lambda event: self.close())
        self.window.bind("<FocusOut>", lambda event: self.close())

        label = ttk.Label(
            self.window,
            text="Double-click or press Enter to reuse an item.",
            padding=10,
        )
        label.pack(fill=tk.X)

        self.listbox = tk.Listbox(
            self.window,
            activestyle="none",
            font=("Segoe UI", 11),
        )
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._current_items = self.history.items()

        for item in self._current_items:
            preview = item.replace("\n", " ⏎ ")
            if len(preview) > 80:
                preview = preview[:77] + "..."
            self.listbox.insert(tk.END, preview)

        self.listbox.bind("<Double-Button-1>", self._on_activate)
        self.listbox.bind("<Return>", self._on_activate)
        self.listbox.focus_set()

    def _on_activate(self, event) -> None:
        if not self.listbox:
            return
        selection = self.listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self._current_items):
            return
        chosen = self._current_items[index]
        try:
            pyperclip.copy(chosen)
        except pyperclip.PyperclipException:
            return
        self.history.add(chosen)
        self.close()

    def close(self) -> None:
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.destroy()
        self.window = None
        self.listbox = None
        self._current_items = []


def create_tray_icon(show_history: Callable[[], None], clear_history: Callable[[], None], stop_callback: Callable[[], None]) -> pystray.Icon:
    image = Image.new("RGB", (64, 64), color="#1e90ff")
    draw = ImageDraw.Draw(image)
    draw.rectangle([8, 16, 56, 48], outline="white", width=3)
    draw.line([16, 28, 48, 28], fill="white", width=3)

    menu = pystray.Menu(
        pystray.MenuItem(f"Show history ({HOTKEY})", lambda: show_history()),
        pystray.MenuItem("Clear history", lambda: clear_history()),
        pystray.MenuItem("Quit", lambda: stop_callback()),
    )
    return pystray.Icon("ClipboardWin", image, "ClipboardWin", menu)


class Application:
    """Main application wiring everything together."""

    def __init__(self) -> None:
        self.history = ClipboardHistory()
        self.root = tk.Tk()
        self.root.withdraw()
        self.history_window = HistoryWindow(self.root, self.history)
        self.monitor = ClipboardMonitor(self.history)
        self.icon = create_tray_icon(
            show_history=self.show_history,
            clear_history=self.clear_history,
            stop_callback=self.stop,
        )
        self._icon_thread: threading.Thread | None = None
        self._hotkey_ref: int | None = None
        self._shutting_down = threading.Event()

    def start(self) -> None:
        self.monitor.start()
        self._hotkey_ref = keyboard.add_hotkey(HOTKEY, self.show_history)
        self._icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        self._icon_thread.start()
        try:
            self.root.mainloop()
        finally:
            if self._hotkey_ref is not None:
                keyboard.remove_hotkey(self._hotkey_ref)

    def stop(self) -> None:
        if self._shutting_down.is_set():
            return

        self._shutting_down.set()

        def _shutdown() -> None:
            self.icon.stop()
            self.monitor.stop()
            if self.monitor.is_alive():
                self.monitor.join(timeout=1)
            self.history_window.close()
            self.root.quit()

        self.root.after(0, _shutdown)

    def show_history(self) -> None:
        self.root.after(0, self.history_window.show)

    def clear_history(self) -> None:
        self.history.clear()
        self.root.after(0, self.history_window.close)


def main() -> None:
    app = Application()
    try:
        app.start()
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    main()
