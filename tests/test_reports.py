"""
Tests for CSV, TXT, and JSON report generation.
"""

from datetime import datetime
from pathlib import Path
import json
import csv

from src.core.models import FileItem, FileStatus, ScanConfig, ScanSummary
from src.reports.csv_report import generate_csv_report
from src.reports.txt_report import generate_txt_report
from src.reports.json_report import generate_json_report
from src.reports.report_manager import ReportManager


class TestReports:

    def _sample_data(self, tmp_path):
        item1 = FileItem(
            original_path=tmp_path / "raw1.pdf",
            original_name="raw1.pdf",
            new_name="CI_CD_Guide.pdf",
            new_path=tmp_path / "CI_CD_Guide.pdf",
            file_type="PDF Document",
            file_size=2048,
            sha256="abc123456",
            status=FileStatus.RENAMED,
            explanation="Extracted from PDF title"
        )
        item2 = FileItem(
            original_path=tmp_path / "img.jpg",
            original_name="img.jpg",
            new_name="img.jpg",
            file_type="JPEG Image",
            file_size=4096,
            status=FileStatus.UNCHANGED,
            explanation="No descriptive text found"
        )
        config = ScanConfig(root_path=tmp_path)
        summary = ScanSummary(total_files=2, renamed=1, unchanged=1)
        return [item1, item2], config, summary

    def test_csv_report(self, tmp_path):
        items, _, _ = self._sample_data(tmp_path)
        csv_out = tmp_path / "report.csv"
        generate_csv_report(items, csv_out, datetime.now())

        assert csv_out.exists()
        # Verify utf-8-sig (Excel BOM)
        raw_bytes = csv_out.read_bytes()
        assert raw_bytes.startswith(b"\xef\xbb\xbf")

        with open(csv_out, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["Original Filename"] == "raw1.pdf"
            assert rows[0]["New Filename"] == "CI_CD_Guide.pdf"
            assert rows[0]["Status"] == "RENAMED"

    def test_txt_report(self, tmp_path):
        items, config, summary = self._sample_data(tmp_path)
        txt_out = tmp_path / "report.txt"
        generate_txt_report(items, config, summary, txt_out, datetime.now())

        assert txt_out.exists()
        content = txt_out.read_text(encoding="utf-8")
        assert "SMART FILE ORGANIZER" in content
        assert "Total Files Scanned      : 2" in content
        assert "CI_CD_Guide.pdf" in content

    def test_json_report(self, tmp_path):
        items, config, summary = self._sample_data(tmp_path)
        json_out = tmp_path / "report.json"
        generate_json_report(items, config, summary, json_out, datetime.now(), "sess_123")

        assert json_out.exists()
        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert data["session_id"] == "sess_123"
        assert data["summary"]["total_files"] == 2
        assert len(data["files"]) == 2

    def test_report_manager_all(self, tmp_path):
        items, config, summary = self._sample_data(tmp_path)
        mgr = ReportManager(export_dir=tmp_path)
        csv_p, txt_p, json_p = mgr.generate_all_reports(items, config, summary)

        assert csv_p.exists()
        assert txt_p.exists()
        assert json_p.exists()
        assert csv_p.stem.startswith("smart_organizer_report_")
