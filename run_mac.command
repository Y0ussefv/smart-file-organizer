#!/bin/bash
# ==============================================================================
# One-Click macOS Launcher for Smart File Organizer
# Double-click this file in macOS Finder to run the application instantly!
# ==============================================================================

cd "$(dirname "$0")"

echo "=============================================================================="
echo " Starting Smart File Organizer..."
echo "=============================================================================="

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 is required but not found on your Mac."
    echo "Please install Python 3 from https://www.python.org/downloads/mac-osx/ or via 'brew install python'."
    read -p "Press Enter to exit..."
    exit 1
fi

# Ensure virtual environment exists
if [ ! -d "venv" ]; then
    echo "Setting up environment for first run (this only takes a moment)..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Launch application
python3 src/main.py
