"""
tools/os_control.py — OS-level controls: open apps, hotkeys, screenshots, typing.

Display-presence is detected via _has_display() on every call.
Docker / headless awareness is no longer handled here; set STT_MODE and
TTS_ENGINE in .env instead.
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys


class OSControl:

    _APP_MAP = {
        "firefox":      {"mac": "Firefox",            "linux": "firefox",          "win": "firefox"},
        "chrome":       {"mac": "Google Chrome",      "linux": "google-chrome",    "win": "chrome"},
        "chromium":     {"mac": "Chromium",           "linux": "chromium-browser", "win": "chromium"},
        "spotify":      {"mac": "Spotify",            "linux": "spotify",          "win": "spotify"},
        "vscode":       {"mac": "Visual Studio Code", "linux": "code",             "win": "code"},
        "code":         {"mac": "Visual Studio Code", "linux": "code",             "win": "code"},
        "terminal":     {"mac": "Terminal",           "linux": "gnome-terminal",   "win": "cmd"},
        "notepad":      {"mac": "TextEdit",           "linux": "gedit",            "win": "notepad"},
        "calculator":   {"mac": "Calculator",         "linux": "gnome-calculator", "win": "calc"},
        "file manager": {"mac": "Finder",             "linux": "nautilus",         "win": "explorer"},
        "files":        {"mac": "Finder",             "linux": "nautilus",         "win": "explorer"},
        "slack":        {"mac": "Slack",              "linux": "slack",            "win": "slack"},
        "zoom":         {"mac": "zoom.us",            "linux": "zoom",             "win": "zoom"},
        "vlc":          {"mac": "VLC",                "linux": "vlc",              "win": "vlc"},
        "discord":      {"mac": "Discord",            "linux": "discord",          "win": "discord"},
        "obsidian":     {"mac": "Obsidian",           "linux": "obsidian",         "win": "obsidian"},
        "gimp":         {"mac": "GIMP",               "linux": "gimp",             "win": "gimp"},
        "obs":          {"mac": "OBS",                "linux": "obs",              "win": "obs"},
        "blender":      {"mac": "Blender",            "linux": "blender",          "win": "blender"},
    }

    @staticmethod
    def _platform() -> str:
        if sys.platform == "darwin": return "mac"
        if sys.platform == "win32":  return "win"
        return "linux"

    @staticmethod
    def _has_display() -> bool:
        """Return True when a graphical display is available."""
        if sys.platform in ("win32", "darwin"):
            return True
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    def open_app(self, app: str) -> str:
        if not self._has_display():
            return (
                f"Cannot open '{app}' — no display detected (running headless). "
                "Set DISPLAY or WAYLAND_DISPLAY if you have a compositor running."
            )
        platform = self._platform()
        key      = app.lower().strip()
        resolved = self._APP_MAP.get(key, {}).get(platform, app)

        try:
            if platform == "mac":
                subprocess.Popen(["open", "-a", resolved])
            elif platform == "win":
                subprocess.Popen(["start", "", resolved], shell=True)
            else:
                subprocess.Popen(
                    [resolved],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return f"Opening {app}…"
        except FileNotFoundError:
            return (
                f"Could not find '{app}'. "
                "Please check that it is installed and on your PATH."
            )
        except Exception as exc:
            return f"Failed to open '{app}': {exc}"

    def hotkey(self, keys: str) -> str:
        if not self._has_display():
            return (
                f"Keyboard shortcut '{keys}' is not available — "
                "no display detected (running headless)."
            )
        try:
            import pyautogui
            parts = [k.strip() for k in keys.lower().split("+")]
            pyautogui.hotkey(*parts)
            return f"Sent hotkey: {keys}"
        except ImportError:
            return "pyautogui not installed. Run: pip install pyautogui"
        except Exception as exc:
            return f"Hotkey '{keys}' failed: {exc}"

    def type_text(self, text: str) -> str:
        if not self._has_display():
            return (
                "Text typing is not available — "
                "no display detected (running headless)."
            )
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.03)
            return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"
        except ImportError:
            return "pyautogui not installed. Run: pip install pyautogui"
        except Exception as exc:
            return f"Type text failed: {exc}"

    def screenshot(self, directory: str = ".") -> str:
        if not self._has_display():
            return (
                "Screenshots via pyautogui are not available — "
                "no display detected (running headless)."
            )
        try:
            import pyautogui
            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(os.path.abspath(directory), f"screenshot_{ts}.png")
            img  = pyautogui.screenshot()
            img.save(path)
            return f"Screenshot saved → {path}"
        except ImportError:
            return "pyautogui not installed. Run: pip install pyautogui"
        except Exception as exc:
            return f"Screenshot failed: {exc}"
