"""
AI Vision integration for intelligent image content analysis.
Supports Groq Cloud (Qwen 3.8 27B Vision, ultra-fast free tier)
and Google Gemini Vision (Gemini 3.8 Flash, opt-in).
Derives concise, descriptive filenames from visual content (scenes, charts, diagrams, screenshots, products).
"""

import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Optional, Tuple
import requests
from PIL import Image

# Supported AI Vision models
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

SUPPORTED_GROQ_MODELS = ["qwen/qwen3.8-27b"]
SUPPORTED_GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]


def detect_ai_provider(api_key: str, provider: str = "auto") -> str:
    """Determines whether to use Groq Cloud or Google Gemini based on key prefix or user preference."""
    p = (provider or "auto").strip().lower()
    if p in ("groq", "groq cloud", "groqcloud"):
        return "groq"
    if p in ("google", "gemini", "google gemini"):
        return "google"
    # Auto-detect from key prefix: Groq keys start with 'gsk_'
    if api_key and api_key.strip().startswith("gsk_"):
        return "groq"
    return "google"


def prepare_image_for_ai(image_path: Path, max_dimension: int = 1024) -> Tuple[bytes, str]:
    """
    Resizes the image to a safe max dimension and encodes it to JPEG bytes
    to minimize network payload while preserving full visual comprehension.
    """
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(str(image_path)) as img:
        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue(), "image/jpeg"


def analyze_image_with_groq(
    image_path: Path,
    api_key: str,
    model: str = DEFAULT_GROQ_MODEL,
    timeout_seconds: int = 15
) -> Tuple[Optional[str], Optional[str]]:
    """
    Sends the image to Groq Cloud Vision API (Qwen 3.8 27B Vision).
    Returns: (title, error_message)
    """
    clean_key = api_key.strip()
    if not clean_key:
        return None, "Groq API key is not configured."

    try:
        image_bytes, mime_type = prepare_image_for_ai(image_path)
        base64_data = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "Analyze this image and generate a short, descriptive, specific title in 2 to 5 words for a filename. "
            "Focus on the main subject, document title, product, diagram, screenshot, or scene "
            "(e.g., 'Eiffel_Tower_Sunset', 'Company_Revenue_Chart', 'User_Login_Screen', 'Golden_Retriever_Puppy', 'Math_Formula_Notes'). "
            "Return ONLY the plain title text with no punctuation, no markdown, and no extra explanation."
        )

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {clean_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or DEFAULT_GROQ_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_data}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 30,
            "temperature": 0.2
        }

        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)

        if response.status_code != 200:
            try:
                err_data = response.json()
                msg = err_data.get("error", {}).get("message", response.text)
            except Exception:
                msg = response.text
            return None, f"Groq API Error ({response.status_code}): {msg}"

        result_json = response.json()
        choices = result_json.get("choices", [])
        if not choices:
            return None, "No description returned by Groq AI."

        raw_title = choices[0].get("message", {}).get("content", "").strip()
        clean_title = re.sub(r'[\'"`*#_]+', ' ', raw_title).strip()
        clean_title = re.sub(r'\s+', ' ', clean_title)

        if len(clean_title) < 2:
            return None, "Groq AI generated an uninformative title."

        return clean_title, None

    except requests.exceptions.Timeout:
        return None, "Groq API request timed out."
    except requests.exceptions.RequestException as e:
        return None, f"Network error connecting to Groq API: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error analyzing image with Groq: {str(e)}"


def analyze_image_with_google(
    image_path: Path,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
    timeout_seconds: int = 15
) -> Tuple[Optional[str], Optional[str]]:
    """
    Sends the image to Google Gemini Vision API.
    Returns: (title, error_message)
    """
    clean_key = api_key.strip()
    if not clean_key:
        return None, "Google API key is not configured."

    try:
        image_bytes, mime_type = prepare_image_for_ai(image_path)
        base64_data = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "Analyze this image and generate a short, descriptive, specific title in 2 to 5 words for a filename. "
            "Focus on the main subject, document title, product, diagram, screenshot, or scene "
            "(e.g., 'Eiffel_Tower_Sunset', 'Company_Revenue_Chart', 'User_Login_Screen', 'Golden_Retriever_Puppy', 'Math_Formula_Notes'). "
            "Return ONLY the plain title text with no punctuation, no markdown, and no extra explanation."
        )

        if model in ("gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-flash"):
            model = DEFAULT_GEMINI_MODEL

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 40
            }
        }

        response = requests.post(url, json=payload, timeout=timeout_seconds)

        if response.status_code == 404:
            for fallback_model in ("gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash"):
                if fallback_model != model:
                    fb_url = f"https://generativelanguage.googleapis.com/v1beta/models/{fallback_model}:generateContent?key={clean_key}"
                    fb_resp = requests.post(fb_url, json=payload, timeout=timeout_seconds)
                    if fb_resp.status_code == 200:
                        response = fb_resp
                        break

        if response.status_code != 200:
            try:
                err_data = response.json()
                msg = err_data.get("error", {}).get("message", response.text)
            except Exception:
                msg = response.text
            return None, f"Google API Error ({response.status_code}): {msg}"

        result_json = response.json()
        candidates = result_json.get("candidates", [])
        if not candidates:
            return None, "No description returned by Google AI."

        content_parts = candidates[0].get("content", {}).get("parts", [])
        if not content_parts:
            return None, "Empty response from Google AI."

        raw_title = content_parts[0].get("text", "").strip()
        clean_title = re.sub(r'[\'"`*#_]+', ' ', raw_title).strip()
        clean_title = re.sub(r'\s+', ' ', clean_title)

        if len(clean_title) < 2:
            return None, "Google AI generated an uninformative title."

        return clean_title, None

    except requests.exceptions.Timeout:
        return None, "Google API request timed out."
    except requests.exceptions.RequestException as e:
        return None, f"Network error connecting to Google API: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error analyzing image with Google: {str(e)}"


