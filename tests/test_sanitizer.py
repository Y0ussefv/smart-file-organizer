"""
Tests for filename sanitization, character filtering, unicode handling, and conventions.
"""

import pytest
from src.core.models import NamingConvention
from src.core.filename_sanitizer import (
    sanitize_stem,
    build_safe_filename,
    extract_words_from_text,
    format_by_convention,
)
from src.utils.platform_utils import split_filename_and_ext


class TestFilenameSanitizer:

    def test_strip_invalid_characters(self):
        raw = 'My "Special" <Report>: 2026/10/15*?|test'
        sanitized = sanitize_stem(raw)
        for char in '<>:"/\\|?*':
            assert char not in sanitized

    def test_windows_reserved_names(self):
        # Reserved words must be prefixed
        for reserved in ["CON", "prn", "AUX", "NUL", "COM1", "lpt9"]:
            sanitized = sanitize_stem(reserved, enforce_windows_rules=True)
            assert sanitized.upper() not in ["CON", "PRN", "AUX", "NUL", "COM1", "LPT9"]
            assert sanitized.startswith("File_")

    def test_unicode_preservation(self):
        # International characters should be preserved in NFC
        raw = "Über_große_Pläne_naïve_résumé_日本語_тест"
        sanitized = sanitize_stem(raw)
        assert "Über" in sanitized
        assert "Pläne" in sanitized
        assert "naïve" in sanitized
        assert "résumé" in sanitized
        assert "日本語" in sanitized
        assert "тест" in sanitized

    def test_trailing_periods_and_spaces(self):
        raw = "   document...   "
        sanitized = sanitize_stem(raw)
        assert not sanitized.endswith(".")
        assert not sanitized.endswith(" ")
        assert not sanitized.startswith(" ")

    def test_compound_extension_preservation(self):
        stem, ext = split_filename_and_ext("archive_backup.tar.gz")
        assert ext == ".tar.gz"
        assert stem == "archive_backup"

        stem, ext = split_filename_and_ext("component.spec.ts")
        assert ext == ".spec.ts"
        assert stem == "component"

    def test_naming_conventions(self):
        words = ["ci", "cd", "deployment", "guide"]

        title = format_by_convention(words, NamingConvention.TITLE_CASE, "_")
        assert title == "Ci_Cd_Deployment_Guide"

        snake = format_by_convention(words, NamingConvention.SNAKE_CASE)
        assert snake == "ci_cd_deployment_guide"

        kebab = format_by_convention(words, NamingConvention.KEBAB_CASE)
        assert kebab == "ci-cd-deployment-guide"

        camel = format_by_convention(words, NamingConvention.CAMEL_CASE)
        assert camel == "CiCdDeploymentGuide"

        sentence = format_by_convention(words, NamingConvention.SENTENCE_CASE, "_")
        assert sentence == "Ci_cd_deployment_guide"

    def test_max_length_truncation(self):
        long_title = "This is an extremely long document title that should be safely truncated at a reasonable word boundary to prevent path issues"
        safe = build_safe_filename(
            candidate_name=long_title,
            original_filename="doc.pdf",
            max_length=40
        )
        assert len(safe) <= 40
        assert safe.endswith(".pdf")
        # Ensure it didn't end with an ugly separator
        stem, _ = split_filename_and_ext(safe)
        assert not stem.endswith("_")
        assert not stem.endswith("-")
