"""
File classifier and extractor registry.
Determines file types using extensions, MIME types, and magic bytes/signatures,
and selects the appropriate specialized content extractor.
"""

from pathlib import Path
from typing import List, Optional
import mimetypes

from src.core.content_extractors import (
    BaseExtractor,
    PDFExtractor,
    DocxExtractor,
    XlsxExtractor,
    PptxExtractor,
    TextExtractor,
    SourceCodeExtractor,
    ImageExtractor,
    VideoExtractor,
    ExecutableExtractor,
    MediaExtractor,
    FontExtractor,
    ArchiveExtractor,
    UniversalFallbackExtractor,
    FallbackExtractor,
)
from src.utils.platform_utils import split_filename_and_ext


# Common magic byte signatures
MAGIC_SIGNATURES = [
    (b"%PDF-", ".pdf", "PDF Document"),
    (b"\x89PNG\r\n\x1a\n", ".png", "PNG Image"),
    (b"\xff\xd8\xff", ".jpg", "JPEG Image"),
    (b"GIF87a", ".gif", "GIF Image"),
    (b"GIF89a", ".gif", "GIF Image"),
    (b"PK\x03\x04", ".zip", "ZIP Archive"),  # Also base container for docx/xlsx/pptx
    (b"SQLite format 3\x00", ".sqlite", "SQLite Database"),
    (b"MZ", ".exe", "Windows Executable"),
    (b"\x1a\x45\xdf\xa3", ".mkv", "Matroska Video"),
    (b"RIFF", ".wav", "RIFF Audio/Video"),
    (b"ID3", ".mp3", "MP3 Audio"),
    (b"\x00\x01\x00\x00", ".ttf", "TrueType Font"),
    (b"OTTO", ".otf", "OpenType Font"),
    (b"wOFF", ".woff", "Web Open Font"),
    (b"wOF2", ".woff2", "Web Open Font 2"),
]


class FileClassifier:
    """
    Maintains extractor registry and selects the most appropriate extractor for any file.
    """

    def __init__(self):
        self.extractors: List[BaseExtractor] = [
            PDFExtractor(),
            DocxExtractor(),
            XlsxExtractor(),
            PptxExtractor(),
            SourceCodeExtractor(),
            TextExtractor(),
            ImageExtractor(),
            VideoExtractor(),
            ExecutableExtractor(),
            MediaExtractor(),
            FontExtractor(),
            ArchiveExtractor(),
            UniversalFallbackExtractor(),  # Always last universal fallback
        ]

    def inspect_magic_signature(self, file_path: Path) -> Optional[tuple[str, str]]:
        """Reads leading bytes to identify file format from signature."""
        try:
            with open(file_path, "rb") as f:
                header = f.read(32)
                for sig, suggested_ext, type_name in MAGIC_SIGNATURES:
                    if header.startswith(sig):
                        return suggested_ext, type_name
        except Exception:
            pass
        return None

    def get_extractor_for_file(self, file_path: Path) -> BaseExtractor:
        """Finds the first extractor capable of handling the file."""
        _, ext = split_filename_and_ext(file_path.name)
        mime, _ = mimetypes.guess_type(str(file_path))

        for extractor in self.extractors:
            if extractor.can_handle(ext, mime):
                return extractor

        return self.extractors[-1]

    def register_extractor(self, extractor: BaseExtractor, priority: bool = False) -> None:
        """Allows registering custom plugins or new format extractors."""
        if priority:
            self.extractors.insert(0, extractor)
        else:
            # Insert right before fallback
            self.extractors.insert(len(self.extractors) - 1, extractor)
