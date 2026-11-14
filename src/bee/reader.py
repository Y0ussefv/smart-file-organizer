"""
Local reading of a downloaded file. Nothing here touches the network.

The extracted text lives only in memory for the time of the decision: it is never
written to the ledger, a cache, a temp file or the logs (spec PR-24).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger("SmartFileOrganizer")

MAX_TEXT = 20000

TEXT_EXTS = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm", ".yaml", ".yml",
             ".ini", ".log", ".rtf", ".vcf", ".ics", ".eml", ".py", ".js", ".ts", ".sql"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2"}

# Below this much readable text, a document is treated as not interpretable
MIN_READABLE_CHARS = 40


@dataclass
class LocalContent:
    kind: str                      # text / pdf / office / image / video / archive / other
    text: str = ""                 # in memory only
    readable: bool = False         # enough text to understand the document
    encrypted: bool = False
    exif_gps: bool = False
    metadata_titles: List[str] = field(default_factory=list)
    error: str = ""


def _kind(ext: str) -> str:
    if ext == ".pdf":
        return "pdf"
    if ext in (".docx", ".pptx", ".xlsx", ".xlsm"):
        return "office"
    if ext in TEXT_EXTS:
        return "text"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in ARCHIVE_EXTS:
        return "archive"
    return "other"


def _pdf(path: Path, out: LocalContent) -> None:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        out.encrypted = True
        try:
            reader.decrypt("")
        except Exception:
            return
    meta = reader.metadata or {}
    for key in ("/Title", "/Subject"):
        value = str(meta.get(key) or "").strip()
        if value:
            out.metadata_titles.append(value)
    parts = []
    for page in reader.pages[:5]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
        if sum(len(p) for p in parts) > MAX_TEXT:
            break
    out.text = "\n".join(parts)


def _office(path: Path, ext: str, out: LocalContent) -> None:
    from src.core import openai_titler as readers  # local readers only, no network
    if ext == ".docx":
        out.text = readers._docx_content(path)
        try:
            import docx
            title = (docx.Document(str(path)).core_properties.title or "").strip()
            if title:
                out.metadata_titles.append(title)
        except Exception:
            pass
    elif ext == ".pptx":
        out.text = readers._pptx_content(path)
    else:
        out.text = readers._xlsx_content(path)


def _image(path: Path, out: LocalContent) -> None:
    try:
        from PIL import Image
        with Image.open(path) as img:
            exif = img.getexif()
            out.exif_gps = bool(exif and exif.get_ifd(0x8825))  # GPSInfo
            for tag in (0x010E, 0x9C9B):  # ImageDescription, XPTitle
                value = exif.get(tag) if exif else None
                if isinstance(value, bytes):
                    value = value.decode("utf-16-le", "ignore").strip("\x00")
                if value:
                    out.metadata_titles.append(str(value).strip())
    except Exception:
        pass
    # No local OCR: an image is never "readable", so it can never go to the cloud (PR-08).


def read_local(path: Path) -> LocalContent:
    ext = path.suffix.lower()
    out = LocalContent(kind=_kind(ext))
    try:
        if out.kind == "pdf":
            _pdf(path, out)
        elif out.kind == "office":
            _office(path, ext, out)
        elif out.kind == "text":
            from src.core import openai_titler as readers
            out.text = readers._read_text(path, limit=MAX_TEXT)
        elif out.kind == "image":
            _image(path, out)
        # video / archive / other: not read (archives are never extracted, PR-28)
    except Exception as e:
        out.error = type(e).__name__
        logger.info("Local reading failed (%s)", out.error)
    out.text = (out.text or "")[:MAX_TEXT]
    useful = "".join(ch for ch in out.text if ch.isalnum())
    out.readable = len(useful) >= MIN_READABLE_CHARS and not out.error
    return out
