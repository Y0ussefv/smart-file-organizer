"""
Cross-platform utilities for Smart File Organizer.
Provides consistent handling for file paths, app directories, OS detection, and system limits.
"""

import os
import sys
import platform
from pathlib import Path
from typing import Optional


# Known compound extensions that should be preserved as a single unit
COMPOUND_EXTENSIONS = {
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
    ".spec.ts",
    ".spec.js",
    ".test.ts",
    ".test.js",
    ".d.ts",
}

# Windows reserved file names (case-insensitive)
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

# Invalid characters per platform
WINDOWS_INVALID_CHARS = set('<>:"/\\|?*')
POSIX_INVALID_CHARS = {'/', '\0'}
MACOS_INVALID_CHARS = {'/', ':', '\0'}


def is_windows() -> bool:
    return sys.platform.startswith("win") or platform.system() == "Windows"


def is_macos() -> bool:
    return sys.platform == "darwin" or platform.system() == "Darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux") or platform.system() == "Linux"


def get_platform_name() -> str:
    if is_windows():
        return "Windows"
    elif is_macos():
        return "macOS"
    elif is_linux():
        return "Linux"
    return platform.system()


def get_app_data_dir(app_name: str = "SmartFileOrganizer") -> Path:
    """
    Returns the appropriate user application data directory across Windows, macOS, and Linux.
    Ensures the directory exists.
    """
    if is_windows():
        base = os.getenv("APPDATA")
        if base:
            data_dir = Path(base) / app_name
        else:
            data_dir = Path.home() / "AppData" / "Roaming" / app_name
    elif is_macos():
        data_dir = Path.home() / "Library" / "Application Support" / app_name
    else:
        # Linux / XDG
        xdg_data_home = os.getenv("XDG_DATA_HOME")
        if xdg_data_home:
            data_dir = Path(xdg_data_home) / app_name
        else:
            data_dir = Path.home() / ".local" / "share" / app_name

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_downloads_dir() -> Path:
    """The user's real Downloads folder (honours a moved Downloads folder on Windows)."""
    if is_windows():
        try:
            import ctypes
            from ctypes import wintypes
            import uuid as _uuid

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            u = _uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")  # FOLDERID_Downloads
            guid = GUID(u.fields[0], u.fields[1], u.fields[2],
                        (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0:
                path = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
                if path.is_dir():
                    return path
        except Exception:
            pass
    elif is_linux():
        try:
            import subprocess
            p = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=3)
            if p.returncode == 0 and p.stdout.strip() and Path(p.stdout.strip()).is_dir():
                return Path(p.stdout.strip())
        except Exception:
            pass
    return Path.home() / "Downloads"


def get_default_reports_dir() -> Path:
    """Returns the default directory where reports and history are exported."""
    reports_dir = get_app_data_dir() / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def split_filename_and_ext(filename: str) -> tuple[str, str]:
    """
    Correctly splits filename into (stem, extension), preserving compound extensions
    like .tar.gz, .spec.ts, etc.
    """
    lower_name = filename.lower()
    for compound in COMPOUND_EXTENSIONS:
        if lower_name.endswith(compound):
            stem = filename[:-len(compound)]
            ext = filename[-len(compound):]
            return stem, ext

    p = Path(filename)
    return p.stem, p.suffix


def is_safe_path(target_path: Path, base_directory: Optional[Path] = None) -> bool:
    """
    Verifies that a path does not escape the base directory (prevent path traversal)
    and is not a dangerous system directory or symlink cycle.
    """
    try:
        resolved_target = target_path.resolve()
        if base_directory:
            resolved_base = base_directory.resolve()
            # Must be inside or equal to base_dir
            if not (resolved_target == resolved_base or resolved_base in resolved_target.parents):
                return False
        return True
    except (OSError, ValueError):
        return False


def reveal_in_file_manager(path, select: bool = True) -> bool:
    """Shows a file in Explorer / Finder (selected), or opens a folder. False if it no longer exists."""
    import subprocess
    p = Path(path)
    if not p.exists():
        return False
    if sys.platform.startswith("win"):
        if select:
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            os.startfile(str(p))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p)] if select else ["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent if select else p)])
    return True
