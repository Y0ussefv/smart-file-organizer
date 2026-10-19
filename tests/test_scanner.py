"""
Tests for DirectoryScanner: recursive scanning, system ignore lists, and progress callbacks.
"""

from pathlib import Path
from src.core.models import ScanConfig, FileStatus
from src.core.scanner import DirectoryScanner


class TestDirectoryScanner:

    def test_recursive_vs_non_recursive(self, tmp_path):
        # Create folder structure
        top_file = tmp_path / "top_level.txt"
        top_file.write_text("Top level file content")

        sub_dir = tmp_path / "subfolder"
        sub_dir.mkdir()
        sub_file = sub_dir / "nested_doc.txt"
        sub_file.write_text("Nested file content")

        # Non-recursive
        cfg_non_rec = ScanConfig(root_path=tmp_path, recursive=False)
        scanner = DirectoryScanner(cfg_non_rec)
        items, summary = scanner.scan()
        assert summary.total_files == 1
        assert items[0].original_name == "top_level.txt"

        # Recursive
        cfg_rec = ScanConfig(root_path=tmp_path, recursive=True)
        scanner_rec = DirectoryScanner(cfg_rec)
        items_rec, summary_rec = scanner_rec.scan()
        assert summary_rec.total_files == 2
        names = {i.original_name for i in items_rec}
        assert "top_level.txt" in names
        assert "nested_doc.txt" in names

    def test_ignores_system_directories(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main")

        valid_file = tmp_path / "user_notes.txt"
        valid_file.write_text("My personal notes")

        cfg = ScanConfig(root_path=tmp_path, recursive=True, include_hidden=False)
        scanner = DirectoryScanner(cfg)
        items, summary = scanner.scan()

        assert summary.total_files == 1
        assert items[0].original_name == "user_notes.txt"

    def test_scan_cancellation(self, tmp_path):
        # Create multiple files
        for i in range(10):
            (tmp_path / f"file_{i}.txt").write_text(f"Content {i}")

        cfg = ScanConfig(root_path=tmp_path, recursive=False)
        scanner = DirectoryScanner(cfg)

        called = []
        def on_progress(cur, tot, name):
            called.append(name)
            if cur >= 2:
                scanner.cancel()

        items, summary = scanner.scan(progress_callback=on_progress)
        assert len(items) <= 3
