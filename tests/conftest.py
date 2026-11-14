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
    """For tests of the legacy cloud code paths (HTTP mocked): skip the permit check."""
    from src.privacy import cloud_gate
    monkeypatch.setattr(cloud_gate, "_check", lambda url, permit=None: None)


@pytest.fixture(autouse=True)
def cloud_switch_off():
    """The cloud switch starts OFF in every test, and permits never leak between tests."""
    from src.privacy import cloud_gate
    cloud_gate.set_enabled_provider(lambda: False)
    cloud_gate.revoke_all()
    yield
    cloud_gate.set_enabled_provider(lambda: False)
    cloud_gate.revoke_all()
