"""
Convenience launcher for Smart File Organizer / BeeOrganizer.

    python main.py                              # window + background Downloads watcher
    python main.py --watch                      # background watcher only (start-up mode)
    python main.py --no-watch                   # window only
"""

import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.main import main

if __name__ == "__main__":
    main()
