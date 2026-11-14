"""
Persistent application settings management.
Saves user preferences to the OS-appropriate application data directory.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from src.core.models import ScanConfig, NamingConvention
from src.storage.secrets import SECRET_KEYS, SecretStore, default_store
from src.utils.platform_utils import get_app_data_dir


class SettingsManager:
    """Manages application settings stored in a JSON configuration file."""

    def __init__(self, config_path: Path = None, secret_store: SecretStore = None):
        self.secrets = secret_store or default_store()
        if config_path:
            self.config_path = config_path
        else:
            self.config_path = get_app_data_dir() / "settings.json"

        self._settings: Dict[str, Any] = self._load_defaults()
        self.load()

    def _load_defaults(self) -> Dict[str, Any]:
        return {
            "theme": "dark",
            "recursive": True,
            "naming_convention": NamingConvention.TITLE_CASE.value,
            "space_replacement": "_",
            "max_filename_length": 80,
            "add_date_prefix": False,
            "date_prefix_format": "%Y-%m-%d",
            "preserve_extension": True,
            "include_hidden": False,
            "enable_ocr": False,
            "enable_google_ai": False,
            "ai_provider": "auto",
            "google_ai_model": "gemini-3.8-flash",
            "groq_model": "qwen/qwen3.8-27b",
            "openai_model": "gpt-5-mini",
            "group_by_domain": True,
            "min_domain_files": 2,
            "rename_unlabelled_images": False,
            "max_file_size_mb": 100,
            "last_folder": "",
            "export_dir": "",
        }

    def load(self) -> None:
        """Loads settings from disk if the file exists."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._settings.update(loaded)
            except Exception:
                # If corrupt or unreadable, fall back to defaults
                pass
        self._migrate_plaintext_secrets()

    def _migrate_plaintext_secrets(self) -> None:
        """Keys saved in clear text by versions <= 1.4.1 move to the OS vault (PR-23)."""
        found = [k for k in SECRET_KEYS if k in self._settings]
        if not found:
            return
        for key in found:
            value = (self._settings.get(key) or "").strip()
            if value and not self.secrets.set(key, value):
                continue  # vault unavailable: the key is dropped below, never kept in clear
        for key in found:
            self._settings.pop(key, None)
        self.save()

    def save(self) -> None:
        """Saves current settings to disk."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        if key in SECRET_KEYS:
            return self.secrets.get(key) or default or ""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """Saves a setting. API keys go to the OS vault; returns False if that failed."""
        if key in SECRET_KEYS:
            return self.secrets.set(key, (value or "").strip())
        self._settings[key] = value
        self.save()
        return True

    def secret(self, key: str, *env_names: str) -> str:
        """An API key from the vault, or from the environment."""
        value = self.get(key, "")
        for env in env_names:
            value = value or os.getenv(env, "")
        return (value or "").strip()

    def get_scan_config(self, root_path: Path) -> ScanConfig:
        """Constructs a ScanConfig object based on current settings."""
        # The scanner never gets a key: its old whole-file AI paths would send original
        # files. V2 cloud titles go only through src/bee (minimised excerpt + per-file permit).
        groq_key = google_key = openai_key = ""
        ai_enabled = False

        return ScanConfig(
            root_path=root_path,
            recursive=self.get("recursive", True),
            naming_convention=NamingConvention(self.get("naming_convention", NamingConvention.TITLE_CASE.value)),
            space_replacement=self.get("space_replacement", "_"),
            max_filename_length=self.get("max_filename_length", 80),
            add_date_prefix=self.get("add_date_prefix", False),
            date_prefix_format=self.get("date_prefix_format", "%Y-%m-%d"),
            preserve_extension=self.get("preserve_extension", True),
            include_hidden=self.get("include_hidden", False),
            enable_ocr=self.get("enable_ocr", False),
            enable_google_ai=ai_enabled,
            ai_provider=self.get("ai_provider", "auto"),
            google_api_key=google_key,
            google_ai_model=self.get("google_ai_model", "gemini-3.8-flash"),
            groq_api_key=groq_key,
            groq_model=self.get("groq_model", "qwen/qwen3.8-27b"),
            openai_api_key=openai_key,
            openai_model=self.get("openai_model", "gpt-5-mini") or "gpt-5-mini",
            group_by_domain=self.get("group_by_domain", True),
            min_domain_files=self.get("min_domain_files", 2),
            rename_unlabelled_images=self.get("rename_unlabelled_images", False),
            max_file_size_mb=self.get("max_file_size_mb", 100),
            export_dir=Path(self.get("export_dir")) if self.get("export_dir") else None,
        )
