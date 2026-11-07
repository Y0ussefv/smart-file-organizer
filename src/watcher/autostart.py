"""
Start BeeOrganizer (background mode) automatically when the user logs in.

- Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
- macOS:   ~/Library/LaunchAgents/com.rnj.beeorganizer.plist
- Linux:   ~/.config/autostart/beeorganizer.desktop
"""

import os
import plistlib
import sys
from pathlib import Path
from typing import List

APP_NAME = "BeeOrganizer"
MAC_LABEL = "com.rnj.beeorganizer"
WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> List[str]:
    """Command that starts the background watcher."""
    if getattr(sys, "frozen", False):  # PyInstaller .exe / .app
        return [sys.executable, "--watch"]
    python = Path(sys.executable)
    if sys.platform.startswith("win") and python.name.lower() == "python.exe":
        pythonw = python.with_name("pythonw.exe")  # no console window at login
        if pythonw.exists():
            python = pythonw
    main_py = Path(__file__).resolve().parents[2] / "main.py"
    return [str(python), str(main_py), "--watch"]


def _mac_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def _linux_desktop_path() -> Path:
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return cfg / "autostart" / "beeorganizer.desktop"


def _quote(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


def is_enabled() -> bool:
    if sys.platform.startswith("win"):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY) as key:
                winreg.QueryValueEx(key, APP_NAME)
                return True
        except OSError:
            return False
    if sys.platform == "darwin":
        return _mac_plist_path().exists()
    return _linux_desktop_path().exists()


def enable() -> None:
    cmd = launch_command()
    if sys.platform.startswith("win"):
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, " ".join(_quote(c) for c in cmd))
    elif sys.platform == "darwin":
        path = _mac_plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            plistlib.dump({
                "Label": MAC_LABEL,
                "ProgramArguments": cmd,
                "RunAtLoad": True,
                "ProcessType": "Interactive",
                "LimitLoadToSessionType": "Aqua",
            }, f)
    else:
        path = _linux_desktop_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\nType=Application\nName=BeeOrganizer\n"
            f"Exec={' '.join(_quote(c) for c in cmd)}\nX-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )


def disable() -> None:
    if sys.platform.startswith("win"):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, APP_NAME)
        except OSError:
            pass
    elif sys.platform == "darwin":
        _mac_plist_path().unlink(missing_ok=True)
    else:
        _linux_desktop_path().unlink(missing_ok=True)
