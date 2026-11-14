"""
Main application entry point for Smart File Organizer / BeeOrganizer.

    SmartFileOrganizer.exe                    open the window + watch Downloads in the background
    SmartFileOrganizer.exe --watch            background only (used at computer start-up)
    SmartFileOrganizer.exe --no-watch         window only (classic mode)
"""

import sys
from pathlib import Path

# Ensure 'src' is in python path
src_dir = Path(__file__).resolve().parent
project_root = src_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _set_windows_app_id() -> None:
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("rnj.smartfileorganizer.app.1.2")
        except Exception:
            pass


def _run_window_only() -> None:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from src.app.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Smart File Organizer")
    app.setApplicationDisplayName("Smart File Organizer & Intelligent File Renamer")
    app.setOrganizationName("SmartOrganizer")
    app.setApplicationVersion("1.3.0")

    icon_path = src_dir / "app" / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    sys.exit(app.exec())


def main():
    args = sys.argv[1:]

    from src.utils.logging_config import setup_logging
    setup_logging(log_file_name="smart_file_organizer.log")
    _set_windows_app_id()

    if "--no-watch" in args:
        _run_window_only()
        return

    # Default: background watcher (tray / menu bar). Window opens unless --watch.
    from src.watcher.tray_app import run
    sys.exit(run(show_window="--watch" not in args))


if __name__ == "__main__":
    main()
