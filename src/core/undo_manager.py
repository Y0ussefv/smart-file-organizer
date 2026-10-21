"""
Undo Manager for Smart File Organizer.
Validates and safely reverses previous file rename operations using historical audit records.
Ensures no destination files are overwritten and verifies files before reverting.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from src.core.models import RenameHistoryRecord
from src.storage.history import HistoryManager


@dataclass
class UndoResultItem:
    original_path: Path
    renamed_path: Path
    success: bool
    message: str


@dataclass
class UndoSessionResult:
    session_id: str
    total_items: int
    reverted_items: int
    failed_items: int
    results: List[UndoResultItem]


class UndoManager:
    """Manages the safe reversal of previously applied rename sessions."""

    def __init__(self, history_manager: Optional[HistoryManager] = None):
        self.history_manager = history_manager or HistoryManager()

    def get_last_undoable_session_id(self) -> Optional[str]:
        """Returns the ID of the latest session eligible for undo."""
        return self.history_manager.get_last_active_session_id()

    def undo_session(
        self,
        session_id: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> UndoSessionResult:
        """
        Reverses all renamed files in a session back to their original names.
        Strictly enforces that the renamed file must exist and the original destination must NOT be occupied.
        """
        records = self.history_manager.get_session_records(session_id)
        # Only process successfully renamed records
        renamed_records = [r for r in records if r.status == "RENAMED"]

        total = len(renamed_records)
        reverted_count = 0
        failed_count = 0
        results: List[UndoResultItem] = []

        for idx, rec in enumerate(renamed_records, 1):
            cur_path = Path(rec.new_path)
            orig_path = Path(rec.original_path)

            if progress_callback:
                progress_callback(idx, total, f"Reverting {cur_path.name} -> {orig_path.name}")

            # Verification 1: Current file (new_path) must exist
            if not cur_path.exists():
                failed_count += 1
                results.append(UndoResultItem(
                    original_path=orig_path,
                    renamed_path=cur_path,
                    success=False,
                    message=f"Current file '{cur_path.name}' no longer exists on disk."
                ))
                continue

            # Verification 2: Original destination must NOT be occupied
            if orig_path.exists() and orig_path.resolve() != cur_path.resolve():
                failed_count += 1
                results.append(UndoResultItem(
                    original_path=orig_path,
                    renamed_path=cur_path,
                    success=False,
                    message=f"Original location '{orig_path.name}' is already occupied. Overwrite strictly prevented."
                ))
                continue

            # Perform safe revert
            try:
                import shutil
                shutil.move(str(cur_path), str(orig_path))
                reverted_count += 1
                # Clean up empty subfolder if it was created for domain grouping
                if cur_path.parent != orig_path.parent and cur_path.parent.exists():
                    try:
                        cur_path.parent.rmdir()
                    except OSError:
                        pass
                results.append(UndoResultItem(
                    original_path=orig_path,
                    renamed_path=cur_path,
                    success=True,
                    message=f"Successfully restored to '{orig_path.name}'."
                ))
            except Exception as e:
                failed_count += 1
                results.append(UndoResultItem(
                    original_path=orig_path,
                    renamed_path=cur_path,
                    success=False,
                    message=f"System error while restoring: {str(e)}"
                ))

        # Mark session as reverted in history database
        self.history_manager.mark_session_reverted(session_id)

        return UndoSessionResult(
            session_id=session_id,
            total_items=total,
            reverted_items=reverted_count,
            failed_items=failed_count,
            results=results
        )
