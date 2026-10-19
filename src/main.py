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
    app = QApplication(sys.argv)
    app.setApplicationName("Smart File Organizer")
    app.setApplicationDisplayName("Smart File Organizer & Intelligent File Renamer")
    app.setOrganizationName("SmartOrganizer")
    app.setApplicationVersion("1.0.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
