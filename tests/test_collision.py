"""
Tests for filename collision resolution and deterministic suffixing.
"""

from pathlib import Path
from src.core.models import FileItem, FileStatus
from src.core.collision_handler import CollisionHandler


class TestCollisionHandler:

    def test_single_collision_adds_suffix(self, tmp_path):
        # Create an existing file on disk
        existing = tmp_path / "Report.pdf"
        existing.write_text("existing content")

        handler = CollisionHandler()
        item = FileItem(
            original_path=tmp_path / "scan_001.pdf",
            original_name="scan_001.pdf"
        )

        resolved = handler.resolve_proposed_name(item, "Report.pdf", claim=True)
        assert resolved == "Report_2.pdf"

    def test_multiple_collisions_increment_deterministic(self, tmp_path):
        existing1 = tmp_path / "Report.pdf"
        existing1.write_text("1")
        existing2 = tmp_path / "Report_2.pdf"
        existing2.write_text("2")

        handler = CollisionHandler()
        item = FileItem(
            original_path=tmp_path / "scan_002.pdf",
            original_name="scan_002.pdf"
        )

        resolved = handler.resolve_proposed_name(item, "Report.pdf", claim=True)
        assert resolved == "Report_3.pdf"

    def test_batch_collision_resolution(self, tmp_path):
        item1 = FileItem(
            original_path=tmp_path / "file1.docx",
            original_name="file1.docx",
            new_name="Project_Plan.docx"
        )
        item2 = FileItem(
            original_path=tmp_path / "file2.docx",
            original_name="file2.docx",
            new_name="Project_Plan.docx"
        )
        item3 = FileItem(
            original_path=tmp_path / "file3.docx",
            original_name="file3.docx",
            new_name="Project_Plan.docx"
        )

        handler = CollisionHandler()
        handler.resolve_batch_collisions([item1, item2, item3])

        assert item1.new_name == "Project_Plan.docx"
        assert item2.new_name == "Project_Plan_2.docx"
        assert item3.new_name == "Project_Plan_3.docx"

    def test_same_name_is_unchanged_not_collided(self, tmp_path):
        item = FileItem(
            original_path=tmp_path / "Already_Good.pdf",
            original_name="Already_Good.pdf",
            new_name="Already_Good.pdf"
        )

        handler = CollisionHandler()
        handler.resolve_batch_collisions([item])

        assert item.new_name == "Already_Good.pdf"
        assert item.status == FileStatus.UNCHANGED
