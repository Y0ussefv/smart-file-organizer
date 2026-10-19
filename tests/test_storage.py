"""
Tests for settings persistence and SQLite history tracking.
"""

from pathlib import Path
from src.core.models import NamingConvention, RenameHistoryRecord
from src.storage.settings import SettingsManager
from src.storage.history import HistoryManager


class TestStorage:

    def test_settings_save_and_load(self, tmp_path):
        config_file = tmp_path / "custom_settings.json"
        mgr = SettingsManager(config_path=config_file)

        mgr.set("naming_convention", NamingConvention.KEBAB_CASE.value)
        mgr.set("max_filename_length", 120)
        mgr.set("theme", "light")

        # Reload from disk
        mgr2 = SettingsManager(config_path=config_file)
        assert mgr2.get("naming_convention") == NamingConvention.KEBAB_CASE.value
        assert mgr2.get("max_filename_length") == 120
        assert mgr2.get("theme") == "light"

    def test_history_sessions_and_records(self, tmp_path):
        db_file = tmp_path / "test_history.sqlite3"
        history = HistoryManager(db_path=db_file)

        records = [
            RenameHistoryRecord(
                session_id="sess_100",
                timestamp="2026-10-19T16:00:00",
                original_path=str(tmp_path / "a.txt"),
                new_path=str(tmp_path / "Alpha.txt"),
                original_name="a.txt",
                new_name="Alpha.txt",
                file_size=50,
                sha256="hash100",
                status="RENAMED"
            ),
            RenameHistoryRecord(
                session_id="sess_100",
                timestamp="2026-10-19T16:00:01",
                original_path=str(tmp_path / "b.txt"),
                new_path=str(tmp_path / "Beta.txt"),
                original_name="b.txt",
                new_name="Beta.txt",
                file_size=60,
                sha256="hash200",
                status="RENAMED"
            ),
        ]

        history.record_session("sess_100", str(tmp_path), 2, records)

        # Check recent sessions
        sessions = history.get_recent_sessions(limit=5)
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "sess_100"
        assert sessions[0]["renamed_files"] == 2
        assert sessions[0]["is_reverted"] == 0

        # Check records
        fetched = history.get_session_records("sess_100")
        assert len(fetched) == 2
        assert fetched[0].new_name == "Alpha.txt"
        assert fetched[1].new_name == "Beta.txt"

        # Check active session id
        assert history.get_last_active_session_id() == "sess_100"

        # Mark reverted
        history.mark_session_reverted("sess_100")
        assert history.get_last_active_session_id() is None
        sessions_rev = history.get_recent_sessions()
        assert sessions_rev[0]["is_reverted"] == 1
