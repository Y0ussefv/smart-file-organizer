"""
Packages the BeeOrganizer browser extension.

    python build_scripts/package_extension.py           # private zip to share: dist/BeeOrganizer.zip
    python build_scripts/package_extension.py --store   # Chrome Web Store upload zip

The private zip unpacks into a "BeeOrganizer" folder with INSTALL.txt inside,
ready for "Load unpacked" in chrome://extensions.
"""

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "browser_extension"


def main(argv) -> None:
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    store = "--store" in argv
    if store and "key" in manifest:
        raise SystemExit("Remove the 'key' field from manifest.json - the Chrome Web Store rejects it.")

    if store:
        out = ROOT / "dist" / f"BeeOrganizer-store-{manifest['version']}.zip"
        prefix = ""
    else:
        out = ROOT / "dist" / "BeeOrganizer.zip"
        prefix = "BeeOrganizer/"

    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(EXT.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                z.write(f, prefix + f.relative_to(EXT).as_posix())
    print(f"Created {out}  (version {manifest['version']})")


if __name__ == "__main__":
    main(sys.argv[1:])
