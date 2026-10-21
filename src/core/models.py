"""
Data models and enumerations for Smart File Organizer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid


class FileStatus(str, Enum):
    FOUND = "FOUND"
    ANALYZING = "ANALYZING"
    READY_TO_RENAME = "READY_TO_RENAME"
    UNCHANGED = "UNCHANGED"
    RENAMED = "RENAMED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    REVERTED = "REVERTED"

    @property
    def display_name(self) -> str:
        names = {
            FileStatus.FOUND: "Discovered",
            FileStatus.ANALYZING: "Analyzing...",
            FileStatus.READY_TO_RENAME: "Ready to Rename",
            FileStatus.UNCHANGED: "Unchanged",
            FileStatus.RENAMED: "Renamed",
            FileStatus.SKIPPED: "Skipped",
            FileStatus.ERROR: "Error",
            FileStatus.REVERTED: "Reverted",
        }
        return names.get(self, self.value)


class NamingConvention(str, Enum):
    TITLE_CASE = "Title_Case"       # e.g., CI_CD_Deployment_Guide
    SNAKE_CASE = "snake_case"       # e.g., ci_cd_deployment_guide
    KEBAB_CASE = "kebab-case"       # e.g., ci-cd-deployment-guide
    CAMEL_CASE = "CamelCase"         # e.g., CiCdDeploymentGuide
    SENTENCE_CASE = "Sentence_case" # e.g., Ci_cd_deployment_guide


@dataclass
class ScanConfig:
    """Configuration options for scanning and renaming."""
    root_path: Path
    recursive: bool = True
    naming_convention: NamingConvention = NamingConvention.TITLE_CASE
    space_replacement: str = "_"
    max_filename_length: int = 80
    add_date_prefix: bool = False
    date_prefix_format: str = "%Y-%m-%d"
    preserve_extension: bool = True
    include_hidden: bool = False
    enable_ocr: bool = False
    enable_google_ai: bool = False
    ai_provider: str = "auto"
    google_api_key: str = ""
    google_ai_model: str = "gemini-3.8-flash"
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    group_by_domain: bool = True
    min_domain_files: int = 2
    rename_unlabelled_images: bool = False
    max_file_size_mb: int = 100
    export_dir: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_path": str(self.root_path),
            "recursive": self.recursive,
            "naming_convention": self.naming_convention.value,
            "space_replacement": self.space_replacement,
            "max_filename_length": self.max_filename_length,
            "add_date_prefix": self.add_date_prefix,
            "date_prefix_format": self.date_prefix_format,
            "preserve_extension": self.preserve_extension,
            "include_hidden": self.include_hidden,
            "enable_ocr": self.enable_ocr,
            "enable_google_ai": self.enable_google_ai,
            "ai_provider": self.ai_provider,
            "google_api_key": self.google_api_key,
            "google_ai_model": self.google_ai_model,
            "groq_api_key": self.groq_api_key,
            "groq_model": self.groq_model,
            "group_by_domain": self.group_by_domain,
            "min_domain_files": self.min_domain_files,
            "rename_unlabelled_images": self.rename_unlabelled_images,
            "max_file_size_mb": self.max_file_size_mb,
            "export_dir": str(self.export_dir) if self.export_dir else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScanConfig":
        return cls(
            root_path=Path(data.get("root_path", ".")),
            recursive=data.get("recursive", True),
            naming_convention=NamingConvention(data.get("naming_convention", NamingConvention.TITLE_CASE.value)),
            space_replacement=data.get("space_replacement", "_"),
            max_filename_length=data.get("max_filename_length", 80),
            add_date_prefix=data.get("add_date_prefix", False),
            date_prefix_format=data.get("date_prefix_format", "%Y-%m-%d"),
            preserve_extension=data.get("preserve_extension", True),
            include_hidden=data.get("include_hidden", False),
            enable_ocr=data.get("enable_ocr", False),
            enable_google_ai=data.get("enable_google_ai", False),
            ai_provider=data.get("ai_provider", "auto"),
            google_api_key=data.get("google_api_key", ""),
            google_ai_model=data.get("google_ai_model", "gemini-3.8-flash"),
            groq_api_key=data.get("groq_api_key", ""),
            groq_model=data.get("groq_model", "qwen/qwen3.8-27b"),
            group_by_domain=data.get("group_by_domain", True),
            min_domain_files=data.get("min_domain_files", 2),
            rename_unlabelled_images=data.get("rename_unlabelled_images", False),
            max_file_size_mb=data.get("max_file_size_mb", 100),
            export_dir=Path(data["export_dir"]) if data.get("export_dir") else None,
        )


@dataclass
class FileItem:
    """Represents a scanned and analyzed file."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_path: Path = field(default_factory=lambda: Path("."))
    original_name: str = ""
    original_stem: str = ""
    original_ext: str = ""
    new_name: str = ""
    new_path: Optional[Path] = None
    domain: Optional[str] = None
    target_subfolder: Optional[str] = None
    file_type: str = "Unknown"
    file_size: int = 0
    sha256: Optional[str] = None
    detected_title: Optional[str] = None
    content_summary: Optional[str] = None
    status: FileStatus = FileStatus.FOUND
    explanation: str = ""
    is_selected: bool = False
    is_supported: bool = True
    error_message: Optional[str] = None
    manual_override: bool = False
    analysis_time_ms: float = 0.0

    @property
    def formatted_size(self) -> str:
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{self.file_size} B"

    @property
    def has_name_changed(self) -> bool:
        return bool((self.new_name and self.new_name != self.original_name) or self.target_subfolder)

    @property
    def proposed_display_path(self) -> str:
        if self.target_subfolder:
            return f"{self.target_subfolder}/{self.new_name}"
        return self.new_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "original_path": str(self.original_path),
            "original_name": self.original_name,
            "original_stem": self.original_stem,
            "original_ext": self.original_ext,
            "new_name": self.new_name,
            "new_path": str(self.new_path) if self.new_path else None,
            "domain": self.domain,
            "target_subfolder": self.target_subfolder,
            "proposed_display_path": self.proposed_display_path,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "formatted_size": self.formatted_size,
            "sha256": self.sha256,
            "detected_title": self.detected_title,
            "content_summary": self.content_summary,
            "status": self.status.value,
            "explanation": self.explanation,
            "is_selected": self.is_selected,
            "is_supported": self.is_supported,
            "error_message": self.error_message,
            "manual_override": self.manual_override,
        }


@dataclass
class RenameHistoryRecord:
    """Historical record of an applied rename for auditing and undo."""
    session_id: str
    timestamp: str
    original_path: str
    new_path: str
    original_name: str
    new_name: str
    file_size: int
    sha256: Optional[str] = None
    status: str = "RENAMED"  # RENAMED, REVERTED, ERROR
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "original_path": self.original_path,
            "new_path": self.new_path,
            "original_name": self.original_name,
            "new_name": self.new_name,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class ScanSummary:
    """Summary counts for UI cards and reporting."""
    total_files: int = 0
    supported_files: int = 0
    unsupported_files: int = 0
    ready_to_rename: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    renamed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
