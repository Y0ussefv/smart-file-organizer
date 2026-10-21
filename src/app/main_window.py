"""
Main Window for Smart File Organizer.
Integrates Dashboard, KPI stats cards, interactive preview table, background worker threads,
activity logs, and full action workflows (scan, preview, rename, undo, export).
"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QProgressBar, QPlainTextEdit, QFileDialog,
    QMessageBox, QSplitter, QStatusBar, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

from src.core.models import FileItem, FileStatus, ScanConfig, ScanSummary
from src.core.scanner import DirectoryScanner
from src.core.rename_engine import RenameEngine
from src.core.undo_manager import UndoManager
from src.storage.settings import SettingsManager
from src.storage.history import HistoryManager
from src.reports.report_manager import ReportManager
from src.app.theme import DARK_THEME_QSS, LIGHT_THEME_QSS
from src.app.widgets.stats_widget import StatsWidget
from src.app.widgets.preview_table import PreviewTableWidget
from src.app.dialogs import RenameConfirmationDialog, SettingsDialog, UndoDialog


class ScanWorker(QObject):
    """Background worker for scanning and analyzing files."""
    progress = Signal(int, int, str)
    item_found = Signal(object)
    finished = Signal(list, object)
    error = Signal(str)

    def __init__(self, config: ScanConfig):
        super().__init__()
        self.config = config
        self.scanner = DirectoryScanner(config)

    def run(self):
        try:
            items, summary = self.scanner.scan(
                progress_callback=lambda cur, tot, name: self.progress.emit(cur, tot, name),
                item_found_callback=lambda item: self.item_found.emit(item)
            )
            self.finished.emit(items, summary)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.scanner.cancel()


class RenameWorker(QObject):
    """Background worker for safely applying file renames."""
    progress = Signal(int, int, str)
    item_updated = Signal(object)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, items: List[FileItem], history_manager: HistoryManager):
        super().__init__()
        self.items = items
        self.engine = RenameEngine(history_manager)

    def run(self):
        try:
            records = self.engine.execute_renames(
                self.items,
                progress_callback=lambda cur, tot, name: self.progress.emit(cur, tot, name),
                item_callback=lambda item: self.item_updated.emit(item)
            )
            self.finished.emit(records)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.engine.cancel()


class MainWindow(QMainWindow):
    """Main desktop application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart File Organizer & Intelligent File Renamer")
        self.resize(1200, 780)
        self.setMinimumSize(900, 600)

        # Core managers
        self.settings_manager = SettingsManager()
        self.history_manager = HistoryManager()
        self.report_manager = ReportManager()

        self.current_items: List[FileItem] = []
        self.current_summary = ScanSummary()
        self.active_thread: Optional[QThread] = None
        self.active_worker: Optional[QObject] = None

        self.is_dark_theme = self.settings_manager.get("theme", "dark") == "dark"

        self._init_ui()
        self._apply_theme()
        self._restore_last_state()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Top Dashboard Panel
        dashboard = QFrame()
        dashboard.setObjectName("dashboard_frame")
        dash_layout = QVBoxLayout(dashboard)
        dash_layout.setContentsMargins(12, 12, 12, 12)
        dash_layout.setSpacing(10)

        # Title and Theme Toggle row
        title_row = QHBoxLayout()
        v_title = QVBoxLayout()
        app_title = QLabel("Smart File Organizer")
        app_title.setObjectName("title_label")
        app_sub = QLabel("Intelligent Content-Aware File Renamer with Non-Destructive Safety")
        app_sub.setObjectName("subtitle_label")
        v_title.addWidget(app_title)
        v_title.addWidget(app_sub)
        title_row.addLayout(v_title)

        title_row.addStretch()

        self.btn_theme = QPushButton("☀️ Light Mode" if self.is_dark_theme else "🌙 Dark Mode")
        self.btn_theme.clicked.connect(self._toggle_theme)

        self.btn_settings = QPushButton("⚙️ Settings")
        self.btn_settings.clicked.connect(self._open_settings)

        self.btn_undo = QPushButton("↺ Undo Session")
        self.btn_undo.clicked.connect(self._open_undo)

        title_row.addWidget(self.btn_theme)
        title_row.addWidget(self.btn_settings)
        title_row.addWidget(self.btn_undo)
        dash_layout.addLayout(title_row)

        # Folder Picker Row
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)

        self.btn_select_folder = QPushButton("📁 Select Folder...")
        self.btn_select_folder.setObjectName("primary_button")
        self.btn_select_folder.clicked.connect(self._browse_folder)

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select a folder to scan and organize...")
        self.folder_input.textChanged.connect(self._on_folder_changed)

        self.check_recursive = QCheckBox("Include Subfolders")
        self.check_recursive.setChecked(self.settings_manager.get("recursive", True))
        self.check_recursive.stateChanged.connect(lambda: self.settings_manager.set("recursive", self.check_recursive.isChecked()))

        self.check_domain_group = QCheckBox("Group Domain Folders")
        self.check_domain_group.setToolTip("Creates dedicated subfolders for matching domains/projects (e.g., logo delfa + pdf delfa ➔ delfa/)")
        self.check_domain_group.setChecked(self.settings_manager.get("group_by_domain", True))
        self.check_domain_group.stateChanged.connect(lambda: self.settings_manager.set("group_by_domain", self.check_domain_group.isChecked()))

        folder_row.addWidget(self.btn_select_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.check_recursive)
        folder_row.addWidget(self.check_domain_group)
        dash_layout.addLayout(folder_row)

        # Action Buttons Row
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.btn_scan = QPushButton("🔍 Start Scan")
        self.btn_scan.setObjectName("primary_button")
        self.btn_scan.clicked.connect(self.start_scan)

        self.btn_preview = QPushButton("👁️ Refresh Preview")
        self.btn_preview.clicked.connect(self.start_scan)

        self.btn_rename = QPushButton("✓ Rename Files")
        self.btn_rename.setObjectName("rename_button")
        self.btn_rename.setEnabled(False)
        self.btn_rename.clicked.connect(self.start_rename)

        self.btn_cancel = QPushButton("⏹ Cancel")
        self.btn_cancel.setObjectName("cancel_button")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_active_task)

        self.btn_export_reports = QPushButton("📊 Export Reports")
        self.btn_export_reports.clicked.connect(self.export_reports)

        action_row.addWidget(self.btn_scan)
        action_row.addWidget(self.btn_preview)
        action_row.addWidget(self.btn_rename)
        action_row.addWidget(self.btn_cancel)
        action_row.addStretch()
        action_row.addWidget(self.btn_export_reports)

        dash_layout.addLayout(action_row)

        # Progress bar & live indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        self.status_indicator = QLabel("Ready")
        self.status_indicator.setStyleSheet("color: #a5adcb; font-size: 11px;")

        dash_layout.addWidget(self.progress_bar)
        dash_layout.addWidget(self.status_indicator)

        main_layout.addWidget(dashboard)

        # 2. KPI Stats Cards Widget
        self.stats_widget = StatsWidget()
        main_layout.addWidget(self.stats_widget)

        # 3. Main Splitter: File Preview Table on Top, Activity Log on Bottom
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Preview Table
        self.preview_table = PreviewTableWidget()
        self.preview_table.item_selection_changed.connect(self._on_table_selection_changed)
        self.preview_table.item_edited.connect(self._on_item_manually_edited)
        splitter.addWidget(self.preview_table)

        # Activity Log Section
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.setSpacing(4)

        log_header = QHBoxLayout()
        log_title = QLabel("Activity Log")
        log_title.setStyleSheet("font-weight: 600; font-size: 11px; text-transform: uppercase; color: #939ab7;")
        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.setFixedHeight(22)
        self.btn_clear_log.clicked.connect(lambda: self.log_text.clear())
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(self.btn_clear_log)
        log_layout.addLayout(log_header)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(140)
        log_layout.addWidget(self.log_text)

        splitter.addWidget(log_container)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

        # 4. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Select a folder to begin.")

    def _apply_theme(self):
        """Switches between sleek dark and light stylesheets."""
        qss = DARK_THEME_QSS if self.is_dark_theme else LIGHT_THEME_QSS
        self.setStyleSheet(qss)
        self.preview_table.is_dark_theme = self.is_dark_theme
        self.preview_table.refresh_table()

    def _toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self.settings_manager.set("theme", "dark" if self.is_dark_theme else "light")
        self.btn_theme.setText("☀️ Light Mode" if self.is_dark_theme else "🌙 Dark Mode")
        self._apply_theme()

    def _restore_last_state(self):
        last_folder = self.settings_manager.get("last_folder", "")
        if last_folder and Path(last_folder).exists():
            self.folder_input.setText(last_folder)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Organize",
            self.folder_input.text() or str(Path.home())
        )
        if folder:
            self.folder_input.setText(folder)
            self.settings_manager.set("last_folder", folder)
            self.start_scan()

    def _on_folder_changed(self, text: str):
        path = Path(text.strip())
        is_valid = path.exists() and path.is_dir()
        self.btn_scan.setEnabled(is_valid)
        self.btn_preview.setEnabled(is_valid)

    def log_message(self, message: str):
        self.log_text.appendPlainText(message)

    # -------------------------------------------------------------
    # Scan Flow
    # -------------------------------------------------------------
    def start_scan(self):
        folder_str = self.folder_input.text().strip()
        folder_path = Path(folder_str)
        if not folder_path.exists() or not folder_path.is_dir():
            QMessageBox.warning(self, "Invalid Folder", "Please select a valid existing directory.")
            return

        self._set_ui_busy(True, "Scanning folder...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_message(f"Starting scan in: {folder_path} (Recursive: {self.check_recursive.isChecked()})")

        config = self.settings_manager.get_scan_config(folder_path)
        config.recursive = self.check_recursive.isChecked()
        config.group_by_domain = self.check_domain_group.isChecked()

        self.active_thread = QThread()
        self.active_worker = ScanWorker(config)
        self.active_worker.moveToThread(self.active_thread)

        self.active_thread.started.connect(self.active_worker.run)
        self.active_worker.progress.connect(self._on_scan_progress)
        self.active_worker.finished.connect(self._on_scan_finished)
        self.active_worker.error.connect(self._on_task_error)

        self.active_worker.finished.connect(self.active_thread.quit)
        self.active_worker.finished.connect(self.active_worker.deleteLater)
        self.active_thread.finished.connect(self.active_thread.deleteLater)

        self.active_thread.start()

    def _on_scan_progress(self, current: int, total: int, filename: str):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.status_indicator.setText(f"Analyzing {current}/{total}: {filename}")

    def _on_scan_finished(self, items: List[FileItem], summary: ScanSummary):
        self._set_ui_busy(False)
        self.progress_bar.setVisible(False)
        self.current_items = items
        self.current_summary = summary

        self.preview_table.set_items(items)
        self.stats_widget.update_stats(summary)

        self.log_message(
            f"Scan completed: {summary.total_files} files analyzed. "
            f"{summary.ready_to_rename} ready to rename, {summary.unchanged} unchanged, {summary.errors} errors."
        )
        self.status_bar.showMessage(f"Scan complete. {summary.ready_to_rename} files ready for rename.", 5000)
        self._update_rename_button_state()

        # Generate automatic reports after scan
        self._auto_save_reports(items, summary)

    # -------------------------------------------------------------
    # Rename Flow
    # -------------------------------------------------------------
    def start_rename(self):
        items_to_rename = [
            item for item in self.current_items
            if item.is_selected and item.status == FileStatus.READY_TO_RENAME
        ]

        if not items_to_rename:
            QMessageBox.information(self, "No Files Selected", "No files are currently selected for renaming.")
            return

        # Show confirmation dialog
        dialog = RenameConfirmationDialog(items_to_rename, self)
        if dialog.exec() != RenameConfirmationDialog.DialogCode.Accepted:
            self.log_message("Renaming operation cancelled by user.")
            return

        self._set_ui_busy(True, f"Renaming {len(items_to_rename)} files...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_message(f"Applying safe renames to {len(items_to_rename)} files...")

        self.active_thread = QThread()
        self.active_worker = RenameWorker(self.current_items, self.history_manager)
        self.active_worker.moveToThread(self.active_thread)

        self.active_thread.started.connect(self.active_worker.run)
        self.active_worker.progress.connect(self._on_rename_progress)
        self.active_worker.finished.connect(self._on_rename_finished)
        self.active_worker.error.connect(self._on_task_error)

        self.active_worker.finished.connect(self.active_thread.quit)
        self.active_worker.finished.connect(self.active_worker.deleteLater)
        self.active_thread.finished.connect(self.active_thread.deleteLater)

        self.active_thread.start()

    def _on_rename_progress(self, current: int, total: int, text: str):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.status_indicator.setText(f"{current}/{total}: {text}")

    def _on_rename_finished(self, records: list):
        self._set_ui_busy(False)
        self.progress_bar.setVisible(False)

        renamed_count = sum(1 for r in records if r.status == "RENAMED")
        error_count = sum(1 for r in records if r.status == "ERROR")

        self.preview_table.refresh_table()

        # Update summary counts
        self.current_summary.renamed += renamed_count
        self.current_summary.ready_to_rename -= renamed_count
        self.stats_widget.update_stats(self.current_summary)

        self.log_message(f"Rename complete: {renamed_count} files renamed, {error_count} errors.")
        self.status_bar.showMessage(f"Renamed {renamed_count} files.", 5000)
        self._update_rename_button_state()

        # Save post-rename reports automatically
        self._auto_save_reports(self.current_items, self.current_summary)

        QMessageBox.information(
            self,
            "Rename Complete",
            f"Successfully renamed {renamed_count} files." +
            (f"\n{error_count} files encountered errors (see activity log)." if error_count > 0 else "") +
            "\nReports have been generated automatically."
        )

    # -------------------------------------------------------------
    # Undo Flow
    # -------------------------------------------------------------
    def _open_undo(self):
        dialog = UndoDialog(self.history_manager, self)
        if dialog.exec() == UndoDialog.DialogCode.Accepted:
            sess_id = dialog.selected_session_id
            if not sess_id:
                return

            undo_mgr = UndoManager(self.history_manager)
            self.log_message(f"Reverting rename session: {sess_id}...")

            result = undo_mgr.undo_session(sess_id)
            self.log_message(f"Undo finished: {result.reverted_items} restored, {result.failed_items} failed.")

            msg = f"Reverted {result.reverted_items} files back to their original names."
            if result.failed_items > 0:
                msg += f"\n{result.failed_items} files could not be reverted (missing or destination occupied)."

            QMessageBox.information(self, "Undo Session Complete", msg)

            # Re-scan to update table if current folder matches
            if self.folder_input.text():
                self.start_scan()

    # -------------------------------------------------------------
    # Reports & Settings
    # -------------------------------------------------------------
    def _auto_save_reports(self, items: List[FileItem], summary: ScanSummary):
        if not items:
            return
        try:
            config = self.settings_manager.get_scan_config(Path(self.folder_input.text().strip()))
            csv_p, txt_p, json_p = self.report_manager.generate_all_reports(items, config, summary)
            self.log_message(f"Reports automatically generated in: {csv_p.parent}")
        except Exception as e:
            self.log_message(f"Notice: Automatic report generation skipped: {str(e)}")

    def export_reports(self):
        if not self.current_items:
            QMessageBox.information(self, "No Data", "Please scan a folder before exporting reports.")
            return

        export_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Directory to Save Reports",
            str(self.report_manager.export_dir)
        )
        if not export_dir:
            return

        target_dir = Path(export_dir)
        config = self.settings_manager.get_scan_config(Path(self.folder_input.text().strip()))

        csv_p, txt_p, json_p = self.report_manager.generate_all_reports(
            self.current_items,
            config,
            self.current_summary,
            custom_dir=target_dir
        )

        self.log_message(f"Exported reports to: {target_dir}")

        reply = QMessageBox.question(
            self,
            "Reports Exported",
            f"Reports successfully generated:\n• {csv_p.name}\n• {txt_p.name}\n• {json_p.name}\n\nOpen export folder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ReportManager.open_folder_in_file_manager(target_dir)

    def _open_settings(self):
        dialog = SettingsDialog(self.settings_manager, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self.log_message("Settings updated.")
            if self.current_items:
                # Prompt user to re-scan with new naming convention
                reply = QMessageBox.question(
                    self,
                    "Refresh Preview",
                    "Settings changed. Would you like to refresh proposed filenames using the updated rules?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.start_scan()

    # -------------------------------------------------------------
    # Task Control & Helpers
    # -------------------------------------------------------------
    def cancel_active_task(self):
        if self.active_worker and hasattr(self.active_worker, "cancel"):
            self.active_worker.cancel()
            self.log_message("Cancellation requested by user...")
            self.btn_cancel.setEnabled(False)

    def _on_task_error(self, err_msg: str):
        self._set_ui_busy(False)
        self.progress_bar.setVisible(False)
        self.log_message(f"ERROR: {err_msg}")
        QMessageBox.critical(self, "Operation Error", f"An error occurred:\n{err_msg}")

    def _set_ui_busy(self, is_busy: bool, status_msg: str = "Ready"):
        self.status_indicator.setText(status_msg)
        self.status_bar.showMessage(status_msg)
        self.btn_scan.setEnabled(not is_busy)
        self.btn_preview.setEnabled(not is_busy)
        self.btn_select_folder.setEnabled(not is_busy)
        self.btn_cancel.setEnabled(is_busy)
        self.btn_rename.setEnabled(not is_busy and self._count_selected_ready() > 0)

    def _on_table_selection_changed(self):
        self._update_rename_button_state()

    def _on_item_manually_edited(self, item: FileItem):
        self.log_message(f"Manual edit: '{item.original_name}' -> '{item.new_name}'")
        self._update_rename_button_state()

    def _count_selected_ready(self) -> int:
        return sum(
            1 for item in self.current_items
            if item.is_selected and item.status == FileStatus.READY_TO_RENAME and item.new_name != item.original_name
        )

    def _update_rename_button_state(self):
        count = self._count_selected_ready()
        self.btn_rename.setEnabled(count > 0)
        self.btn_rename.setText(f"✓ Rename {count} Files" if count > 0 else "✓ Rename Files")
