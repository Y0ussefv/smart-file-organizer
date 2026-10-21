"""
Main application entry point for Smart File Organizer.
Initializes the Qt Application, configures system logging, and launches the desktop interface.
"""

import sys
from pathlib import Path

# Ensure 'src' is in python path
src_dir = Path(__file__).resolve().parent
project_root = src_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.app.main_window import MainWindow
from src.utils.logging_config import setup_logging


def main():
    # Setup application-wide logging
    setup_logging(log_file_name="smart_file_organizer.log")

    # High DPI scaling attributes are default on Qt 6 / PySide6
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("rnj.smartfileorganizer.app.1.2")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Smart File Organizer")
    app.setApplicationDisplayName("Smart File Organizer & Intelligent File Renamer")
    app.setOrganizationName("SmartOrganizer")
    app.setApplicationVersion("1.2.0")

    icon_path = src_dir / "app" / "assets" / "icon.png"
    if icon_path.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    if icon_path.exists():
        from PySide6.QtGui import QIcon
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
