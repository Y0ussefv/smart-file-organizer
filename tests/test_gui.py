"""
Automated GUI unit tests using PySide6 in offscreen mode.
"""

import os
import sys
import pytest
from pathlib import Path

# Force Qt offscreen platform plugin for automated CI/headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from src.app.main_window import MainWindow
from src.core.models import FileItem, FileStatus, ScanSummary


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class TestGUI:

    def test_main_window_initialization(self, qapp, tmp_path):
        window = MainWindow()
        assert window.windowTitle() == "Smart File Organizer & Intelligent File Renamer"
        assert window.folder_input is not None
        assert window.btn_scan is not None
        assert window.preview_table is not None
        assert window.stats_widget is not None
        window.close()

    def test_table_population_and_selection(self, qapp, tmp_path):
        window = MainWindow()
        items = [
            FileItem(
                original_path=tmp_path / "doc1.pdf",
                original_name="doc1.pdf",
                new_name="Project_Charter.pdf",
                file_type="PDF Document",
                file_size=1024,
                status=FileStatus.READY_TO_RENAME,
                is_selected=True
            ),
            FileItem(
                original_path=tmp_path / "img1.png",
                original_name="img1.png",
                new_name="img1.png",
                file_type="PNG Image",
                file_size=2048,
                status=FileStatus.UNCHANGED,
                is_selected=False
            )
        ]

        summary = ScanSummary(total_files=2, ready_to_rename=1, unchanged=1)
        window._on_scan_finished(items, summary)

        # Check table row count
        assert window.preview_table.table.rowCount() == 2
        # Check KPI card values
        assert window.stats_widget.card_total.number_label.text() == "2"
        assert window.stats_widget.card_ready.number_label.text() == "1"

        # Test deselect all
        window.preview_table.deselect_all()
        assert window._count_selected_ready() == 0

        # Test select all
        window.preview_table.select_all()
        assert window._count_selected_ready() == 1

        window.close()

    def test_theme_toggle(self, qapp):
        window = MainWindow()
        initial_dark = window.is_dark_theme
        window._toggle_theme()
        assert window.is_dark_theme != initial_dark
        window._toggle_theme()
        assert window.is_dark_theme == initial_dark
        window.close()
