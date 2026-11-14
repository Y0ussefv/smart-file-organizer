"""
API keys live in the operating system's secret vault, never in settings.json (spec PR-23):
macOS Keychain, Windows Credential Manager, Linux Secret Service (via `keyring`).

If the vault is not available the key is not stored at all (fail closed), and
nothing about the key is ever written to the logs.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger("SmartFileOrganizer")

SERVICE = "BeeOrganizer"
SECRET_KEYS = ("openai_api_key", "groq_api_key", "google_api_key")


class SecretStore:
    """OS vault through `keyring`."""

    def get(self, name: str) -> str:
        try:
            import keyring
            return keyring.get_password(SERVICE, name) or ""
        except Exception as e:
            logger.warning("Secret vault unavailable (%s)", type(e).__name__)
            return ""

    def set(self, name: str, value: str) -> bool:
        try:
            import keyring
            if value:
                keyring.set_password(SERVICE, name, value)
            else:
                try:
                    keyring.delete_password(SERVICE, name)
                except Exception:
                    pass  # nothing stored
            return True
        except Exception as e:
            logger.warning("Could not save %s in the secret vault (%s)", name, type(e).__name__)
            return False


class MemorySecretStore(SecretStore):
    """In-memory store for tests: never touches the real vault."""

    def __init__(self, data: Optional[Dict[str, str]] = None):
        self.data: Dict[str, str] = dict(data or {})

    def get(self, name: str) -> str:
        return self.data.get(name, "")

    def set(self, name: str, value: str) -> bool:
        if value:
            self.data[name] = value
        else:
            self.data.pop(name, None)
        return True


_default: SecretStore = SecretStore()


def default_store() -> SecretStore:
    return _default


def set_default_store(store: SecretStore) -> None:
    global _default
    _default = store
