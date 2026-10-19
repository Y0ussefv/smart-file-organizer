"""
Dialogs for Smart File Organizer.
Includes Rename Confirmation, Settings Configuration, Undo Session Manager, and Reports Export dialogs.
"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QFileDialog, QListWidget, QListWidgetItem,
    QMessageBox, QFrame, QTextEdit, QScrollArea, QWidget
)
from PySide6.QtCore import Qt

from src.core.models import ScanConfig, NamingConvention, FileItem
from src.storage.settings import SettingsManager
from src.storage.history import HistoryManager
from src.reports.report_manager import ReportManager


class RenameConfirmationDialog(QDialog):
    """Safety confirmation modal displayed before executing actual renames on disk."""

    def __init__(self, items_to_rename: List[FileItem], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm File Renaming")
        self.setMinimumWidth(550)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # Header Title
        title = QLabel(f"Ready to Rename {len(items_to_rename)} Files")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #a6da95;")
        layout.addWidget(title)

        desc = QLabel(
            "Please review the proposed operations below before applying changes.\n"
            "• Existing files will never be overwritten.\n"
            "• Operations are atomic and verified.\n"
            "• Full CSV, TXT, and JSON reports will be saved automatically.\n"
            "• Changes can be reverted via the Undo manager if files remain available."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Preview list of files
        list_label = QLabel("Preview of Changes:")
        list_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(list_label)

        list_widget = QListWidget()
        for item in items_to_rename[:100]:
            list_widget.addItem(f"{item.original_name}  ➔  {item.new_name}")

        if len(items_to_rename) > 100:
            list_widget.addItem(f"... and {len(items_to_rename) - 100} more files.")

        layout.addWidget(list_widget)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_confirm = QPushButton(f"Rename {len(items_to_rename)} Files Now")
        self.btn_confirm.setObjectName("rename_button")
        self.btn_confirm.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_confirm)

        layout.addLayout(btn_row)


class SettingsDialog(QDialog):
    """Configuration dialog for naming rules, conventions, and safety limits."""

    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self.setWindowTitle("Organizer Settings & Naming Rules")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Naming convention
        layout.addWidget(QLabel("Naming Style Convention:"))
        self.cb_convention = QComboBox()
        for nc in NamingConvention:
            self.cb_convention.addItem(nc.value)
        cur_nc = self.settings.get("naming_convention", NamingConvention.TITLE_CASE.value)
        self.cb_convention.setCurrentText(cur_nc)
        layout.addWidget(self.cb_convention)

        # Space replacement
        layout.addWidget(QLabel("Space Replacement Separator:"))
        self.cb_separator = QComboBox()
        self.cb_separator.addItem("Underscore (_)", "_")
        self.cb_separator.addItem("Hyphen (-)", "-")
        self.cb_separator.addItem("Space ( )", " ")
        cur_sep = self.settings.get("space_replacement", "_")
        for i in range(self.cb_separator.count()):
            if self.cb_separator.itemData(i) == cur_sep:
                self.cb_separator.setCurrentIndex(i)
        layout.addWidget(self.cb_separator)

        # Max length
        layout.addWidget(QLabel("Maximum Filename Length (characters):"))
        self.spin_max_len = QSpinBox()
        self.spin_max_len.setRange(20, 255)
        self.spin_max_len.setValue(self.settings.get("max_filename_length", 80))
        layout.addWidget(self.spin_max_len)

        # Date prefix
        self.check_date_prefix = QCheckBox("Add date prefix (e.g. 2026-10-19_...)")
        self.check_date_prefix.setChecked(self.settings.get("add_date_prefix", False))
        layout.addWidget(self.check_date_prefix)

        # Preserve extension
        self.check_preserve_ext = QCheckBox("Preserve original file extensions")
        self.check_preserve_ext.setChecked(self.settings.get("preserve_extension", True))
        layout.addWidget(self.check_preserve_ext)

        # Include subfolders by default
        self.check_recursive = QCheckBox("Scan subfolders recursively by default")
        self.check_recursive.setChecked(self.settings.get("recursive", True))
        layout.addWidget(self.check_recursive)

        # Structured format for unlabelled/hash image names
        self.check_unlabelled_images = QCheckBox("Auto-format cryptic unlabelled images (e.g. 4a73b82d.png ➔ PNG_1330x1183.png)")
        self.check_unlabelled_images.setChecked(self.settings.get("rename_unlabelled_images", True))
        layout.addWidget(self.check_unlabelled_images)

        # Safe file size limit
        layout.addWidget(QLabel("Max file size for deep text inspection (MB):"))
        self.spin_max_size = QSpinBox()
        self.spin_max_size.setRange(5, 500)
        self.spin_max_size.setValue(self.settings.get("max_file_size_mb", 100))
        layout.addWidget(self.spin_max_size)

        # -------------------------------------------------------------
        # Google AI Vision for Image Recognition (Opt-in)
        # -------------------------------------------------------------
        ai_box = QFrame()
        ai_box.setStyleSheet("background-color: #24273a; border-radius: 8px; border: 1px solid #363a4f; padding: 10px;")
        ai_layout = QVBoxLayout(ai_box)
        ai_layout.setSpacing(8)

        self.check_google_ai = QCheckBox("Enable Google AI Image Recognition (Gemini Vision)")
        self.check_google_ai.setStyleSheet("font-weight: 700; color: #8aadf4;")
        self.check_google_ai.setChecked(self.settings.get("enable_google_ai", False))
        ai_layout.addWidget(self.check_google_ai)

        ai_notice = QLabel(
            "Privacy Notice: Visual content from images will be sent to Google's Gemini API "
            "to generate descriptive filenames (e.g. photos, diagrams, screenshots). All documents remain 100% local."
        )
        ai_notice.setWordWrap(True)
        ai_notice.setStyleSheet("color: #a5adcb; font-size: 11px;")
        ai_layout.addWidget(ai_notice)

        # API Key input & Test Button
        key_label = QLabel("Google Gemini API Key:")
        key_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        ai_layout.addWidget(key_label)

        key_row = QHBoxLayout()
        self.edit_api_key = QLineEdit(self.settings.get("google_api_key", ""))
        self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_api_key.setPlaceholderText("Paste your AI Studio / Gemini API Key here (AIzaSy...)")

        self.btn_toggle_key = QPushButton("👁️")
        self.btn_toggle_key.setFixedWidth(36)
        self.btn_toggle_key.setToolTip("Show / Hide API Key")
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)

        self.btn_test_api = QPushButton("⚡ Test API Key")
        self.btn_test_api.clicked.connect(self._test_api_key)

        key_row.addWidget(self.edit_api_key)
        key_row.addWidget(self.btn_toggle_key)
        key_row.addWidget(self.btn_test_api)
        ai_layout.addLayout(key_row)

        # Model selector
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Vision Model:"))
        self.cb_ai_model = QComboBox()
        self.cb_ai_model.addItems(["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"])
        cur_model = self.settings.get("google_ai_model", "gemini-3.8-flash")
        if cur_model not in ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]:
            cur_model = "gemini-3.8-flash"
        self.cb_ai_model.setCurrentText(cur_model)
        model_row.addWidget(self.cb_ai_model)
        model_row.addStretch()
        ai_layout.addLayout(model_row)

        layout.addWidget(ai_box)

        # Export directory
        layout.addWidget(QLabel("Custom Reports Export Directory (optional):"))
        export_layout = QHBoxLayout()
        self.edit_export_dir = QLineEdit(self.settings.get("export_dir", ""))
        self.edit_export_dir.setPlaceholderText("Default app reports folder")
        btn_browse_export = QPushButton("Browse...")
        btn_browse_export.clicked.connect(self._browse_export)
        export_layout.addWidget(self.edit_export_dir)
        export_layout.addWidget(btn_browse_export)
        layout.addLayout(export_layout)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Save Settings")
        btn_save.setObjectName("primary_button")
        btn_save.clicked.connect(self._save_settings)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _toggle_key_visibility(self):
        if self.edit_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)

    def _test_api_key(self):
        key = self.edit_api_key.text().strip()
        if not key:
            QMessageBox.warning(self, "API Key Missing", "Please enter a Google Gemini API Key first.")
            return

        from src.core.ai_vision import verify_google_api_key
        model = self.cb_ai_model.currentText()
        self.btn_test_api.setEnabled(False)
        self.btn_test_api.setText("Testing...")
        success, msg = verify_google_api_key(key, model=model)
        self.btn_test_api.setEnabled(True)
        self.btn_test_api.setText("⚡ Test API Key")

        if success:
            QMessageBox.information(self, "API Key Validated", msg)
        else:
            QMessageBox.critical(self, "API Key Error", msg)

    def _browse_export(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if folder:
            self.edit_export_dir.setText(folder)

    def _save_settings(self):
        self.settings.set("naming_convention", self.cb_convention.currentText())
        self.settings.set("space_replacement", self.cb_separator.currentData())
        self.settings.set("max_filename_length", self.spin_max_len.value())
        self.settings.set("add_date_prefix", self.check_date_prefix.isChecked())
        self.settings.set("preserve_extension", self.check_preserve_ext.isChecked())
        self.settings.set("recursive", self.check_recursive.isChecked())
        self.settings.set("max_file_size_mb", self.spin_max_size.value())
        self.settings.set("enable_google_ai", self.check_google_ai.isChecked())
        self.settings.set("google_api_key", self.edit_api_key.text().strip())
        self.settings.set("google_ai_model", self.cb_ai_model.currentText())
        self.settings.set("rename_unlabelled_images", self.check_unlabelled_images.isChecked())
        self.settings.set("export_dir", self.edit_export_dir.text().strip())
        self.accept()


class UndoDialog(QDialog):
    """Allows reviewing and safely undoing previous rename sessions."""

    def __init__(self, history_manager: HistoryManager, parent=None):
        super().__init__(parent)
        self.history = history_manager
        self.selected_session_id: Optional[str] = None
        self.setWindowTitle("Undo Rename Session")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "Select a previous rename session to restore files to their original names.\n"
            "Changes are reversible only when renamed files are still available and no destination conflicts exist."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.session_list = QListWidget()
        self.session_list.currentItemChanged.connect(self._on_session_selected)
        layout.addWidget(self.session_list, 1)

        layout.addWidget(QLabel("Files in Selected Session:"))
        self.files_list = QListWidget()
        layout.addWidget(self.files_list, 2)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Close")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_undo = QPushButton("Revert Selected Session")
        self.btn_undo.setObjectName("primary_button")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_undo)
        layout.addLayout(btn_row)

        self._load_sessions()

    def _load_sessions(self):
        sessions = self.history.get_recent_sessions(limit=20)
        self.session_list.clear()

        for s in sessions:
            status_text = "Already Reverted" if s["is_reverted"] else f"Active ({s['renamed_files']} files renamed)"
            item = QListWidgetItem(f"[{s['timestamp'][:19]}] {Path(s['folder_path']).name} — {status_text}")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.session_list.addItem(item)

    def _on_session_selected(self, current: QListWidgetItem, previous=None):
        if not current:
            self.btn_undo.setEnabled(False)
            return

        session_data = current.data(Qt.ItemDataRole.UserRole)
        sess_id = session_data["session_id"]
        is_reverted = bool(session_data["is_reverted"])

        self.selected_session_id = sess_id
        records = self.history.get_session_records(sess_id)

        self.files_list.clear()
        for r in records:
            self.files_list.addItem(f"{r.new_name}  ➔  {r.original_name}  [{r.status}]")

        self.btn_undo.setEnabled(not is_reverted and session_data["renamed_files"] > 0)
