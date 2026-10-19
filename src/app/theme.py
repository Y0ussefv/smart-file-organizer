"""
Modern UI Themes and Stylesheets for Smart File Organizer.
Provides polished Dark and Light modes with modern typography, glassmorphism hints,
vibrant accents, and status badge styling.
"""

DARK_THEME_QSS = """
/* Global Dark Theme */
QWidget {
    background-color: #181926;
    color: #cad3f5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: #5b6078;
    selection-color: #ffffff;
}

/* Main Window */
QMainWindow {
    background-color: #181926;
}

/* Top Dashboard Container */
#dashboard_frame {
    background-color: #1e2030;
    border-radius: 10px;
    border: 1px solid #363a4f;
    padding: 14px;
}

/* Card Widgets */
.StatCard {
    background-color: #24273a;
    border-radius: 8px;
    border: 1px solid #363a4f;
    padding: 10px 14px;
}
.StatCard:hover {
    border-color: #8aadf4;
}

/* Labels */
QLabel {
    color: #cad3f5;
    background: transparent;
}
QLabel#title_label {
    font-size: 20px;
    font-weight: 700;
    color: #8aadf4;
}
QLabel#subtitle_label {
    font-size: 12px;
    color: #a5adcb;
}
QLabel#card_number {
    font-size: 22px;
    font-weight: 700;
    color: #f4dbd6;
}
QLabel#card_title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: #939ab7;
}

/* Buttons */
QPushButton {
    background-color: #363a4f;
    color: #cad3f5;
    border: 1px solid #494d64;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    min-height: 18px;
}
QPushButton:hover {
    background-color: #494d64;
    border-color: #5b6078;
}
QPushButton:pressed {
    background-color: #24273a;
}
QPushButton:disabled {
    background-color: #1e2030;
    color: #6e738d;
    border-color: #24273a;
}

/* Primary Accent Button */
QPushButton#primary_button {
    background-color: #8aadf4;
    color: #181926;
    border: 1px solid #7dc4e4;
    font-weight: 700;
}
QPushButton#primary_button:hover {
    background-color: #91d7e3;
    border-color: #8aadf4;
}
QPushButton#primary_button:pressed {
    background-color: #7dc4e4;
}

/* Action Success Button (Rename) */
QPushButton#rename_button {
    background-color: #a6da95;
    color: #181926;
    border: 1px solid #8bd5ca;
    font-weight: 700;
}
QPushButton#rename_button:hover {
    background-color: #8bd5ca;
}
QPushButton#rename_button:disabled {
    background-color: #24273a;
    color: #6e738d;
    border-color: #363a4f;
}

/* Danger / Cancel Button */
QPushButton#cancel_button {
    background-color: #ed8796;
    color: #181926;
    border: 1px solid #ee99a0;
    font-weight: 700;
}
QPushButton#cancel_button:hover {
    background-color: #ee99a0;
}

/* Inputs & ComboBoxes */
QLineEdit {
    background-color: #24273a;
    color: #cad3f5;
    border: 1px solid #363a4f;
    border-radius: 6px;
    padding: 7px 10px;
}
QLineEdit:focus {
    border: 1px solid #8aadf4;
}

QComboBox {
    background-color: #24273a;
    color: #cad3f5;
    border: 1px solid #363a4f;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 18px;
}
QComboBox:hover {
    border-color: #5b6078;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #363a4f;
}
QComboBox QAbstractItemView {
    background-color: #24273a;
    border: 1px solid #363a4f;
    selection-background-color: #494d64;
    color: #cad3f5;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #cad3f5;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #494d64;
    border-radius: 4px;
    background-color: #24273a;
}
QCheckBox::indicator:hover {
    border-color: #8aadf4;
}
QCheckBox::indicator:checked {
    background-color: #8aadf4;
    border-color: #8aadf4;
}

/* Table Widget */
QTableWidget {
    background-color: #1e2030;
    border: 1px solid #363a4f;
    border-radius: 8px;
    gridline-color: #24273a;
    alternate-background-color: #222538;
}
QTableWidget::item {
    padding: 6px;
    border-bottom: 1px solid #24273a;
}
QTableWidget::item:selected {
    background-color: #363a4f;
    color: #ffffff;
}

/* Table Header */
QHeaderView::section {
    background-color: #24273a;
    color: #a5adcb;
    font-weight: 700;
    font-size: 12px;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #363a4f;
    border-right: 1px solid #363a4f;
}

/* Progress Bar */
QProgressBar {
    background-color: #24273a;
    border: 1px solid #363a4f;
    border-radius: 6px;
    text-align: center;
    color: #cad3f5;
    font-weight: 600;
    height: 16px;
}
QProgressBar::chunk {
    background-color: #8aadf4;
    border-radius: 5px;
}

/* Text Logs */
QPlainTextEdit, QTextEdit {
    background-color: #1e2030;
    color: #a5adcb;
    border: 1px solid #363a4f;
    border-radius: 6px;
    font-family: "Cascadia Code", Consolas, "Courier New", monospace;
    font-size: 12px;
    padding: 8px;
}

/* Scroll Bars */
QScrollBar:vertical {
    border: none;
    background-color: #1e2030;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #363a4f;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #5b6078;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Tab & Status Bar */
QStatusBar {
    background-color: #181926;
    border-top: 1px solid #363a4f;
    color: #939ab7;
    font-size: 12px;
}
"""

