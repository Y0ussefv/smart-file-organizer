"""
Interactive File Preview Table Widget for Smart File Organizer.
Supports in-place manual editing of proposed filenames, real-time filtering,
search, multi-column sorting, selection checkboxes, and custom status badge rendering.
"""

from pathlib import Path
from typing import List, Optional, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QComboBox, QPushButton, QLabel, QMenu,
    QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QAction

from src.core.models import FileItem, FileStatus
from src.app.theme import get_status_badge_style
from src.reports.report_manager import ReportManager


class PreviewTableWidget(QWidget):
    """
    Rich interactive table for reviewing and editing proposed file renames.
    """
    item_selection_changed = Signal()
    item_edited = Signal(FileItem)

    COL_CHECKBOX = 0
    COL_ORIGINAL = 1
    COL_PROPOSED = 2
    COL_EXT = 3
    COL_TYPE = 4
    COL_SIZE = 5
    COL_TITLE = 6
    COL_STATUS = 7
    COL_EXPLANATION = 8

    HEADERS = [
        "", "Original Filename", "Proposed New Filename (Editable)",
        "Ext", "File Type", "Size", "Detected Title / Summary", "Status", "Explanation"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[FileItem] = []
        self._is_populating = False
        self.is_dark_theme = True

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Filter and Search Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files, extensions, or titles...")
        self.search_input.textChanged.connect(self.apply_filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems([
            "All Statuses",
            "Ready to Rename",
            "Unchanged",
            "Skipped",
            "Renamed",
            "Errors"
        ])
        self.status_filter.currentIndexChanged.connect(self.apply_filter)

        self.type_filter = QComboBox()
        self.type_filter.addItem("All File Types")
        self.type_filter.currentIndexChanged.connect(self.apply_filter)

        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self.select_all)

        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.clicked.connect(self.deselect_all)

        self.record_count_label = QLabel("0 files displayed")
        self.record_count_label.setStyleSheet("color: #a5adcb; font-weight: 600;")

        filter_bar.addWidget(QLabel("Filter:"))
        filter_bar.addWidget(self.search_input, 2)
        filter_bar.addWidget(self.status_filter)
        filter_bar.addWidget(self.type_filter)
        filter_bar.addWidget(self.btn_select_all)
        filter_bar.addWidget(self.btn_deselect_all)
        filter_bar.addWidget(self.record_count_label)

        layout.addLayout(filter_bar)

        # 2. Main Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemChanged.connect(self._on_item_changed)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECKBOX, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_ORIGINAL, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_PROPOSED, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_EXT, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TITLE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_EXPLANATION, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(self.COL_ORIGINAL, 220)
        self.table.setColumnWidth(self.COL_PROPOSED, 240)
        self.table.setColumnWidth(self.COL_TITLE, 220)

        layout.addWidget(self.table)

    def set_items(self, items: List[FileItem]):
        """Populates the table with scanned file items."""
        self.items = items
        self._update_type_filter_options()
        self.refresh_table()

    def _update_type_filter_options(self):
        """Populates type filter dropdown with detected file types."""
        types = sorted({item.file_type for item in self.items if item.file_type})
        current = self.type_filter.currentText()
        self.type_filter.blockSignals(True)
        self.type_filter.clear()
        self.type_filter.addItem("All File Types")
        for t in types:
            self.type_filter.addItem(t)
        idx = self.type_filter.findText(current)
        if idx >= 0:
            self.type_filter.setCurrentIndex(idx)
        self.type_filter.blockSignals(False)

    def refresh_table(self):
        """Redraws rows based on items and active filter."""
        self._is_populating = True
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        visible_count = 0
        search_query = self.search_input.text().strip().lower()
        status_filter = self.status_filter.currentText()
        type_filter = self.type_filter.currentText()

        for item in self.items:
            # Check filter conditions
            if not self._item_matches_filter(item, search_query, status_filter, type_filter):
                continue

            visible_count += 1
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            check_item.setCheckState(Qt.CheckState.Checked if item.is_selected else Qt.CheckState.Unchecked)
            check_item.setData(Qt.ItemDataRole.UserRole, item)
            self.table.setItem(row, self.COL_CHECKBOX, check_item)

            # Original Filename
            orig_item = QTableWidgetItem(item.original_name)
            orig_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, self.COL_ORIGINAL, orig_item)

            # Proposed New Filename (Editable)
            prop_item = QTableWidgetItem(item.new_name)
            # Editable only if item is not an error
            if item.status != FileStatus.ERROR:
                prop_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            else:
                prop_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if item.manual_override:
                prop_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.table.setItem(row, self.COL_PROPOSED, prop_item)

            # Extension
            ext_item = QTableWidgetItem(item.original_ext)
            ext_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, self.COL_EXT, ext_item)

            # File Type
            type_item = QTableWidgetItem(item.file_type)
            type_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, self.COL_TYPE, type_item)

            # Size
            size_item = QTableWidgetItem(item.formatted_size)
            size_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            size_item.setData(Qt.ItemDataRole.UserRole, item.file_size)  # For numeric sorting
            self.table.setItem(row, self.COL_SIZE, size_item)

            # Detected Title
            title_text = item.detected_title or item.content_summary or ""
            title_item = QTableWidgetItem(title_text)
            title_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, self.COL_TITLE, title_item)

            # Status Badge
            status_item = QTableWidgetItem(item.status.display_name)
            status_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            bg_col, fg_col = get_status_badge_style(item.status.value, self.is_dark_theme)
            status_item.setBackground(QColor(bg_col))
            status_item.setForeground(QColor(fg_col))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, self.COL_STATUS, status_item)

            # Explanation
            exp_item = QTableWidgetItem(item.explanation)
            exp_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if item.error_message:
                exp_item.setToolTip(item.error_message)
            self.table.setItem(row, self.COL_EXPLANATION, exp_item)

        self.table.setSortingEnabled(True)
        self._is_populating = False
        self.record_count_label.setText(f"{visible_count} of {len(self.items)} files displayed")

    def _item_matches_filter(self, item: FileItem, query: str, status_filter: str, type_filter: str) -> bool:
        if type_filter != "All File Types" and item.file_type != type_filter:
            return False

        if status_filter == "Ready to Rename" and item.status != FileStatus.READY_TO_RENAME:
            return False
        elif status_filter == "Unchanged" and item.status != FileStatus.UNCHANGED:
            return False
        elif status_filter == "Skipped" and item.status != FileStatus.SKIPPED:
            return False
        elif status_filter == "Renamed" and item.status != FileStatus.RENAMED:
            return False
        elif status_filter == "Errors" and item.status != FileStatus.ERROR:
            return False

        if query:
            matchable = f"{item.original_name} {item.new_name} {item.original_ext} {item.detected_title or ''} {item.explanation}".lower()
            if query not in matchable:
                return False

        return True

    def apply_filter(self):
        self.refresh_table()

    def select_all(self):
        self._set_all_selected(True)

    def deselect_all(self):
        self._set_all_selected(False)

    def _set_all_selected(self, selected: bool):
        for item in self.items:
            if item.status == FileStatus.READY_TO_RENAME:
                item.is_selected = selected
        self.refresh_table()
        self.item_selection_changed.emit()

    def _on_item_changed(self, table_item: QTableWidgetItem):
        if self._is_populating:
            return

        row = table_item.row()
        check_cell = self.table.item(row, self.COL_CHECKBOX)
        if not check_cell:
            return
        file_item: FileItem = check_cell.data(Qt.ItemDataRole.UserRole)
        if not file_item:
            return

        # Checkbox toggled
        if table_item.column() == self.COL_CHECKBOX:
            is_checked = (table_item.checkState() == Qt.CheckState.Checked)
            file_item.is_selected = is_checked
            self.item_selection_changed.emit()

        # Proposed Name manually edited
        elif table_item.column() == self.COL_PROPOSED:
            edited_text = table_item.text().strip()
            if edited_text and edited_text != file_item.new_name:
                file_item.new_name = edited_text
                file_item.manual_override = True

                # If matches original name, set unchanged; otherwise ready
                if edited_text == file_item.original_name:
                    file_item.status = FileStatus.UNCHANGED
                    file_item.explanation = "Restored to original name manually."
                    file_item.is_selected = False
                else:
                    file_item.status = FileStatus.READY_TO_RENAME
                    file_item.explanation = f"Manually edited by user: '{edited_text}'"
                    file_item.is_selected = True

                self.item_edited.emit(file_item)
                self.refresh_table()

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        check_cell = self.table.item(row, self.COL_CHECKBOX)
        if not check_cell:
            return
        file_item: FileItem = check_cell.data(Qt.ItemDataRole.UserRole)
        if not file_item:
            return

        menu = QMenu(self)

        edit_act = QAction("Edit Proposed Name...", self)
        edit_act.triggered.connect(lambda: self.table.editItem(self.table.item(row, self.COL_PROPOSED)))
        menu.addAction(edit_act)

        reset_act = QAction("Reset to Original Name", self)
        reset_act.triggered.connect(lambda: self._reset_item_name(file_item))
        menu.addAction(reset_act)

        menu.addSeparator()

        open_folder_act = QAction("Open Containing Folder", self)
        open_folder_act.triggered.connect(lambda: ReportManager.open_folder_in_file_manager(file_item.original_path.parent))
        menu.addAction(open_folder_act)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _reset_item_name(self, item: FileItem):
        item.new_name = item.original_name
        item.status = FileStatus.UNCHANGED
        item.explanation = "Reset to original filename."
        item.is_selected = False
        item.manual_override = False
        self.refresh_table()
        self.item_selection_changed.emit()
