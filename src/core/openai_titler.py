"""
OpenAI precise titling.

Reads the real content of ANY file (full text, slides, sheets, the picture itself,
video keyframe, archive listing, metadata) and asks OpenAI for an exact,
specific filename title built only from facts that appear in the file.

Used by DirectoryScanner for every file when an OpenAI API key is configured.
"""

import base64
import json
import re
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.privacy import cloud_gate

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
SUGGESTED_OPENAI_MODELS = ["gpt-5-mini", "gpt-5", "gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"]

MAX_CONTEXT_CHARS = 12000

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".xml", ".html", ".htm",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".log", ".tex", ".srt", ".vtt",
    ".svg", ".url", ".rtf", ".eml",
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".c", ".h", ".cpp", ".hpp", ".cs",
    ".go", ".rs", ".rb", ".php", ".swift", ".dart", ".sql", ".sh", ".bat", ".ps1", ".lua",
    ".r", ".m", ".scala", ".vue", ".css", ".scss", ".frag", ".vert", ".glsl", ".hlsl",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif", ".heic"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".m4v"}

SYSTEM_PROMPT = """You name files. You receive the real content of one file and must return an EXACT, specific title for its filename.

Rules:
- Use only facts present in the content: exact company / brand / product / person / project names, document type, invoice or reference numbers, dates, versions, places, topics.
- Be precise, not generic. Bad: "Invoice", "Report", "Image", "Document". Good: "Delfa Invoice 2026-0412 Office Supplies", "Ahmed Benali CV Data Analyst", "Q3 2026 Sales Report Morocco", "Golden Retriever Puppy On Beach".
- 3 to 10 words. No file extension. No dates unless they appear in the content and identify the file.
- For images: describe exactly what is shown (readable text, logos, brand, scene, screenshot of which app/page).
- For code: what the module/program does and its main component name.
- Write the title in the main language of the content.
- Never invent facts. If the content is unreadable, describe the file as precisely as the available metadata allows.
Return JSON only."""

RESPONSE_SCHEMA = {
    "name": "file_title",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "description": "Exact filename title, 3-10 words, no extension"},
            "document_type": {"type": "string", "description": "e.g. Invoice, CV, Contract, Photo, Logo, Source Code"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["title", "document_type", "confidence"],
    },
}


# ---------------------------------------------------------------------------
# Content gathering
# ---------------------------------------------------------------------------

def _read_text(path: Path, limit: int = MAX_CONTEXT_CHARS) -> str:
    with open(path, "rb") as f:
        raw = f.read(limit * 2)
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            if enc == "utf-16" and not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                continue
            return text[:limit]
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")[:limit]


def _pdf_content(path: Path) -> Tuple[str, List[Tuple[bytes, str]]]:
    import pypdf
    reader = pypdf.PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return "[Encrypted PDF - content not readable]", []
    parts = []
    meta = reader.metadata or {}
    for key in ("/Title", "/Author", "/Subject", "/Creator"):
        val = meta.get(key) if hasattr(meta, "get") else None
        if val:
            parts.append(f"{key[1:]}: {val}")
    parts.append(f"Pages: {len(reader.pages)}")
    text = ""
    for page in reader.pages[:5]:
        try:
            text += (page.extract_text() or "") + "\n"
        except Exception:
            continue
        if len(text) > MAX_CONTEXT_CHARS:
            break
    images: List[Tuple[bytes, str]] = []
    if len(text.strip()) < 80 and reader.pages:
        # Scanned PDF: send the page image(s) instead
        try:
            for img in list(reader.pages[0].images)[:2]:
                images.append(_shrink_image_bytes(img.data))
        except Exception:
            pass
    return "\n".join(parts) + "\n\n" + text, images


def _docx_content(path: Path) -> str:
    import docx
    d = docx.Document(str(path))
    cp = d.core_properties
    head = [f"{k}: {v}" for k, v in (("Title", cp.title), ("Author", cp.author), ("Subject", cp.subject)) if v]
    paras = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables[:3]:
        for row in table.rows[:10]:
            paras.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(head + paras)


