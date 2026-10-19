"""
Persistent application settings management.
Saves user preferences to the OS-appropriate application data directory.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from src.core.models import ScanConfig, NamingConvention
from src.utils.platform_utils import get_app_data_dir


class SettingsManager:
    """Manages application settings stored in a JSON configuration file."""

    def __init__(self, config_path: Path = None):
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
            "google_api_key": os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
            "google_ai_model": "gemini-3.8-flash",
            "groq_api_key": os.getenv("GROQ_API_KEY", ""),
            "groq_model": "qwen/qwen3.8-27b",
            "rename_unlabelled_images": True,
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

    def save(self) -> None:
        """Saves current settings to disk."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self.save()

    def get_scan_config(self, root_path: Path) -> ScanConfig:
        """Constructs a ScanConfig object based on current settings."""
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
            enable_google_ai=self.get("enable_google_ai", False),
            google_api_key=self.get("google_api_key", ""),
            google_ai_model=self.get("google_ai_model", "gemini-1.5-flash"),
            rename_unlabelled_images=self.get("rename_unlabelled_images", True),
            max_file_size_mb=self.get("max_file_size_mb", 100),
            export_dir=Path(self.get("export_dir")) if self.get("export_dir") else None,
        )
