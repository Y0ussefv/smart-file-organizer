"""
Single gate for every request that could send file data to an external service
(OpenAI, Groq, Gemini...). Spec V2 §10: local first, cloud off by default, fail closed.

BeeOrganizer 1.4.2 is local only: cloud analysis stays blocked until the local
sensitivity detector (P0/P1/P2/INCONNU) and minimisation of V2 are in place.
Every HTTP call in openai_titler / ai_vision goes through post()/get() below, so
a forgotten code path cannot leak content: it raises CloudBlocked instead.
"""

import logging

import requests

logger = logging.getLogger("SmartFileOrganizer")

# Hard switch for this build. V2 replaces it with per-file checks (PR-12).
CLOUD_FEATURE_AVAILABLE = False


class CloudBlocked(requests.exceptions.RequestException):
    """Raised instead of sending anything to an external AI service.

    It is a RequestException, so existing network error handling falls back to
    local naming instead of crashing."""


def cloud_allowed() -> bool:
    """True only when this build allows sending data to an external AI service."""
    return bool(CLOUD_FEATURE_AVAILABLE)


def _check(url: str) -> None:
    if not cloud_allowed():
        # Log only the decision, never the payload or the file (PR-25).
        logger.info("Cloud request blocked (local-only mode)")
        raise CloudBlocked("Cloud analysis is disabled: BeeOrganizer works locally only.")


def post(url, *args, **kwargs):
    _check(url)
    return requests.post(url, *args, **kwargs)


def get(url, *args, **kwargs):
    _check(url)
    return requests.get(url, *args, **kwargs)