def _pptx_content(path: Path) -> str:
    from pptx import Presentation
    prs = Presentation(str(path))
    out = []
    for i, slide in enumerate(prs.slides, 1):
        texts = [sh.text_frame.text for sh in slide.shapes if getattr(sh, "has_text_frame", False) and sh.text_frame.text.strip()]
        if texts:
            out.append(f"[Slide {i}] " + " / ".join(texts))
        if i >= 15:
            break
    return "\n".join(out)


def _xlsx_content(path: Path) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    out = []
    if wb.properties and wb.properties.title:
        out.append(f"Title: {wb.properties.title}")
    for ws in wb.worksheets[:4]:
        out.append(f"[Sheet: {ws.title}]")
        for r, row in enumerate(ws.iter_rows(values_only=True)):
            vals = [str(v) for v in row if v is not None]
            if vals:
                out.append(" | ".join(vals)[:300])
            if r >= 20:
                break
    wb.close()
    return "\n".join(out)


def _archive_content(path: Path) -> str:
    names: List[str] = []
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
        elif tarfile.is_tarfile(path):
            with tarfile.open(path) as t:
                names = t.getnames()
    except Exception:
        pass
    if not names:
        return ""
    return f"Archive with {len(names)} entries:\n" + "\n".join(names[:80])


def _shrink_image_bytes(data: bytes) -> Tuple[bytes, str]:
    import io
    from PIL import Image
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        img.thumbnail((1536, 1536))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return buf.getvalue(), "image/jpeg"


def gather_file_content(path: Path, local_result: Any = None) -> Tuple[str, List[Tuple[bytes, str]]]:
    """Returns (text_context, images) describing the file for the model."""
    ext = path.suffix.lower()
    name_lower = path.name.lower()
    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    header = [f"Original filename: {path.name}", f"Extension: {ext or '(none)'}", f"Size: {size} bytes"]
    if local_result is not None:
        if getattr(local_result, "file_type", None):
            header.append(f"Detected type: {local_result.file_type}")
        if getattr(local_result, "title", None):
            header.append(f"Title found by local extractor: {local_result.title}")
        if getattr(local_result, "summary", None):
            header.append(f"Local metadata: {local_result.summary}")

    body = ""
    images: List[Tuple[bytes, str]] = []
    try:
        if ext == ".pdf":
            body, images = _pdf_content(path)
        elif ext == ".docx":
            body = _docx_content(path)
        elif ext == ".pptx":
            body = _pptx_content(path)
        elif ext in (".xlsx", ".xlsm"):
            body = _xlsx_content(path)
        elif ext in IMAGE_EXTS:
            from src.core.ai_vision import prepare_image_for_ai
            images.append(prepare_image_for_ai(path, max_dimension=1536))
        elif ext in VIDEO_EXTS:
            from src.core.ai_vision import extract_video_keyframe
            frame, mime, _ = extract_video_keyframe(path)
            if frame:
                images.append((frame, mime or "image/jpeg"))
        elif ext in (".zip", ".tar", ".gz", ".tgz", ".bz2", ".whl", ".jar", ".apk") or name_lower.endswith((".tar.gz", ".tar.bz2")):
            body = _archive_content(path)
        elif ext in TEXT_EXTS:
            body = _read_text(path)
    except Exception as e:
        body = f"[Could not read content: {e}]"

    text = "\n".join(header)
    if body.strip():
        text += "\n\n--- FILE CONTENT ---\n" + body.strip()[:MAX_CONTEXT_CHARS]
    return text, images


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

def _is_reasoning_model(model: str) -> bool:
    m = (model or "").lower()
    return m.startswith(("gpt-5", "o1", "o3", "o4"))


def _post(api_key: str, payload: Dict[str, Any], timeout: int) -> requests.Response:
    return cloud_gate.post(
        OPENAI_URL,
        headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )


def _error_message(resp: requests.Response) -> str:
    try:
        return resp.json().get("error", {}).get("message", resp.text)
    except Exception:
        return resp.text


def clean_title(raw: str) -> str:
    t = re.sub(r"[\"'`*#]+", " ", raw or "")
    t = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", t.strip())  # drop an extension the model may add
    return re.sub(r"\s+", " ", t).strip()


