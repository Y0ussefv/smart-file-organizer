# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for Smart File Organizer.
Produces a self-contained, standalone executable for Windows, macOS, or Linux.
"""

from pathlib import Path
import sys

block_cipher = None
project_root = Path.cwd().resolve()

a = Analysis(
    [str(project_root / 'src' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'src' / 'app' / 'assets'), 'src/app/assets'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'pypdf',
        'docx',
        'openpyxl',
        'pptx',
        'PIL',
        'PIL.Image',
        'PIL.ExifTags',
        'imageio',
        'imageio.v3',
        'imageio_ffmpeg',
        'requests',
        'sqlite3',
        'csv',
        'json',
        'xml',
        'src.core.models',
        'src.core.domain_matcher',
        'src.core.ai_vision',
        'src.core.scanner',
        'src.core.rename_engine',
        'src.core.undo_manager',
        'src.core.collision_handler',
        'src.core.content_extractors',
        'src.core.file_classifier',
        'src.core.filename_sanitizer',
        'src.core.title_generator',
        'src.storage.settings',
        'src.storage.history',
        'src.reports.report_manager',
        'src.reports.csv_report',
        'src.reports.txt_report',
        'src.reports.json_report',
        'src.app.main_window',
        'src.app.dialogs',
        'src.app.theme',
        'src.app.widgets.preview_table',
        'src.app.widgets.stats_widget',
        'src.utils.platform_utils',
        'src.utils.logging_config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'notebook',
        'scipy',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

icon_ico = str(project_root / 'src' / 'app' / 'assets' / 'icon.ico')
icon_png = str(project_root / 'src' / 'app' / 'assets' / 'icon.png')
selected_icon = icon_ico if (project_root / 'src' / 'app' / 'assets' / 'icon.ico').exists() else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SmartFileOrganizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=selected_icon,
)

# macOS Application Bundle (.app)
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='SmartFileOrganizer.app',
        icon=icon_png,
        bundle_identifier='com.rnj.smartfileorganizer',
        info_plist={
            'CFBundleName': 'Smart File Organizer',
            'CFBundleDisplayName': 'Smart File Organizer',
            'CFBundleGetInfoString': "Intelligent Content-Aware File Organizer & Renamer",
            'CFBundleIdentifier': "com.rnj.smartfileorganizer",
            'CFBundleVersion': "1.2.0",
            'CFBundleShortVersionString': "1.2.0",
            'NSHumanReadableCopyright': "Copyright © 2026",
            'NSHighResolutionCapable': True,
        }
    )
