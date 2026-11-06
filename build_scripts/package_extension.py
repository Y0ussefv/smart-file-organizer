"""
Builds the Chrome Web Store upload zip:  dist/smart-rename-<version>.zip

    python build_scripts/package_extension.py
"""

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "browser_extension"


def main() -> None:
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    if "key" in manifest:
        raise SystemExit("Remove the 'key' field from manifest.json - the Chrome Web Store rejects it.")
    out = ROOT / "dist" / f"smart-rename-{manifest['version']}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(EXT.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                z.write(f, f.relative_to(EXT).as_posix())
    print(f"Created {out}")


if __name__ == "__main__":
    main()