def generate_precise_title(
    path: Path,
    api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
    local_result: Any = None,
    timeout_seconds: int = 60,
) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Returns (title, error_message, details) where details has document_type / confidence.
    """
    if not (api_key or "").strip():
        return None, "OpenAI API key is not configured.", {}

    model = (model or DEFAULT_OPENAI_MODEL).strip()
    text, images = gather_file_content(path, local_result)

    content: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    for data, mime in images[:2]:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}", "detail": "high"},
        })

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        "max_completion_tokens": 2000,
    }
    if _is_reasoning_model(model):
        payload["reasoning_effort"] = "low"

    try:
        resp = _post(api_key, payload, timeout_seconds)
        if resp.status_code == 400 and "reasoning_effort" in payload and "reasoning" in _error_message(resp).lower():
            payload.pop("reasoning_effort")
            resp = _post(api_key, payload, timeout_seconds)
        if resp.status_code != 200:
            return None, f"OpenAI API error ({resp.status_code}): {_error_message(resp)}", {}

        choices = resp.json().get("choices") or []
        if not choices:
            return None, "OpenAI returned no answer.", {}
        msg = choices[0].get("message", {})
        if msg.get("refusal"):
            return None, f"OpenAI refused: {msg['refusal']}", {}
        data = json.loads(msg.get("content") or "{}")
        title = clean_title(data.get("title", ""))
        if len(title) < 2:
            return None, "OpenAI returned an empty title.", data
        return title, None, data

    except requests.exceptions.Timeout:
        return None, "OpenAI request timed out.", {}
    except requests.exceptions.RequestException as e:
        return None, f"Network error contacting OpenAI: {e}", {}
    except (ValueError, KeyError) as e:
        return None, f"Could not parse OpenAI answer: {e}", {}


def chat_json(
    api_key: str,
    model: str,
    system: str,
    user_text: str,
    schema: Dict[str, Any],
    timeout_seconds: int = 120,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Generic structured-JSON chat call. Returns (data, error)."""
    if not (api_key or "").strip():
        return None, "OpenAI API key is not configured."
    model = (model or DEFAULT_OPENAI_MODEL).strip()
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_text}],
        "response_format": {"type": "json_schema", "json_schema": schema},
        "max_completion_tokens": 16000,
    }
    if _is_reasoning_model(model):
        payload["reasoning_effort"] = "low"
    try:
        resp = _post(api_key, payload, timeout_seconds)
        if resp.status_code == 400 and "reasoning_effort" in payload and "reasoning" in _error_message(resp).lower():
            payload.pop("reasoning_effort")
            resp = _post(api_key, payload, timeout_seconds)
        if resp.status_code != 200:
            return None, f"OpenAI API error ({resp.status_code}): {_error_message(resp)}"
        msg = (resp.json().get("choices") or [{}])[0].get("message", {})
        if msg.get("refusal"):
            return None, f"OpenAI refused: {msg['refusal']}"
        return json.loads(msg.get("content") or "{}"), None
    except requests.exceptions.Timeout:
        return None, "OpenAI request timed out."
    except requests.exceptions.RequestException as e:
        return None, f"Network error contacting OpenAI: {e}"
    except (ValueError, KeyError) as e:
        return None, f"Could not parse OpenAI answer: {e}"


def verify_openai_api_key(api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> Tuple[bool, str]:
    if not (api_key or "").strip():
        return False, "Please enter an OpenAI API key."
    # Sends the key only, no file data; still needs cloud analysis to be switched on.
    permit = cloud_gate.issue("key-check", cloud_gate.PURPOSE_KEY_CHECK)
    if permit is None:
        return False, "Turn on cloud analysis in Privacy first."
    try:
        resp = cloud_gate.get(
            f"https://api.openai.com/v1/models/{model or DEFAULT_OPENAI_MODEL}",
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=15,
            permit=permit,
        )
    except requests.exceptions.RequestException as e:
        return False, f"Network error: {e}"
    if resp.status_code == 200:
        return True, f"OpenAI key works and model '{model}' is available."
    if resp.status_code == 404:
        return False, f"Key works, but model '{model}' is not available to your account."
    return False, f"OpenAI error ({resp.status_code}): {_error_message(resp)}"
