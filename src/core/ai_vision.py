"""
Google Gemini Vision API integration for intelligent image content analysis.
Transmits compressed image thumbnails to Google Generative Language API (opt-in only)
to derive concise, descriptive filenames from visual content (scenes, charts, diagrams, screenshots, products).
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

# Supported Gemini models with vision capabilities
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
SUPPORTED_GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]


def prepare_image_for_ai(image_path: Path, max_dimension: int = 1024) -> Tuple[bytes, str]:
    """
    Resizes the image to a safe max dimension and encodes it to JPEG bytes
    to minimize network payload while preserving full visual comprehension.
    """
    with Image.open(str(image_path)) as img:
        # Convert RGBA/P to RGB if needed for clean JPEG encoding
        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if larger than max_dimension
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue(), "image/jpeg"


def analyze_image_with_google_ai(
    image_path: Path,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
    timeout_seconds: int = 15
) -> Tuple[Optional[str], Optional[str]]:
    """
    Sends the image to Google Gemini Vision API and asks for a short descriptive title.
    Returns: (title, error_message)
    """
    if not api_key:
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

        # Auto-promote retired model names to modern active models
        if model in ("gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-flash"):
            model = "gemini-3.8-flash"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

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

        # Automatic fallback if configured model was deprecated
        if response.status_code == 404:
            for fallback_model in ("gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash"):
                if fallback_model != model:
                    fb_url = f"https://generativelanguage.googleapis.com/v1beta/models/{fallback_model}:generateContent?key={api_key}"
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

        # Clean title: strip quotes, markdown backticks, leading/trailing symbols
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
        return None, f"Unexpected error analyzing image: {str(e)}"


def verify_google_api_key(api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> Tuple[bool, str]:
    """Tests if a Google Gemini API key is valid by sending a tiny lightweight prompt."""
    clean_key = api_key.strip()
    if not clean_key:
        return False, "API key cannot be empty."

    # Auto-promote retired model names
    if model in ("gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-flash"):
        model = "gemini-3.8-flash"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
    payload = {
        "contents": [{"parts": [{"text": "Hello"}]}],
        "generationConfig": {"maxOutputTokens": 5}
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True, f"API Key is valid and successfully connected to Google Gemini ({model})!"
        else:
            try:
                err = resp.json().get("error", {}).get("message", resp.text)
            except Exception:
                err = resp.text

            # If 404 model not found, try available fallbacks
            if resp.status_code == 404 or "is no longer available" in err or "not found" in err:
                for fb in ("gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash"):
                    if fb != model:
                        fb_url = f"https://generativelanguage.googleapis.com/v1beta/models/{fb}:generateContent?key={clean_key}"
                        fb_resp = requests.post(fb_url, json=payload, timeout=10)
                        if fb_resp.status_code == 200:
                            return True, f"API Key is valid and successfully connected to Google Gemini ({fb})!"

            # If project denied access (403), provide actionable fix
            if "denied access" in err.lower() or "permission_denied" in err.lower() or resp.status_code == 403:
                return False, (
                    "Google Project Access Denied (403): Google verified your API key, but the Google Cloud / AI Studio "
                    "project where this key was generated has restricted access.\n\n"
                    "How to fix in 30 seconds:\n"
                    "1. Open https://aistudio.google.com/app/apikey in your browser.\n"
                    "2. Click '+ Create API key'.\n"
                    "3. Select 'Create API key in new project' (this creates a fresh, unrestricted project).\n"
                    "4. Copy the newly generated key and paste it here."
                )

            return False, f"API Key verification failed ({resp.status_code}): {err}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"
