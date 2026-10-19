"""
Tests for intelligent title generation and meaningfulness heuristics.
"""

from pathlib import Path
from src.core.models import FileItem, FileStatus, ScanConfig, NamingConvention
from src.core.content_extractors import ExtractionResult
from src.core.title_generator import TitleGenerator


class TestTitleGenerator:

    def test_meaningful_title_detection(self):
        gen = TitleGenerator()
        assert gen.is_meaningful_title("CI/CD Deployment Guide")
        assert gen.is_meaningful_title("Professional Internship Report")
        assert gen.is_meaningful_title("API Authentication Module")

        # Non-meaningful rejections
        assert not gen.is_meaningful_title("")
        assert not gen.is_meaningful_title("ab")
        assert not gen.is_meaningful_title("12345")
        assert not gen.is_meaningful_title("untitled")
        assert not gen.is_meaningful_title("document")
        assert not gen.is_meaningful_title("scan")

    def test_boilerplate_cleanup(self):
        gen = TitleGenerator()
        raw = "Page 1 of 12: Quarterly Financial Review - Confidential"
        cleaned = gen.clean_candidate_title(raw)
        assert "Quarterly Financial Review" in cleaned
        assert "Page 1" not in cleaned
        assert "Confidential" not in cleaned

    def test_retains_original_name_when_no_title_found(self):
        gen = TitleGenerator()
        item = FileItem(
            original_path=Path("document_8392.pdf"),
            original_name="document_8392.pdf"
        )
        empty_res = ExtractionResult(title=None, summary="", explanation="No text found")

        new_name, status, explanation = gen.generate_proposed_filename(item, empty_res)
        assert new_name == "document_8392.pdf"
        assert status == FileStatus.UNCHANGED
        assert "retained" in explanation.lower() or "kept" in explanation.lower()

    def test_generates_descriptive_name(self):
        config = ScanConfig(root_path=Path("."), naming_convention=NamingConvention.TITLE_CASE)
        gen = TitleGenerator(config)

        item = FileItem(
            original_path=Path("doc_9912.pdf"),
            original_name="doc_9912.pdf"
        )
        res = ExtractionResult(
            title="CI CD Deployment Guide",
            summary="Deployment instructions for Docker",
            file_type="PDF Document",
            explanation="Extracted from PDF heading"
        )

        new_name, status, explanation = gen.generate_proposed_filename(item, res)
        assert new_name == "Ci_Cd_Deployment_Guide.pdf"
        assert status == FileStatus.READY_TO_RENAME
