"""
Tests for RenameEngine, safety verification, and UndoManager session reversal.
"""

from pathlib import Path
from src.core.models import FileItem, FileStatus
from src.core.rename_engine import RenameEngine
from src.core.undo_manager import UndoManager
from src.storage.history import HistoryManager


class TestRenameAndUndo:

    def test_successful_rename_and_undo(self, tmp_path):
        history_db = tmp_path / "test_history.sqlite3"
        history_mgr = HistoryManager(history_db)

        # Create sample files
        f1 = tmp_path / "doc_1.txt"
        f1.write_text("Alpha content")
        f2 = tmp_path / "doc_2.txt"
        f2.write_text("Beta content")

        item1 = FileItem(
            original_path=f1,
            original_name="doc_1.txt",
            new_name="Alpha_Project_Notes.txt",
            file_size=len("Alpha content"),
            status=FileStatus.READY_TO_RENAME,
            is_selected=True
        )
        item2 = FileItem(
            original_path=f2,
            original_name="doc_2.txt",
            new_name="Beta_Release_Checklist.txt",
            file_size=len("Beta content"),
            status=FileStatus.READY_TO_RENAME,
            is_selected=True
        )

        engine = RenameEngine(history_mgr)
        records = engine.execute_renames([item1, item2], session_id="test_sess_01")

        assert len(records) == 2
        assert all(r.status == "RENAMED" for r in records)
        assert item1.status == FileStatus.RENAMED
        assert item2.status == FileStatus.RENAMED

        # Verify filesystem reflects the change
        assert not f1.exists()
        assert not f2.exists()
        new_f1 = tmp_path / "Alpha_Project_Notes.txt"
        new_f2 = tmp_path / "Beta_Release_Checklist.txt"
        assert new_f1.exists()
        assert new_f2.exists()

        # Now test UndoManager
        undo_mgr = UndoManager(history_mgr)
        undo_result = undo_mgr.undo_session("test_sess_01")

        assert undo_result.reverted_items == 2
        assert undo_result.failed_items == 0

        # Verify filesystem is restored
        assert f1.exists()
        assert f2.exists()
        assert not new_f1.exists()
        assert not new_f2.exists()

    def test_never_overwrites_existing_file(self, tmp_path):
        history_db = tmp_path / "test_history.sqlite3"
        history_mgr = HistoryManager(history_db)

        source = tmp_path / "file1.txt"
        source.write_text("Source data")

        # Destination already exists with different data
        dest = tmp_path / "Target.txt"
        dest.write_text("Important existing data")

        item = FileItem(
            original_path=source,
            original_name="file1.txt",
            new_name="Target.txt",
            file_size=source.stat().st_size,
            status=FileStatus.READY_TO_RENAME,
            is_selected=True
        )

        engine = RenameEngine(history_mgr)
        records = engine.execute_renames([item])

        assert records[0].status == "ERROR"
        assert item.status == FileStatus.ERROR
        assert "already exists" in item.error_message.lower()

        # Target file content must be completely untouched
        assert dest.read_text() == "Important existing data"
        assert source.exists()

    def test_undo_refuses_to_overwrite_occupied_destination(self, tmp_path):
        history_db = tmp_path / "test_history.sqlite3"
        history_mgr = HistoryManager(history_db)

        f1 = tmp_path / "draft.txt"
        f1.write_text("Original Draft")

        item = FileItem(
            original_path=f1,
            original_name="draft.txt",
            new_name="Final_Document.txt",
            file_size=f1.stat().st_size,
            status=FileStatus.READY_TO_RENAME,
            is_selected=True
        )

        engine = RenameEngine(history_mgr)
        engine.execute_renames([item], session_id="sess_conflict")

        renamed_file = tmp_path / "Final_Document.txt"
        assert renamed_file.exists()

        # Re-create a file at the original path
        f1.write_text("New independent file that shouldn't be overwritten")

        # Attempt undo
        undo_mgr = UndoManager(history_mgr)
        res = undo_mgr.undo_session("sess_conflict")

        assert res.failed_items == 1
        assert res.reverted_items == 0
        assert f1.read_text() == "New independent file that shouldn't be overwritten"
        assert renamed_file.exists()
