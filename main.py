"""
Convenience launcher for Smart File Organizer.

    python main.py                              # desktop app
    python main.py --install-browser-bridge     # connect the Chrome/Edge extension
    python main.py --uninstall-browser-bridge
    python main.py --native-host                # (used by the browser itself)
"""

import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--install-browser-bridge" in args or "--uninstall-browser-bridge" in args:
        from src.integrations.install_native_host import main as bridge_main
        sys.exit(bridge_main(args))
    if "--native-host" in args:
        from src.integrations.native_host import main as host_main
        host_main()
        sys.exit(0)

    from src.main import main
    main()
