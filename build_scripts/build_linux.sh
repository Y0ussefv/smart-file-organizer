#!/usr/bin/env bash
# ==============================================================================
# Build Standalone Linux Executable / AppImage for Smart File Organizer
# ==============================================================================

set -euo pipefail

echo "[1/3] Installing dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "[2/3] Running test suite..."
python3 -m pytest tests/

echo "[3/3] Building standalone Linux binary..."
python3 -m PyInstaller --clean --noconfirm smart_file_organizer.spec

echo "=============================================================================="
echo "[SUCCESS] Standalone Linux executable built in: dist/SmartFileOrganizer"
echo "=============================================================================="
