"""
Tests for the smart organizer (OpenAI mocked): unwrapping, code projects, project
subfolders, merging, placement, whole-Downloads sorting and undo.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.undo_manager import UndoManager
from src.organizer import smart_organizer as so
from src.organizer.smart_organizer import SmartOrganizer, unwrap, is_code_project
from src.storage.history import HistoryManager
from src.storage.settings import SettingsManager
from src.watcher.download_watcher import DownloadWatcher

YM = datetime.now().strftime("%y-%m")


@pytest.fixture
def env(tmp_path):
    dl = tmp_path / "Downloads"
    dl.mkdir()
    settings = SettingsManager(tmp_path / "settings.json")
    settings._settings.update({"openai_api_key": "sk-test", "groq_api_key": "", "google_api_key": "",
                               "enable_google_ai": False, "watcher_date_prefix": True})
    history = HistoryManager(tmp_path / "history.sqlite3")
    # Per-file OpenAI titles are not under test here: make them fail fast -> local titles
    with patch("src.core.openai_titler.generate_precise_title", return_value=(None, "mocked", {})):
        yield dl, settings, history


def write(path: Path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def tree(root: Path):
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file())


class TestUnwrap:
    def test_single_folder_chain(self, tmp_path):
        write(tmp_path / "X" / "Y" / "Z" / "a.txt")
        assert unwrap(tmp_path / "X") == tmp_path / "X" / "Y" / "Z"

    def test_stops_when_files_present(self, tmp_path):
        write(tmp_path / "X" / "Y" / "a.txt")
        write(tmp_path / "X" / "readme.txt")
        assert unwrap(tmp_path / "X") == tmp_path / "X"

    def test_code_project_detected(self, tmp_path):
        write(tmp_path / "app" / "package.json", "{}")
        assert is_code_project(tmp_path / "app")
        write(tmp_path / "docs" / "a.pdf")
        assert not is_code_project(tmp_path / "docs")


class TestFolderOrganize:
    def test_without_key_only_unwraps(self, env):
        dl, settings, history = env
        settings._settings["openai_api_key"] = ""
        write(dl / "folderX" / "folderY" / "a.txt")
        write(dl / "folderX" / "folderY" / "b.txt")
        r = SmartOrganizer(dl, settings, history).organize_folder(dl / "folderX")
        assert r["moved"] == 2
        assert tree(dl) == ["folderX/a.txt", "folderX/b.txt"]

    def test_code_project_is_only_unwrapped(self, env):
        dl, settings, history = env
        write(dl / "repo-main" / "repo-main" / "package.json", "{}")
        write(dl / "repo-main" / "repo-main" / "src" / "index.js")
        with patch.object(so, "chat_json") as ai:
            SmartOrganizer(dl, settings, history).organize_folder(dl / "repo-main")
        ai.assert_not_called()
        assert tree(dl) == ["repo-main/package.json", "repo-main/src/index.js"]

    def test_ai_project_with_subfolders_and_undo(self, env):
        dl, settings, history = env
        names = ["c1.vcf", "c2.vcf", "logo.png", "banner.png", "contrat.txt", "notes.txt"]
        for n in names:
            write(dl / "download (4)" / "inner" / n, f"content {n}")
        before = tree(dl)
        choices = {
            "c1.vcf": ("Contact", "Delfa Contact Ahmed"),
            "c2.vcf": ("Contact", "Delfa Contact Sara"),
            "logo.png": ("Assets", "Delfa Logo"),
            "banner.png": ("Assets", "Delfa Banner"),
            "contrat.txt": ("", "Contrat Delfa 2026"),
            "notes.txt": ("", "Delfa Meeting Notes"),
        }
        # files are numbered in the order they are listed (alphabetical)
        plan = {
            "project_folder": "Project Delfa", "existing_folder": "",
            "items": [{"id": i, "folder": choices[n][0], "title": choices[n][1]}
                      for i, n in enumerate(sorted(names))],
        }
        with patch.object(so, "chat_json", return_value=(plan, None)):
            r = SmartOrganizer(dl, settings, history).organize_folder(dl / "download (4)")
        project = f"{YM} Project Delfa"
        assert tree(dl) == sorted([
            f"{project}/Assets/{YM} Delfa_Banner.png", f"{project}/Assets/{YM} Delfa_Logo.png",
            f"{project}/Contact/{YM} Delfa_Contact_Ahmed.vcf", f"{project}/Contact/{YM} Delfa_Contact_Sara.vcf",
            f"{project}/{YM} Contrat_Delfa_2026.txt", f"{project}/{YM} Delfa_Meeting_Notes.txt",
        ])
        assert not (dl / "download (4)").exists()  # emptied wrapper removed
        assert r["folders"] == [str(dl / project)]

        UndoManager(history).undo_session(r["session_id"])
        assert tree(dl) == before
        assert not (dl / project).exists()

    def test_merges_into_existing_project(self, env):
        dl, settings, history = env
        write(dl / "Project Delfa" / "Assets" / "old_logo.png")
        write(dl / "new stuff" / "facture.txt", "Facture Delfa")
        plan = {"project_folder": "Delfa", "existing_folder": "Project Delfa",
                "items": [{"id": 0, "folder": "Invoices", "title": "Facture Delfa Novembre"}]}
        with patch.object(so, "chat_json", return_value=(plan, None)):
            SmartOrganizer(dl, settings, history).organize_folder(dl / "new stuff")
        assert f"Project Delfa/Invoices/{YM} Facture_Delfa_Novembre.txt" in tree(dl)
        assert not (dl / "new stuff").exists()

    def test_bad_ai_paths_are_sanitized(self, env):
        dl, settings, history = env
        write(dl / "pack" / "a.txt")
        plan = {"project_folder": "../../Evil", "existing_folder": "",
                "items": [{"id": 0, "folder": "../../../Windows/System32/x/y", "title": "A"}]}
        with patch.object(so, "chat_json", return_value=(plan, None)):
            SmartOrganizer(dl, settings, history).organize_folder(dl / "pack")
        for f in tree(dl):
            assert ".." not in f
        assert all((dl / f).resolve().is_relative_to(dl.resolve()) for f in tree(dl))


class TestPlacement:
    def test_file_goes_into_matching_project(self, env):
        dl, settings, history = env
        (dl / "26-10 Project Delfa" / "Assets").mkdir(parents=True)
        f = write(dl / f"{YM} Delfa_Logo_Blue.png")
        with patch.object(so, "chat_json", return_value=({"folder": "Project Delfa/Assets", "reason": "Delfa logo"}, None)):
            org = SmartOrganizer(dl, settings, history)
            r = org.apply(org.plan_placement(f, title="Delfa Logo Blue"))
        assert tree(dl) == [f"26-10 Project Delfa/Assets/{YM} Delfa_Logo_Blue.png"]
        assert r["session_id"]

    def test_unknown_folder_answer_leaves_file(self, env):
        dl, settings, history = env
        (dl / "Project Delfa").mkdir()
        f = write(dl / "random.txt")
        with patch.object(so, "chat_json", return_value=({"folder": "Something Else", "reason": "?"}, None)):
            plan = SmartOrganizer(dl, settings, history).plan_placement(f)
        assert plan.moves == []


class TestOrganizeDownloads:
    def test_sorts_loose_files_and_unwraps_folders(self, env):
        dl, settings, history = env
        write(dl / "Bee Mission" / "Bee Mission" / "rapport.txt")
        write(dl / "devis_bee.txt", "Devis Bee")
        write(dl / "facture_bee.txt", "Facture Bee")
        write(dl / "vacances.jpg.txt", "photo")
        answer = {"items": [
            {"id": 0, "folder": "Bee Mission/Finance", "title": "Devis Bee 2026"},
            {"id": 1, "folder": "Bee Mission/Finance", "title": "Facture Bee 2026"},
            {"id": 2, "folder": "", "title": "Vacances Photo"},
        ]}
        with patch.object(so, "chat_json", return_value=(answer, None)):
            org = SmartOrganizer(dl, settings, history)
            plan = org.plan_downloads()
            assert "moved" in plan.summary()
            org.apply(plan)
        files = tree(dl)
        assert "Bee Mission/rapport.txt" in files
        assert f"Bee Mission/Finance/{YM} Devis_Bee_2026.txt" in files
        assert f"Bee Mission/Finance/{YM} Facture_Bee_2026.txt" in files
        assert f"{YM} Vacances_Photo.txt" in files or f"{YM} Vacances_Photo.jpg.txt" in files


class TestWatcherFolders:
    def test_new_folder_processed_once_after_it_stops_changing(self, tmp_path):
        seen = []
        w = DownloadWatcher(tmp_path, lambda p: {}, settle_seconds=1,
                            process_dir=lambda p: seen.append(p.name) or {"status": "ORGANIZED"})
        w.snapshot_existing()
        write(tmp_path / "unzipped" / "a.txt")
        w.poll_once(now=0)
        write(tmp_path / "unzipped" / "b.txt")  # still extracting
        w.poll_once(now=1)
        w.poll_once(now=2)
        assert seen == []
        w.poll_once(now=4)
        assert seen == ["unzipped"]
        w.poll_once(now=10)
        assert seen == ["unzipped"]

    def test_app_bundles_and_dated_folders_ignored(self, tmp_path):
        seen = []
        w = DownloadWatcher(tmp_path, lambda p: {}, settle_seconds=0, process_dir=lambda p: seen.append(p.name) or {})
        w.snapshot_existing()
        write(tmp_path / "Tool.app" / "Contents" / "x")
        write(tmp_path / "26-11 Project Delfa" / "a.txt")
        for t in range(4):
            w.poll_once(now=t)
        assert seen == []
