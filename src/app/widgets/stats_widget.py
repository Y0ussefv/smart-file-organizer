"""
KPI Stats Cards Widget for Smart File Organizer Dashboard.
Displays live counts for total files, supported/unsupported, ready to rename, and errors.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt

from src.core.models import ScanSummary


class StatCard(QFrame):
    """An individual KPI card displaying a metric."""

    def __init__(self, title: str, initial_value: str = "0", accent_color: str = "#8aadf4"):
        super().__init__()
        self.setProperty("class", "StatCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("card_title")

        self.number_label = QLabel(initial_value)
        self.number_label.setObjectName("card_number")
        self.number_label.setStyleSheet(f"color: {accent_color};")

        layout.addWidget(self.title_label)
        layout.addWidget(self.number_label)

    def set_value(self, val: int | str):
        self.number_label.setText(str(val))


class StatsWidget(QWidget):
    """Container holding all summary KPI cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.card_total = StatCard("Total Scanned", "0", "#cad3f5")
        self.card_supported = StatCard("Supported", "0", "#8bd5ca")
        self.card_unsupported = StatCard("Unsupported", "0", "#939ab7")
        self.card_ready = StatCard("Ready to Rename", "0", "#a6da95")
        self.card_unchanged = StatCard("Unchanged / Skip", "0", "#eed49f")
        self.card_errors = StatCard("Errors", "0", "#ed8796")

        layout.addWidget(self.card_total)
        layout.addWidget(self.card_supported)
        layout.addWidget(self.card_unsupported)
        layout.addWidget(self.card_ready)
        layout.addWidget(self.card_unchanged)
        layout.addWidget(self.card_errors)

    def update_stats(self, summary: ScanSummary):
        self.card_total.set_value(summary.total_files)
        self.card_supported.set_value(summary.supported_files)
        self.card_unsupported.set_value(summary.unsupported_files)
        self.card_ready.set_value(summary.ready_to_rename)
        self.card_unchanged.set_value(summary.unchanged + summary.skipped)
        self.card_errors.set_value(summary.errors)

    def reset(self):
        self.card_total.set_value(0)
        self.card_supported.set_value(0)
        self.card_unsupported.set_value(0)
        self.card_ready.set_value(0)
        self.card_unchanged.set_value(0)
        self.card_errors.set_value(0)
