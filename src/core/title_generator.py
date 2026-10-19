"""
Intelligent title and descriptive filename generator.
Synthesizes extracted content and metadata into concise, safe, meaningful filenames.
Ensures that if no meaningful title can be derived, the original name is safely kept with a clear explanation.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.models import ScanConfig, FileItem, FileStatus
from src.core.content_extractors import ExtractionResult
from src.core.filename_sanitizer import build_safe_filename, extract_words_from_text
from src.utils.platform_utils import split_filename_and_ext


# Generic words that do not qualify as a meaningful, distinct title on their own
GENERIC_TITLES = {
    "untitled", "document", "file", "new file", "scan", "test",
    "sample", "temp", "tmp", "page", "image", "photo", "screenshot",
    "presentation", "workbook", "sheet", "draft", "notes", "readme",
    "index", "default", "blank", "content", "data", "report"
}


class TitleGenerator:
    """Generates descriptive, sanitized filenames based on extracted content and rules."""

    def __init__(self, config: Optional[ScanConfig] = None):
        self.config = config or ScanConfig(root_path=Path("."))

    def is_meaningful_title(self, title: Optional[str]) -> bool:
        """
        Validates whether a candidate string is sufficiently meaningful to rename a file.
        Rejects empty strings, pure numbers, single characters, and generic placeholders.
        """
        if not title:
            return False

        stripped = title.strip()
        if len(stripped) < 3:
            return False

        # Reject pure numbers or date-only strings
        if re.match(r'^\d+([._\-/]\d+)*$', stripped):
            return False

        # Reject pure punctuation
        if not re.search(r'[A-Za-z0-9\u0080-\uffff]', stripped):
            return False

        # Check if words are purely generic
        words = extract_words_from_text(stripped)
        if not words:
            return False

        # If it's a single word and matches generic words
        if len(words) == 1 and words[0].lower() in GENERIC_TITLES:
            return False

        # If all words are generic
        if all(w.lower() in GENERIC_TITLES for w in words):
            return False

        return True

    def clean_candidate_title(self, raw_title: str) -> str:
        """Strips noise, document boilerplate, URLs, and excessive whitespace from title text."""
        # Remove URLs
        title = re.sub(r'https?://\S+|www\.\S+', '', raw_title)

        # Remove email addresses
        title = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', title)

        # Remove common document footer/header boilerplate
        title = re.sub(r'\b(page\s+\d+(\s+of\s+\d+)?|confidential|all rights reserved|internal use only)\b', '', title, flags=re.IGNORECASE)

        # Remove file extension if accidentally part of extracted title
        title = re.sub(r'\.(pdf|docx|xlsx|pptx|txt|md|html|json)$', '', title, flags=re.IGNORECASE)

        # Remove leading/trailing symbols
        title = re.sub(r'^[\s\-_:;.,|#*~]+|[\s\-_:;.,|#*~]+$', '', title)

        return title.strip()

    def generate_proposed_filename(
        self,
        item: FileItem,
        result: ExtractionResult,
        file_mtime: Optional[datetime] = None
    ) -> tuple[str, FileStatus, str]:
        """
        Generates the proposed new filename for a file item based on extraction result and config.
        Returns: (proposed_filename, status, explanation)
        """
        raw_title = result.title

        # Determine date prefix if configured
        date_prefix = None
        if self.config.add_date_prefix:
            date_obj = file_mtime or datetime.now()
            try:
                date_prefix = date_obj.strftime(self.config.date_prefix_format)
            except Exception:
                date_prefix = date_obj.strftime("%Y-%m-%d")

        # Check if title is meaningful
        cleaned_title = self.clean_candidate_title(raw_title) if raw_title else ""

        if self.is_meaningful_title(cleaned_title):
            # Build safe filename
            proposed_name = build_safe_filename(
                candidate_name=cleaned_title,
                original_filename=item.original_name,
                convention=self.config.naming_convention,
                space_replacement=self.config.space_replacement,
                max_length=self.config.max_filename_length,
                date_prefix=date_prefix,
                preserve_extension=self.config.preserve_extension
            )

            # Check if name is actually different
            if proposed_name.lower() == item.original_name.lower():
                return proposed_name, FileStatus.UNCHANGED, "Current filename already matches proposed descriptive name."

            explanation = result.explanation or f"Generated from extracted title: '{cleaned_title}'"
            return proposed_name, FileStatus.READY_TO_RENAME, explanation

        else:
            # Cannot derive a meaningful title: Keep original filename for safety
            # If date prefix is explicitly requested, we can still add date prefix if user wants
            if self.config.add_date_prefix and date_prefix:
                stem, ext = split_filename_and_ext(item.original_name)
                proposed_name = f"{date_prefix}{self.config.space_replacement}{stem}{ext}"
                if proposed_name != item.original_name:
                    return proposed_name, FileStatus.READY_TO_RENAME, f"Added date prefix ({date_prefix}); no new content title detected."

            explanation = (
                result.explanation
                if result.explanation and "retained" in result.explanation.lower()
                else "No descriptive title or headings detected; kept original filename for data safety."
            )
            return item.original_name, FileStatus.UNCHANGED, explanation
