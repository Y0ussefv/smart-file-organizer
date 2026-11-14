"""
BeeOrganizer 1.4.2 hotfix guarantees (spec V2 §10, RG01, PR-23, §4.3, §5.3):
- nothing is sent to an external AI service, even with API keys present (fail closed);
- API keys are kept in the OS vault, never in settings.json;
- the watcher only renames: downloads are not moved, received folders are left as they are.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from src.core import openai_titler
from src.core.models import ScanConfig
from src.core.scanner import DirectoryScanner
from src.integrations.download_processor import DownloadProcessor
from src.privacy import cloud_gate
from src.storage.history import HistoryManager
from src.storage.secrets import MemorySecretStore, SecretStore
from src.storage.settings import SettingsManager


def _no_network(*args, **kwargs):
    raise AssertionError("an external request was attempted")


@pytest.fixture
def no_network():
    with patch.object(requests, "post", side_effect=_no_network), \
         patch.object(requests, "get", side_effect=_no_network):
        yield


class TestNothingLeavesTheComputer:
    def test_gate_is_closed_by_default(self):
        assert cloud_gate.cloud_allowed() is False
        with pytest.raises(cloud_gate.CloudBlocked):
            cloud_gate.post("https://api.openai.com/v1/chat/completions", json={"x": 1})
        with pytest.raises(cloud_gate.CloudBlocked):
            cloud_gate.get("https://api.openai.com/v1/models")

    def test_keys_present_but_scan_stays_local(self, tmp_path, monkeypatch, no_network):
        """RG01: a key in the vault and in the environment, yet 0 content request."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        monkeypatch.setenv("GROQ_API_KEY", "gsk-env")
        settings = SettingsManager(tmp_path / "settings.json")
        settings.set("openai_api_key", "sk-vault")
        settings.set("enable_google_ai", True)
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "download (3).txt").write_text("Contrat de prestation SINELAC 2026", encoding="utf-8")

        cfg = settings.get_scan_config(docs)
        assert cfg.openai_api_key == "" and cfg.groq_api_key == "" and cfg.google_api_key == ""
        assert cfg.enable_google_ai is False

        items, _ = DirectoryScanner(cfg).scan()  # any network call would raise
        assert len(items) == 1

    def test_direct_call_with_key_is_blocked(self, tmp_path, no_network):
        """Even a code path that still has a key cannot send the file."""
        f = tmp_path / "passport.txt"
        f.write_text("Passport number AB123456", encoding="utf-8")
        title, err, _ = openai_titler.generate_precise_title(f, "sk-test", "gpt-5-mini")
        assert title is None and err

    def test_scanner_with_key_falls_back_to_local(self, tmp_path, no_network):
        (tmp_path / "scan001.txt").write_text("Contrat de travail Delfa", encoding="utf-8")
        cfg = ScanConfig(root_path=tmp_path, recursive=False, group_by_domain=False,
                         openai_api_key="sk-test", openai_model="gpt-5-mini")
        items, _ = DirectoryScanner(cfg).scan()
        assert len(items) == 1
        assert "used local analysis" in (items[0].explanation or "")


class TestKeysInVault:
    def test_plaintext_key_migrates_to_vault(self, tmp_path, memory_secret_store):
        cfg = tmp_path / "settings.json"
        cfg.write_text(json.dumps({"openai_api_key": "sk-old", "theme": "light"}), encoding="utf-8")
        settings = SettingsManager(cfg)
        assert memory_secret_store.get("openai_api_key") == "sk-old"
        on_disk = json.loads(cfg.read_text(encoding="utf-8"))
        assert "openai_api_key" not in on_disk and on_disk["theme"] == "light"
        assert settings.get("openai_api_key") == "sk-old"

    def test_key_never_written_to_settings_file(self, tmp_path):
        cfg = tmp_path / "settings.json"
        settings = SettingsManager(cfg)
        assert settings.set("openai_api_key", "sk-new") is True
        settings.set("theme", "dark")
        assert "sk-new" not in cfg.read_text(encoding="utf-8")

    def test_vault_unavailable_drops_key_instead_of_keeping_it_in_clear(self, tmp_path):
        class BrokenVault(SecretStore):
            def get(self, name):
                return ""

            def set(self, name, value):
                return False

        cfg = tmp_path / "settings.json"
        cfg.write_text(json.dumps({"openai_api_key": "sk-old"}), encoding="utf-8")
        settings = SettingsManager(cfg, secret_store=BrokenVault())
        assert "sk-old" not in cfg.read_text(encoding="utf-8")
        assert settings.set("openai_api_key", "sk-new") is False
        assert "sk-new" not in cfg.read_text(encoding="utf-8")


class TestRenameOnly:
    def test_download_is_renamed_in_place(self, tmp_path, no_network):
        dl = tmp_path / "Downloads"
        dl.mkdir()
        f = dl / "download (3).txt"
        f.write_text("Rapport annuel BeeStart 2026", encoding="utf-8")
        settings = SettingsManager(tmp_path / "settings.json")
        result = DownloadProcessor(settings=settings, history=HistoryManager(tmp_path / "h.sqlite3")).process(
            str(f), folder_mode="none", add_date_prefix=True, date_prefix_format="%y-%m",
            date_prefix_separator=" ")
        new_path = Path(result.get("new_path") or f)
        assert new_path.parent == dl                      # not moved
        assert [p for p in dl.iterdir() if p.is_dir()] == []  # no folder created
        if result.get("status") == "RENAMED":
            assert new_path.name.startswith(datetime.now().strftime("%y-%m") + " ")

    def test_received_folder_is_left_as_is(self, tmp_path):
        pytest.importorskip("PySide6")
        from src.watcher.tray_app import TrayController

        outer = tmp_path / "archive"
        (outer / "inner").mkdir(parents=True)
        (outer / "inner" / "a.txt").write_text("x", encoding="utf-8")
        result = TrayController._process_dir(None, outer)
        assert result["status"] == "SKIPPED"
        assert (outer / "inner" / "a.txt").exists()       # structure untouched (spec §5.3)

    def test_tray_has_no_automatic_folder_options(self):
        pytest.importorskip("PySide6")
        from src.watcher import tray_app
        source = Path(tray_app.__file__).read_text(encoding="utf-8")
        assert "SmartOrganizer" not in source
        assert "watcher_smart_folders" not in source and "watcher_type_folders" not in source
        assert 'folder_mode="none"' in source


class TestInvisibleCharacters:
    def test_utf8_bom_never_reaches_the_file_name(self):
        from src.core.filename_sanitizer import extract_words_from_text, sanitize_stem
        assert extract_words_from_text("﻿rapport annuel")[0] == "rapport"
        assert sanitize_stem("﻿Rapport​_Annuel") == "Rapport_Annuel"

    def test_bom_text_file_gets_clean_title(self, tmp_path, no_network):
        dl = tmp_path / "Downloads"
        dl.mkdir()
        f = dl / "download (9).txt"
        f.write_bytes("Rapport annuel BeeStart 2026".encode("utf-8-sig"))
        settings = SettingsManager(tmp_path / "settings.json")
        result = DownloadProcessor(settings=settings, history=HistoryManager(tmp_path / "h.sqlite3")).process(
            str(f), folder_mode="none", add_date_prefix=True, date_prefix_format="%y-%m",
            date_prefix_separator=" ")
        name = Path(result["new_path"]).name
        assert "﻿" not in name
        assert name.split(" ", 1)[1][0].isupper()
