"""
Registers (or removes) the Smart File Organizer native-messaging host for
Google Chrome, Microsoft Edge, Brave and Chromium on Windows, macOS and Linux.

    python main.py --install-browser-bridge
    python main.py --uninstall-browser-bridge
"""

import json
import os
import stat
import sys
from pathlib import Path
from typing import List

from src.integrations.native_host import HOST_NAME, PROJECT_ROOT
from src.utils.platform_utils import get_app_data_dir

# Fixed ID derived from the "key" in browser_extension/manifest.json.
EXTENSION_ID = "jnmoaimmgkjhfcngfnkgbldeeepghhhf"

WINDOWS_REG_PATHS = [
    r"Software\Google\Chrome\NativeMessagingHosts",
    r"Software\Microsoft\Edge\NativeMessagingHosts",
    r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
    r"Software\Chromium\NativeMessagingHosts",
]


def _posix_manifest_dirs() -> List[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
        return [
            base / "Google" / "Chrome" / "NativeMessagingHosts",
            base / "Microsoft Edge" / "NativeMessagingHosts",
            base / "BraveSoftware" / "Brave-Browser" / "NativeMessagingHosts",
            base / "Chromium" / "NativeMessagingHosts",
        ]
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return [
        cfg / "google-chrome" / "NativeMessagingHosts",
        cfg / "microsoft-edge" / "NativeMessagingHosts",
        cfg / "BraveSoftware" / "Brave-Browser" / "NativeMessagingHosts",
        cfg / "chromium" / "NativeMessagingHosts",
    ]


def _write_launcher(bridge_dir: Path) -> Path:
    python = Path(sys.executable)
    host_script = PROJECT_ROOT / "src" / "integrations" / "native_host.py"
    if sys.platform.startswith("win"):
        # Prefer python.exe (pythonw has no stdio, which native messaging needs).
        if python.name.lower() == "pythonw.exe":
            python = python.with_name("python.exe")
        launcher = bridge_dir / "smart_file_organizer_host.bat"
        launcher.write_text(
            f'@echo off\r\n"{python}" -u "{host_script}" %*\r\n', encoding="utf-8"
        )
    else:
        launcher = bridge_dir / "smart_file_organizer_host.sh"
        launcher.write_text(
            f'#!/bin/sh\nexec "{python}" -u "{host_script}" "$@"\n', encoding="utf-8"
        )
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return launcher


def _manifest(launcher: Path, extension_id: str) -> dict:
    return {
        "name": HOST_NAME,
        "description": "Smart File Organizer - auto-rename browser downloads",
        "path": str(launcher),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }


def install(extension_id: str = EXTENSION_ID) -> List[str]:
    bridge_dir = get_app_data_dir() / "browser_bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    launcher = _write_launcher(bridge_dir)
    manifest = _manifest(launcher, extension_id)
    done: List[str] = []

    if sys.platform.startswith("win"):
        import winreg
        manifest_path = bridge_dir / f"{HOST_NAME}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        for reg in WINDOWS_REG_PATHS:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{reg}\\{HOST_NAME}") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest_path))
            done.append(f"HKCU\\{reg}\\{HOST_NAME}")
    else:
        for d in _posix_manifest_dirs():
            if not d.parent.exists():
                continue  # browser not installed
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{HOST_NAME}.json"
            p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            done.append(str(p))
    return done


def uninstall() -> List[str]:
    removed: List[str] = []
    if sys.platform.startswith("win"):
        import winreg
        for reg in WINDOWS_REG_PATHS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{reg}\\{HOST_NAME}")
                removed.append(f"HKCU\\{reg}\\{HOST_NAME}")
            except OSError:
                pass
    else:
        for d in _posix_manifest_dirs():
            p = d / f"{HOST_NAME}.json"
            if p.exists():
                p.unlink()
                removed.append(str(p))
    return removed


def main(argv: List[str]) -> int:
    if "--uninstall-browser-bridge" in argv:
        removed = uninstall()
        print("Removed:\n  " + "\n  ".join(removed) if removed else "Nothing to remove.")
        return 0

    ext_id = EXTENSION_ID
    if "--extension-id" in argv:
        ext_id = argv[argv.index("--extension-id") + 1]
    registered = install(ext_id)
    print("Browser bridge installed for extension", ext_id)
    print("  " + "\n  ".join(registered) if registered else "  (no supported browser found)")
    print("\nNext: open chrome://extensions, enable Developer mode, click 'Load unpacked'")
    print(f"and pick: {PROJECT_ROOT / 'browser_extension'}")
    return 0
