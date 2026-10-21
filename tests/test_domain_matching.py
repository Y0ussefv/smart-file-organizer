"""
Unit and integration tests for Domain Matching and Folder Organization.
Tests user example:
  logo delfa
  pdf delfa
  -> create folder named delfa and organize both files into it!
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

from src.core.models import FileItem, FileStatus, ScanConfig, NamingConvention
from src.core.domain_matcher import DomainMatcher
from src.core.scanner import DirectoryScanner
from src.core.rename_engine import RenameEngine
from src.core.undo_manager import UndoManager
from src.storage.history import HistoryManager


class TestDomainMatching:

    def test_domain_candidate_extraction(self):
        item = FileItem(
            original_path=Path("logo delfa.png"),
            original_name="logo delfa.png",
            original_stem="logo delfa",
            original_ext=".png",
            new_name="Logo_Delfa.png"
        )
        cands = DomainMatcher.find_file_domain_candidates(item)
        assert any(c.lower() == "delfa" for c in cands)

    def test_exact_user_example_logo_and_pdf_delfa(self, tmp_path):
        """
        User scenario:
        logo delfa
        pdf delfa
        create folder named delfa and put the logo and the pdf into it.
        """
        # Create the sample files
        logo_file = tmp_path / "logo delfa.png"
        img = Image.new("RGB", (64, 64), color="blue")
        img.save(str(logo_file))

        pdf_file = tmp_path / "pdf delfa.pdf"
        # Write minimal valid PDF header
        pdf_file.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n102\n%%EOF\n")

        # Configure scan
        config = ScanConfig(
            root_path=tmp_path,
            group_by_domain=True,
            min_domain_files=2
        )
        scanner = DirectoryScanner(config)
        items, summary = scanner.scan()

        # Both files should be found
        assert len(items) == 2

        logo_item = next(i for i in items if "logo" in i.original_name.lower())
        pdf_item = next(i for i in items if "pdf" in i.original_name.lower())

        # Domain detected should be 'delfa'
        assert logo_item.domain is not None
        assert logo_item.domain.lower() == "delfa"
        assert pdf_item.domain is not None
        assert pdf_item.domain.lower() == "delfa"

        # Target subfolder should be 'Delfa' or 'delfa'
        assert logo_item.target_subfolder.lower() == "delfa"
        assert pdf_item.target_subfolder.lower() == "delfa"

        # Both items should be selected and ready to rename/move
        assert logo_item.is_selected is True
        assert pdf_item.is_selected is True
        assert logo_item.status == FileStatus.READY_TO_RENAME
        assert pdf_item.status == FileStatus.READY_TO_RENAME

        # Verify execution moves files into the 'delfa' directory
        history_mgr = HistoryManager(db_path=tmp_path / "history.db")
        engine = RenameEngine(history_manager=history_mgr)
        records = engine.execute_renames(items)

        assert len(records) == 2
        domain_dir = tmp_path / logo_item.target_subfolder
        assert domain_dir.exists()
        assert domain_dir.is_dir()

        # Files must be inside the domain folder
        moved_logo = domain_dir / logo_item.new_name
        moved_pdf = domain_dir / pdf_item.new_name
        assert moved_logo.exists()
        assert moved_pdf.exists()

        # Original files should no longer exist at root
        assert not logo_file.exists()
        assert not pdf_file.exists()

        # Test Undo restores the files and removes the domain folder
        undo_mgr = UndoManager(history_manager=history_mgr)
        undo_res = undo_mgr.undo_session(records[0].session_id)

        assert undo_res.reverted_items == 2
        assert logo_file.exists()
        assert pdf_file.exists()
        assert not domain_dir.exists()  # Empty domain folder was safely cleaned up!

    def test_single_file_does_not_create_domain_folder(self, tmp_path):
        """Files without matching peers should not create single-file domain folders."""
        f1 = tmp_path / "unique_notes.txt"
        f1.write_text("Hello world")
        f2 = tmp_path / "other_document.txt"
        f2.write_text("Second content")

        config = ScanConfig(root_path=tmp_path, group_by_domain=True, min_domain_files=2)
        scanner = DirectoryScanner(config)
        items, summary = scanner.scan()

        for item in items:
            assert item.target_subfolder is None