def analyze_image_with_ai(
    image_path: Path,
    api_key: str,
    provider: str = "auto",
    model: Optional[str] = None,
    timeout_seconds: int = 15
) -> Tuple[Optional[str], Optional[str], str]:
    """
    Main dispatch function that routes to either Groq Cloud or Google Gemini.
    Returns: (title, error_message, provider_name)
    """
    active_provider = detect_ai_provider(api_key, provider)
    if active_provider == "groq":
        mod = model if (model and "qwen" in model) else DEFAULT_GROQ_MODEL
        title, err = analyze_image_with_groq(image_path, api_key, model=mod, timeout_seconds=timeout_seconds)
        return title, err, "Groq Cloud"
    else:
        mod = model if (model and "gemini" in model) else DEFAULT_GEMINI_MODEL
        title, err = analyze_image_with_google(image_path, api_key, model=mod, timeout_seconds=timeout_seconds)
        return title, err, "Google Gemini"


# Backward compatibility alias
analyze_image_with_google_ai = analyze_image_with_google


def verify_groq_api_key(api_key: str, model: str = DEFAULT_GROQ_MODEL) -> Tuple[bool, str]:
    """Validates a Groq Cloud API key."""
    clean_key = api_key.strip()
    if not clean_key:
        return False, "Groq API key cannot be empty."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model or DEFAULT_GROQ_MODEL,
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 5
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            return True, f"Groq Cloud API Key is valid and successfully connected to {model or DEFAULT_GROQ_MODEL}!"
        else:
            try:
                err = resp.json().get("error", {}).get("message", resp.text)
            except Exception:
                err = resp.text
            return False, f"Groq verification failed ({resp.status_code}): {err}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def verify_google_api_key(api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> Tuple[bool, str]:
    """Validates a Google Gemini API key."""
    clean_key = api_key.strip()
    if not clean_key:
        return False, "API key cannot be empty."

    if model in ("gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-flash"):
        model = DEFAULT_GEMINI_MODEL

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
    payload = {
        "contents": [{"parts": [{"text": "Hello"}]}],
        "generationConfig": {"maxOutputTokens": 5}
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True, f"Google API Key is valid and successfully connected to {model}!"
        else:
            try:
                err = resp.json().get("error", {}).get("message", resp.text)
            except Exception:
                err = resp.text

            if resp.status_code == 404 or "is no longer available" in err or "not found" in err:
                for fb in ("gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash"):
                    if fb != model:
                        fb_url = f"https://generativelanguage.googleapis.com/v1beta/models/{fb}:generateContent?key={clean_key}"
                        fb_resp = requests.post(fb_url, json=payload, timeout=10)
                        if fb_resp.status_code == 200:
                            return True, f"Google API Key is valid and successfully connected ({fb})!"

            if "denied access" in err.lower() or "permission_denied" in err.lower() or resp.status_code == 403:
                return False, (
                    "Google Project Access Denied (403): Your Google Cloud/AI Studio project has restricted access.\n"
                    "Fix: Open https://aistudio.google.com/app/apikey and click 'Create API key in new project', "
                    "or switch to Groq Cloud for instant free access."
                )

            return False, f"Google API Key verification failed ({resp.status_code}): {err}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def verify_ai_api_key(api_key: str, provider: str = "auto", model: Optional[str] = None) -> Tuple[bool, str]:
    """Validates the key against either Groq Cloud or Google Gemini."""
    active_provider = detect_ai_provider(api_key, provider)
    if active_provider == "groq":
        return verify_groq_api_key(api_key, model=model or DEFAULT_GROQ_MODEL)
    else:
        return verify_google_api_key(api_key, model=model or DEFAULT_GEMINI_MODEL)
