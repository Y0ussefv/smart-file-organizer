"""Shared test setup."""

import pytest

from src.storage import secrets


@pytest.fixture(autouse=True)
def memory_secret_store():
    """Tests never read or write the real OS vault (Keychain / Credential Manager)."""
    previous = secrets.default_store()
    store = secrets.MemorySecretStore()
    secrets.set_default_store(store)
    yield store
    secrets.set_default_store(previous)


@pytest.fixture
def cloud_on(monkeypatch):
    """For tests of the cloud code paths (with a mocked HTTP layer): open the gate."""
    from src.privacy import cloud_gate
    monkeypatch.setattr(cloud_gate, "CLOUD_FEATURE_AVAILABLE", True)
