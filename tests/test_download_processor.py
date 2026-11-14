"""
Tests for DownloadProcessor (single download: analyze, rename without overwrite, undo).
"""

from pathlib import Path

from src.integrations.download_processor import (
    DownloadProcessor,
    site_folder_name,
    type_folder_name,
)
from src.storage.history import HistoryManager
from src.storage.settings import SettingsManager


def _processor(tmp_path) -> DownloadProcessor:
    settings = SettingsManager(tmp_path / "settings.json")
    # Keep tests offline / deterministic
    settings._settings.update({"enable_google_ai": False})
    return DownloadProcessor(settings=settings, history=HistoryManager(tmp_path / "history.sqlite3"))


def _download(tmp_path, name, text) -> Path:
    d = tmp_path / "Downloads"
    d.mkdir(exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p


class TestHelpers:
    def test_site_folder_name(self):
        assert site_folder_name("https://www.github.com/a/b.zip") == "Github"
        assert site_folder_name("https://drive.google.com/file") == "Google"
        assert site_folder_name("https://news.bbc.co.uk/x") == "Bbc"
        assert site_folder_name("http://127.0.0.1:8000/x") is None
        assert site_folder_name(None) is None

    def test_type_folder_name(self):
        assert type_folder_name("a.pdf") == "Documents"
        assert type_folder_name("a.tar.gz") == "Archives"
        assert type_folder_name("a.weird") == "Other"


class TestDownloadProcessor:
    def test_renames_from_content_and_undo(self, tmp_path):
        f = _download(tmp_path, "download (3).md", "# Quarterly Marketing Plan\n\nSome body text.")
        proc = _processor(tmp_path)

        r = proc.process(str(f))
        assert r["status"] == "RENAMED", r
        assert r["new_name"] == "Quarterly_Marketing_Plan.md"
        assert Path(r["new_path"]).exists() and not f.exists()

        u = proc.undo(r["session_id"])
        assert u["status"] == "REVERTED", u
        assert f.exists()

    def test_never_overwrites_existing(self, tmp_path):
        _download(tmp_path, "Quarterly_Marketing_Plan.md", "existing")
        f = _download(tmp_path, "file.md", "# Quarterly Marketing Plan\n")
        r = _processor(tmp_path).process(str(f))
        assert r["status"] == "RENAMED"
        assert r["new_name"] == "Quarterly_Marketing_Plan_2.md"
        assert (tmp_path / "Downloads" / "Quarterly_Marketing_Plan.md").read_text() == "existing"

    def test_site_folder_mode(self, tmp_path):
        f = _download(tmp_path, "x.md", "# Release Notes\n")
        r = _processor(tmp_path).process(str(f), source_url="https://www.github.com/repo", folder_mode="site")
        assert r["status"] == "RENAMED"
        assert Path(r["new_path"]) == tmp_path / "Downloads" / "Github" / "Release_Notes.md"

    def test_dry_run_changes_nothing(self, tmp_path):
        f = _download(tmp_path, "x.md", "# Release Notes\n")
        r = _processor(tmp_path).process(str(f), dry_run=True)
        assert r["status"] == "PREVIEW"
        assert f.exists()

    def test_missing_file(self, tmp_path):
        r = _processor(tmp_path).process(str(tmp_path / "nope.pdf"))
        assert r["status"] == "ERROR"
