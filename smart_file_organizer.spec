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
    datas=[],
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
        'sqlite3',
        'csv',
        'json',
        'xml',
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
)