LIGHT_THEME_QSS = """
/* Global Light Theme */
QWidget {
    background-color: #f4f5f8;
    color: #2b3040;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: #d1d5db;
    selection-color: #111827;
}

QMainWindow {
    background-color: #f4f5f8;
}

#dashboard_frame {
    background-color: #ffffff;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    padding: 14px;
}

.StatCard {
    background-color: #ffffff;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    padding: 10px 14px;
}
.StatCard:hover {
    border-color: #3b82f6;
}

QLabel {
    color: #2b3040;
    background: transparent;
}
QLabel#title_label {
    font-size: 20px;
    font-weight: 700;
    color: #2563eb;
}
QLabel#subtitle_label {
    font-size: 12px;
    color: #64748b;
}
QLabel#card_number {
    font-size: 22px;
    font-weight: 700;
    color: #1e293b;
}
QLabel#card_title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: #64748b;
}

QPushButton {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    min-height: 18px;
}
QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
}
QPushButton:pressed {
    background-color: #e2e8f0;
}
QPushButton:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton#primary_button {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
    font-weight: 700;
}
QPushButton#primary_button:hover {
    background-color: #1d4ed8;
}

QPushButton#rename_button {
    background-color: #16a34a;
    color: #ffffff;
    border: 1px solid #15803d;
    font-weight: 700;
}
QPushButton#rename_button:hover {
    background-color: #15803d;
}
QPushButton#rename_button:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #cbd5e1;
}

QPushButton#cancel_button {
    background-color: #ef4444;
    color: #ffffff;
    border: 1px solid #dc2626;
    font-weight: 700;
}
QPushButton#cancel_button:hover {
    background-color: #dc2626;
}

QLineEdit {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 10px;
}
QLineEdit:focus {
    border: 1px solid #2563eb;
}

QComboBox {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 18px;
}
QComboBox:hover {
    border-color: #94a3b8;
}

QCheckBox {
    spacing: 8px;
    color: #1e293b;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #f1f5f9;
    alternate-background-color: #f8fafc;
}
QTableWidget::item {
    padding: 6px;
    border-bottom: 1px solid #e2e8f0;
}
QTableWidget::item:selected {
    background-color: #e0e7ff;
    color: #1e293b;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 700;
    font-size: 12px;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
}

QProgressBar {
    background-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    text-align: center;
    color: #1e293b;
    font-weight: 600;
    height: 16px;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 5px;
}

QPlainTextEdit, QTextEdit {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    font-family: "Cascadia Code", Consolas, "Courier New", monospace;
    font-size: 12px;
    padding: 8px;
}

QStatusBar {
    background-color: #f8fafc;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 12px;
}
"""


def get_status_badge_style(status_value: str, is_dark: bool = True) -> tuple[str, str]:
    """
    Returns (background_color, text_color) for pill badges.
    """
    if status_value == "READY_TO_RENAME":
        return ("#1e3a2f", "#a6da95") if is_dark else ("#dcfce7", "#15803d")
    elif status_value == "RENAMED":
        return ("#18392b", "#8bd5ca") if is_dark else ("#d1fae5", "#065f46")
    elif status_value == "UNCHANGED":
        return ("#2a2b3d", "#a5adcb") if is_dark else ("#f1f5f9", "#64748b")
    elif status_value == "SKIPPED":
        return ("#3b3323", "#eed49f") if is_dark else ("#fef3c7", "#b45309")
    elif status_value == "ERROR":
        return ("#3d2127", "#ed8796") if is_dark else ("#fee2e2", "#b91c1c")
    elif status_value == "REVERTED":
        return ("#1e2d42", "#8aadf4") if is_dark else ("#dbeafe", "#1d4ed8")
    return ("#24273a", "#cad3f5") if is_dark else ("#f3f4f6", "#374151")
