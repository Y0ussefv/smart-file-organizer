"""
Safe Renaming Engine for Smart File Organizer.
Executes atomic file renames with collision avoidance, post-rename verification,
per-file error isolation, and audit history logging.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from src.core.models import FileItem, FileStatus, RenameHistoryRecord
from src.core.scanner import compute_sha256
from src.storage.history import HistoryManager
from src.utils.platform_utils import is_safe_path


class RenameEngine:
    """Performs validated, atomic file renames on selected files."""

    def __init__(self, history_manager: Optional[HistoryManager] = None):
        self.history_manager = history_manager or HistoryManager()
        self._is_cancelled = False

    def cancel(self) -> None:
        """Flags the rename process to cancel."""
        self._is_cancelled = True

    def execute_renames(
        self,
        items: List[FileItem],
        session_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        item_callback: Optional[Callable[[FileItem], None]] = None,
    ) -> List[RenameHistoryRecord]:
        """
        Executes renaming for all selected items.
        Returns list of RenameHistoryRecord entries for auditing and undo.
        """
        self._is_cancelled = False
        sess_id = session_id or str(uuid.uuid4())
        records: List[RenameHistoryRecord] = []

        # Filter items that are actually eligible to be renamed
        eligible_items = [
            item for item in items
            if item.is_selected and item.status == FileStatus.READY_TO_RENAME and item.new_name and item.new_name != item.original_name
        ]

        total_eligible = len(eligible_items)

        for idx, item in enumerate(eligible_items, 1):
            if self._is_cancelled:
                break

            if progress_callback:
                progress_callback(idx, total_eligible, f"Renaming {item.original_name} -> {item.new_name}")

            record = self._rename_single_file(item, sess_id)
            records.append(record)

            if item_callback:
                item_callback(item)

        # Update items that were unselected or unchanged
        for item in items:
            if not item.is_selected and item.status == FileStatus.READY_TO_RENAME:
                item.status = FileStatus.SKIPPED
                item.explanation = "Skipped by user selection."

        # Commit session to history database
        if records:
            folder_str = str(eligible_items[0].original_path.parent) if eligible_items else ""
            self.history_manager.record_session(sess_id, folder_str, total_eligible, records)

        return records

    def _rename_single_file(self, item: FileItem, session_id: str) -> RenameHistoryRecord:
        """Safely renames a single file with rigorous pre- and post-checks."""
        now_iso = datetime.now().isoformat()
        orig_path = item.original_path
        target_path = item.original_path.parent / item.new_name

        record = RenameHistoryRecord(
            session_id=session_id,
            timestamp=now_iso,
            original_path=str(orig_path),
            new_path=str(target_path),
            original_name=item.original_name,
            new_name=item.new_name,
            file_size=item.file_size,
            status="RENAMED",
        )

        # Pre-check 1: Original file must still exist
        if not orig_path.exists():
            item.status = FileStatus.ERROR
            item.error_message = "Original file not found"
            item.explanation = "Source file no longer exists on disk."
            record.status = "ERROR"
            record.error = item.error_message
            return record

        # Pre-check 2: Target path must not escape or be unsafe
        if not is_safe_path(target_path, orig_path.parent):
            item.status = FileStatus.ERROR
            item.error_message = "Unsafe destination path"
            item.explanation = "Operation prevented: Target path is unsafe or attempts path traversal."
            record.status = "ERROR"
            record.error = item.error_message
            return record

        # Pre-check 3: Target path must NOT already exist (never overwrite!)
        if target_path.exists():
            # Check if it's the exact same file (case change on case-insensitive filesystems)
            if target_path.resolve() != orig_path.resolve():
                item.status = FileStatus.ERROR
                item.error_message = "Destination already exists"
                item.explanation = f"Destination '{item.new_name}' already exists. Overwrite strictly prevented."
                record.status = "ERROR"
                record.error = item.error_message
                return record

        # Compute SHA-256 before rename for verification and auditing
        file_hash = compute_sha256(orig_path)
        item.sha256 = file_hash
        record.sha256 = file_hash

        # Perform atomic rename
        try:
            # os.replace or rename
            orig_path.rename(target_path)
        except (PermissionError, OSError) as e:
            item.status = FileStatus.ERROR
            item.error_message = str(e)
            item.explanation = f"Failed to rename: File may be locked, open in another program, or lack write permission. ({str(e)})"
            record.status = "ERROR"
            record.error = str(e)
            return record

        # Post-rename verification
        if not target_path.exists():
            item.status = FileStatus.ERROR
            item.error_message = "Post-rename verification failed"
            item.explanation = "Verification error: Renamed file does not exist at destination."
            record.status = "ERROR"
            record.error = item.error_message
            return record

        # Verify file size matches
        try:
            new_size = target_path.stat().st_size
            if new_size != item.file_size:
                item.status = FileStatus.ERROR
                item.error_message = "Size mismatch after rename"
                item.explanation = f"Integrity warning: Target file size ({new_size}) differs from original ({item.file_size})."
                record.status = "ERROR"
                record.error = item.error_message
                return record
        except Exception:
            pass

        # Success!
        item.status = FileStatus.RENAMED
        item.new_path = target_path
        item.explanation = f"Successfully renamed from '{item.original_name}' to '{item.new_name}'."
        record.status = "RENAMED"

        return record
