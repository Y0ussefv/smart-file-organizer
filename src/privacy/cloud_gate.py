"""
Single gate for every request that could reach an external AI service (spec V2 §10).

Nothing is sent without a Permit. A Permit is issued by CloudPolicy for ONE file,
after the local checks (PR-06, PR-12): cloud option on, file P0 without alert,
project not "always local", minimised excerpt available. The state of another file,
the last folder or an old authorisation never counts.

At sending time the gate checks again that the cloud option is still on: turning
it off stops every new request immediately, including ones already prepared (PR-22).
Any other code path (old whole-file titler, Groq / Gemini vision) has no permit and
is blocked: CloudBlocked is a RequestException, so callers fall back to local naming.
"""

import logging
import secrets as _secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Set

import requests

logger = logging.getLogger("SmartFileOrganizer")

PURPOSE_TITLE = "naming"        # minimised excerpt of one P0 file
PURPOSE_KEY_CHECK = "key_check"  # "Test" button: sends the key only, no file data


class CloudBlocked(requests.exceptions.RequestException):
    """Raised instead of sending anything to an external AI service."""


@dataclass(frozen=True)
class Permit:
    file_ref: str
    purpose: str
    token: str = field(default_factory=lambda: _secrets.token_hex(16))
    issued_at: float = field(default_factory=time.time)


_lock = threading.Lock()
_issued: Set[str] = set()
_enabled: Callable[[], bool] = lambda: False   # wired by the app to the user's cloud choice


def set_enabled_provider(provider: Callable[[], bool]) -> None:
    """The app connects the live "cloud analysis" switch here."""
    global _enabled
    _enabled = provider


def cloud_enabled() -> bool:
    try:
        return bool(_enabled())
    except Exception:
        return False  # fail closed


def cloud_allowed() -> bool:
    """Kept for callers that only need to know whether cloud is switched on at all."""
    return cloud_enabled()


def issue(file_ref: str, purpose: str = PURPOSE_TITLE) -> Optional[Permit]:
    """Only CloudPolicy should call this, after the per-file checks."""
    if not cloud_enabled():
        return None
    permit = Permit(file_ref=file_ref, purpose=purpose)
    with _lock:
        _issued.add(permit.token)
    return permit


def revoke_all() -> None:
    """Called when the user turns cloud analysis off (PR-22)."""
    with _lock:
        _issued.clear()


def _consume(permit: Optional[Permit]) -> None:
    with _lock:
        ok = permit is not None and permit.token in _issued
        if ok:
            _issued.discard(permit.token)  # one permit = one request
    if not ok or not cloud_enabled():
        # Log only the decision, never the payload or the file (PR-25).
        logger.info("Cloud request blocked")
        raise CloudBlocked("Cloud analysis is not authorised for this request.")


def _check(url: str, permit: Optional[Permit] = None) -> None:
    _consume(permit)


def post(url, *args, permit: Optional[Permit] = None, **kwargs):
    _check(url, permit)
    return requests.post(url, *args, **kwargs)


def get(url, *args, permit: Optional[Permit] = None, **kwargs):
    _check(url, permit)
    return requests.get(url, *args, **kwargs)
