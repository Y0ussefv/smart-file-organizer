"""
Filename sanitizer and formatter.
Ensures generated filenames are safe, valid across Windows, macOS, and Linux,
respect length constraints, preserve extensions, and adhere to user-configured naming styles.
"""

import re
import unicodedata
from pathlib import Path
from typing import Optional

from src.core.models import NamingConvention
from src.utils.platform_utils import (
    WINDOWS_INVALID_CHARS,
    WINDOWS_RESERVED_NAMES,
    split_filename_and_ext,
    is_windows,
)


def format_by_convention(
    words: list[str],
    convention: NamingConvention,
    space_replacement: str = "_"
) -> str:
    """Formats a list of cleaned words according to the requested convention."""
    if not words:
        return ""

    if convention == NamingConvention.TITLE_CASE:
        # Capitalize each word, join with space_replacement
        cleaned_words = [w.capitalize() for w in words]
        return space_replacement.join(cleaned_words)

    elif convention == NamingConvention.SNAKE_CASE:
        cleaned_words = [w.lower() for w in words]
        return "_".join(cleaned_words)

    elif convention == NamingConvention.KEBAB_CASE:
        cleaned_words = [w.lower() for w in words]
        return "-".join(cleaned_words)

    elif convention == NamingConvention.CAMEL_CASE:
        cleaned_words = [w.capitalize() for w in words]
        return "".join(cleaned_words)

    elif convention == NamingConvention.SENTENCE_CASE:
        cleaned_words = [w.lower() for w in words]
        if cleaned_words:
            cleaned_words[0] = cleaned_words[0].capitalize()
        return space_replacement.join(cleaned_words)

    # Default fallback
    return space_replacement.join([w.capitalize() for w in words])


def extract_words_from_text(text: str) -> list[str]:
    """
    Extracts meaningful words from a raw title or string,
    handling snake_case, camelCase, kebab-case, punctuation, and Unicode text.
    """
    if not text:
        return []

    # Normalize Unicode to NFC
    text = unicodedata.normalize("NFC", text)

    # Insert spaces between camelCase boundaries: e.g., "DeploymentGuide" -> "Deployment Guide"
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)

    # Replace common delimiters with space
    text = re.sub(r'[\-_/\\|:;,~=+@#$%^&*()\[\]{}<>?"`\t\r\n]+', ' ', text)

    # Split into tokens
    tokens = text.split()
    words = []
    for token in tokens:
        # Strip trailing/leading punctuation
        cleaned = token.strip(". '\"`")
        if cleaned:
            words.append(cleaned)
    return words


def sanitize_stem(
    raw_stem: str,
    max_length: int = 80,
    enforce_windows_rules: bool = True
) -> str:
    """
    Sanitizes the stem (filename without extension) to be safe across platforms.
    """
    if not raw_stem:
        return "Untitled"

    # Unicode NFC normalization
    stem = unicodedata.normalize("NFC", raw_stem)

    # Remove non-printable / control characters (ASCII 0-31 and 127) and Unicode replacement character 
    stem = "".join(c for c in stem if ord(c) >= 32 and ord(c) != 127 and c != '\ufffd')

    # Replace invalid filesystem characters with an underscore
    # Always protect against Windows invalid chars for maximum cross-platform portability
    for char in WINDOWS_INVALID_CHARS:
        stem = stem.replace(char, "_")

    # Unix null byte and forward slash
    stem = stem.replace("\0", "").replace("/", "_")

    # Collapse multiple consecutive underscores, spaces, or hyphens
    stem = re.sub(r'[\s_]{2,}', '_', stem)
    stem = re.sub(r'-{2,}', '-', stem)

    # Strip leading/trailing spaces and dots (illegal or troublesome on Windows)
    stem = stem.strip(" ._\t")

    # Check for Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    if enforce_windows_rules and stem.upper() in WINDOWS_RESERVED_NAMES:
        stem = f"File_{stem}"

    if not stem:
        stem = "Document"

    # Enforce max length constraint, trying to truncate at a word/separator boundary
    if len(stem) > max_length:
        truncated = stem[:max_length]
        # Try to backtrack to the last separator if reasonable
        last_sep = max(truncated.rfind("_"), truncated.rfind("-"), truncated.rfind(" "))
        if last_sep > max_length // 2:
            stem = truncated[:last_sep].rstrip(" ._-")
        else:
            stem = truncated.rstrip(" ._-")

    return stem


sanitize_component_name = sanitize_stem


def build_safe_filename(
    candidate_name: str,
    original_filename: str,
    convention: NamingConvention = NamingConvention.TITLE_CASE,
    space_replacement: str = "_",
    max_length: int = 80,
    date_prefix: Optional[str] = None,
    preserve_extension: bool = True,
) -> str:
    """
    Builds a fully safe, formatted filename using the candidate title and original extension.
    """
    _, ext = split_filename_and_ext(original_filename)
    if not preserve_extension:
        ext = ""

    # Calculate allowed length for stem
    # Allow 255 total max, but user preference may be lower (e.g. 80)
    allowed_total = min(max_length, 255)
    allowed_stem_len = max(allowed_total - len(ext) - (len(date_prefix) + 1 if date_prefix else 0), 10)

    # Extract words and format
    words = extract_words_from_text(candidate_name)
    if words:
        formatted = format_by_convention(words, convention, space_replacement)
    else:
        # Fallback to sanitized candidate
        formatted = candidate_name

    clean_stem = sanitize_stem(formatted, max_length=allowed_stem_len)

    if date_prefix:
        clean_stem = f"{date_prefix}{space_replacement}{clean_stem}"

    # Final sanity check for full name length
    final_name = f"{clean_stem}{ext}"
    if len(final_name) > 255:
        # Hard truncate stem to fit 255 bytes limit
        excess = len(final_name) - 255
        clean_stem = clean_stem[:-excess].rstrip(" ._-")
        final_name = f"{clean_stem}{ext}"

    return final_name
