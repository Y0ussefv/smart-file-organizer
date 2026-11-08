"""
Download Processor.

Analyzes a single freshly-downloaded file with the same engine the desktop app uses
(content extractors + AI vision + title generator), picks a safe collision-free name,
optionally sorts it into a subfolder, and renames it with full undo history.

Used by the browser native-messaging host (src/integrations/native_host.py).
"""

import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from src.core.collision_handler import CollisionHandler
from src.core.models import FileStatus
from src.core.rename_engine import RenameEngine
from src.core.scanner import DirectoryScanner
from src.core.undo_manager import UndoManager
from src.storage.history import HistoryManager
from src.storage.settings import SettingsManager
from src.utils.platform_utils import split_filename_and_ext

# Folder used for "organize by file type" mode.
TYPE_FOLDERS = {
    "Documents": {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".tex", ".epub"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".tsv", ".ods"},
    "Presentations": {".ppt", ".pptx", ".odp", ".key"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg", ".heic", ".ico"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv"},
    "Audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".tar.gz", ".tar.bz2"},
    "Installers": {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage", ".apk"},
    "Code": {".py", ".js", ".ts", ".java", ".cpp", ".c", ".cs", ".go", ".rs", ".json", ".xml", ".html", ".sql"},
    "Fonts": {".ttf", ".otf", ".woff", ".woff2"},
}

FOLDER_MODES = ("none", "site", "type")


def site_folder_name(url: Optional[str]) -> Optional[str]:
    """'https://www.github.com/x' -> 'github'.  Returns None if no usable host."""
    if not url:
        return None
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return None
    if not host or host in ("localhost",) or host.replace(".", "").isdigit():
        return None
    parts = [p for p in host.split(".") if p and p not in ("www", "m", "dl", "download", "downloads", "cdn")]
    if not parts:
        return None
    # Drop public suffix-ish tail: keep the most significant label (e.g. drive.google.com -> google)
    if len(parts) >= 2:
        # handle two-part TLDs like co.uk / com.au
        if len(parts) >= 3 and parts[-2] in ("co", "com", "net", "org", "gov", "ac", "edu"):
            name = parts[-3]
        else:
            name = parts[-2]
    else:
        name = parts[0]
    name = "".join(ch for ch in name if ch.isalnum() or ch in "-_")
    return name.capitalize() if name else None


def type_folder_name(filename: str) -> Optional[str]:
    _, ext = split_filename_and_ext(filename)
    ext = ext.lower()
    for folder, exts in TYPE_FOLDERS.items():
        if ext in exts:
            return folder
    return "Other" if ext else None


def wait_until_unlocked(path: Path, timeout: float = 8.0) -> bool:
    """Browsers / antivirus may hold the file for a moment after the download completes."""
    deadline = time.time() + timeout
    last_size = -1
    while time.time() < deadline:
        try:
            size = path.stat().st_size
            with open(path, "ab"):
                pass
            if size == last_size:
                return True
            last_size = size
        except (PermissionError, OSError):
            pass
        time.sleep(0.4)
    return path.exists()


class DownloadProcessor:
    """Runs the Smart File Organizer pipeline on one downloaded file."""

    def __init__(
        self,
        settings: Optional[SettingsManager] = None,
        history: Optional[HistoryManager] = None,
    ):
        self.settings = settings or SettingsManager()
        self.history = history or HistoryManager()

    def process(
        self,
        file_path: str,
        source_url: Optional[str] = None,
        folder_mode: str = "none",
        dry_run: bool = False,
        add_date_prefix: Optional[bool] = None,
        date_prefix_format: Optional[str] = None,
        date_prefix_separator: Optional[str] = None,
    ) -> Dict[str, Any]:
        path = Path(file_path)
        base: Dict[str, Any] = {
            "original_path": str(path),
            "original_name": path.name,
            "new_path": str(path),
            "new_name": path.name,
            "renamed": False,
            "session_id": None,
        }

        if not path.is_file():
            return {**base, "status": "ERROR", "message": "File not found on disk."}

        wait_until_unlocked(path)

        config = self.settings.get_scan_config(path.parent)
        config.recursive = False
        config.group_by_domain = False  # single file: domain grouping needs a batch
        if add_date_prefix is not None:
            config.add_date_prefix = bool(add_date_prefix)
        if date_prefix_format:
            config.date_prefix_format = date_prefix_format
        if date_prefix_separator is not None:
            config.date_prefix_separator = date_prefix_separator

        max_bytes = int(config.max_file_size_mb or 0) * 1024 * 1024
        try:
            if max_bytes and path.stat().st_size > max_bytes:
                return {**base, "status": "SKIPPED",
                        "message": f"Larger than {config.max_file_size_mb} MB limit; left unchanged."}
        except OSError as e:
            return {**base, "status": "ERROR", "message": str(e)}

        scanner = DirectoryScanner(config)
        item = scanner.analyze_file(path)
        base["detected_title"] = item.detected_title
        base["file_type"] = item.file_type

        if item.status == FileStatus.ERROR:
            return {**base, "status": "ERROR", "message": item.explanation or item.error_message}

        # Optional subfolder
        folder_mode = folder_mode if folder_mode in FOLDER_MODES else "none"
        subfolder = None
        if folder_mode == "site":
            subfolder = site_folder_name(source_url)
        elif folder_mode == "type":
            subfolder = type_folder_name(item.new_name or item.original_name)
        if subfolder and subfolder.lower() == path.parent.name.lower():
            subfolder = None  # already inside that folder
        item.target_subfolder = subfolder

        if not item.new_name:
            item.new_name = item.original_name

        if item.status != FileStatus.READY_TO_RENAME and not subfolder:
            return {**base, "status": "UNCHANGED",
                    "message": item.explanation or "No better name found; kept original."}

        # Collision-free final name (never overwrites)
        collisions = CollisionHandler()
        collisions.register_batch_item(item)
        item.new_name = collisions.resolve_proposed_name(item, item.new_name, claim=True)
        dest_dir = path.parent / subfolder if subfolder else path.parent
        item.new_path = dest_dir / item.new_name
        item.status = FileStatus.READY_TO_RENAME
        item.is_selected = True

        planned = {
            **base,
            "new_name": item.new_name,
            "new_path": str(item.new_path),
            "subfolder": subfolder,
            "explanation": item.explanation,
        }
        if dry_run:
            return {**planned, "status": "PREVIEW", "message": "Dry run - nothing changed."}

        session_id = str(uuid.uuid4())
        records = RenameEngine(self.history).execute_renames([item], session_id=session_id)
        record = records[0] if records else None

        if record and record.status == "RENAMED":
            return {**planned, "status": "RENAMED", "renamed": True, "session_id": session_id,
                    "message": item.explanation}

        return {**base, "status": "ERROR",
                "message": (record.error if record else None) or item.explanation or "Rename failed."}

    def undo(self, session_id: str) -> Dict[str, Any]:
        result = UndoManager(self.history).undo_session(session_id)
        first = result.results[0] if result.results else None
        return {
            "status": "REVERTED" if result.reverted_items else "ERROR",
            "reverted": result.reverted_items,
            "failed": result.failed_items,
            "restored_path": str(first.original_path) if first and first.success else None,
            "message": first.message if first else "Nothing to undo.",
        }
