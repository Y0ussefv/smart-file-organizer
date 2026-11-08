#!/usr/bin/env bash
# ==============================================================================
# Build Standalone macOS Application Bundle (.app) for Smart File Organizer
# ==============================================================================

set -euo pipefail

echo "[1/3] Installing dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "[2/3] Running test suite..."
python3 -m pytest tests/

echo "[3/3] Building standalone macOS application..."
python3 -m PyInstaller --clean --noconfirm smart_file_organizer.spec

if [ -d "dist/BeeOrganizer.app" ]; then
    echo "=============================================================================="
    echo "[SUCCESS] macOS application bundle built in: dist/BeeOrganizer.app"
    echo "=============================================================================="

    # Automatically create .dmg installer disk image if hdiutil is present
    if command -v hdiutil &>/dev/null; then
        echo "Creating macOS DMG installer..."
        hdiutil create -volname "BeeOrganizer" -srcfolder dist/BeeOrganizer.app -ov -format UDZO dist/BeeOrganizer-Installer.dmg
        echo "[SUCCESS] macOS DMG installer created: dist/BeeOrganizer-Installer.dmg"
    fi
else
    echo "[ERROR] Build failed. dist/BeeOrganizer.app not found."
    exit 1
fi
