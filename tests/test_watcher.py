"""
Tests for the Downloads watcher, the "26-11 " prefix and start-at-login helpers.
"""

import sys
from datetime import datetime
from pathlib import Path

from src.integrations.download_processor import DownloadProcessor
from src.storage.history import HistoryManager
from src.storage.settings import SettingsManager
from src.watcher import autostart
from src.watcher.download_watcher import DownloadWatcher, is_candidate


def _processor(tmp_path):
    s = SettingsManager(tmp_path / "settings.json")
    s._settings.update({"groq_api_key": "", "google_api_key": "", "openai_api_key": "", "enable_google_ai": False})
    return DownloadProcessor(settings=s, history=HistoryManager(tmp_path / "h.sqlite3"))


class TestCandidates:
    def test_temp_and_organized_files_are_skipped(self):
        for name in ["a.pdf.crdownload", "a.part", "x.tmp", "desktop.ini", ".hidden", "~$doc.docx",
                     "26-11 Already_Named.pdf", "26-11_Old.pdf"]:
            assert not is_candidate(Path(name)), name
        for name in ["report.pdf", "IMG_0001.jpg", "my.part2.pdf", "2026-11-04 notes.txt"]:
            assert is_candidate(Path(name)), name


class TestWatcher:
    def test_only_new_finished_files_are_processed(self, tmp_path):
        (tmp_path / "old.pdf").write_text("existing")
        seen = []
        w = DownloadWatcher(tmp_path, lambda p: seen.append(p.name) or {"status": "UNCHANGED"},
                            settle_seconds=3)
        w.snapshot_existing()

        (tmp_path / "new.pdf.crdownload").write_text("partial")
        w.poll_once(now=100)
        (tmp_path / "new.pdf.crdownload").rename(tmp_path / "new.pdf")
        w.poll_once(now=101)          # just appeared: not settled yet
        assert seen == []
        w.poll_once(now=105)          # size stable for >= 3 s
        assert seen == ["new.pdf"]
        w.poll_once(now=110)          # never twice
        assert seen == ["new.pdf"]

    def test_growing_file_waits(self, tmp_path):
        seen = []
        w = DownloadWatcher(tmp_path, lambda p: seen.append(p.name) or {}, settle_seconds=3)
        w.snapshot_existing()
        f = tmp_path / "big.zip"
        f.write_bytes(b"1")
        w.poll_once(now=0)
        f.write_bytes(b"12")
        w.poll_once(now=4)            # still growing
        assert seen == []
        w.poll_once(now=8)
        assert seen == ["big.zip"]

    def test_own_output_and_ignored_names_not_reprocessed(self, tmp_path):
        calls = []

        def process(p):
            calls.append(p.name)
            new = p.with_name("Renamed Thing.pdf")
            p.rename(new)
            return {"status": "RENAMED", "new_path": str(new)}

        w = DownloadWatcher(tmp_path, process, settle_seconds=0)
        w.snapshot_existing()
        (tmp_path / "dl.pdf").write_text("x")
        w.poll_once(now=1)
        w.poll_once(now=2)
        assert calls == ["dl.pdf"]

        w.ignore("restored.pdf")
        (tmp_path / "restored.pdf").write_text("x")
        w.poll_once(now=3)
        assert calls == ["dl.pdf"]

    def test_paused_watcher_retries_after_resume(self, tmp_path):
        seen = []
        w = DownloadWatcher(tmp_path, lambda p: seen.append(p.name) or {}, settle_seconds=0)
        w.snapshot_existing()
        w.pause(True)
        (tmp_path / "a.txt").write_text("hello")
        w.poll_once(now=1)
        assert seen == []
        w.pause(False)
        w.poll_once(now=2)
        w.poll_once(now=3)
        assert seen == ["a.txt"]


class TestYearMonthPrefix:
    def test_download_gets_26_11_style_prefix(self, tmp_path):
        d = tmp_path / "Downloads"
        d.mkdir()
        f = d / "download (3).md"
        f.write_text("# Bee Diagnostic et cadrage\n\ntext", encoding="utf-8")
        r = _processor(tmp_path).process(str(f), add_date_prefix=True,
                                         date_prefix_format="%y-%m", date_prefix_separator=" ")
        assert r["status"] == "RENAMED", r
        mtime = datetime.fromtimestamp(Path(r["new_path"]).stat().st_mtime)
        assert r["new_name"] == f"{mtime:%y-%m} Bee_Diagnostic_Et_Cadrage.md"


class TestAutostart:
    def test_launch_command_runs_watch_mode(self):
        cmd = autostart.launch_command()
        assert cmd[-1] == "--watch"
        if not getattr(sys, "frozen", False):
            assert cmd[-2].endswith("main.py")


class TestFileInUse:
    def test_open_file_waits_until_closed(self, tmp_path):
        """A browser virus scan holds the file open: renaming it then makes Chrome say 'Virus scan failed'."""
        import pytest
        if sys.platform != "win32":
            pytest.skip("Windows-only check")
        from src.watcher.download_watcher import file_in_use

        seen = []
        w = DownloadWatcher(tmp_path, lambda p: seen.append(p.name) or {}, settle_seconds=3)
        w.snapshot_existing()
        f = tmp_path / "report.pdf"
        f.write_bytes(b"%PDF-1.4 data")
        handle = open(f, "rb")  # like Windows Defender scanning it
        try:
            assert file_in_use(f)
            w.poll_once(now=100)
            w.poll_once(now=110)
            assert seen == []
        finally:
            handle.close()
        assert not file_in_use(f)
        w.poll_once(now=111)  # closed: waits a full settle period again
        assert seen == []
        w.poll_once(now=114)
        assert seen == ["report.pdf"]
