"""Tests for Stage 7 OS Keyring Credential Store."""
import pytest
from unittest.mock import MagicMock, patch
from clairecoder.gateway.credentials import CredentialStore


def test_credential_store_lifecycle():
    """Verify storing, retrieving, and deleting credentials via CredentialStore."""
    store = CredentialStore(service_name="clairecoder-test")

    # Mock keyring backend to avoid mutating the real OS keychain during automated tests
    fake_keychain = {}

    def mock_set_password(service, username, password):
        fake_keychain[(service, username)] = password

    def mock_get_password(service, username):
        return fake_keychain.get((service, username))

    def mock_delete_password(service, username):
        if (service, username) in fake_keychain:
            del fake_keychain[(service, username)]
        else:
            import keyring.errors
            raise keyring.errors.PasswordDeleteError("Password not found")

    with patch("keyring.set_password", side_effect=mock_set_password), \
         patch("keyring.get_password", side_effect=mock_get_password), \
         patch("keyring.delete_password", side_effect=mock_delete_password):

        assert not store.has_credential("openai-main")
        assert store.get_credential("openai-main") is None

        ref = store.store_credential("openai-main", "sk-secret-12345")
        assert ref == "provider:openai-main"
        assert store.has_credential("openai-main")
        assert store.get_credential("openai-main") == "sk-secret-12345"

        # Verify distinct references for different providers
        store.store_credential("anthropic-main", "sk-ant-abcde")
        assert store.get_credential("anthropic-main") == "sk-ant-abcde"
        assert store.get_credential("openai-main") == "sk-secret-12345"

        # Delete credential
        assert store.delete_credential("openai-main") is True
        assert not store.has_credential("openai-main")
        assert store.get_credential("openai-main") is None

        # Deleting non-existent returns False without crashing
        assert store.delete_credential("non-existent") is False


def test_credential_store_check_backend_health_healthy():
    """Verify check_backend_health returns (True, backend_name, None) when keyring is operational."""
    mock_backend = MagicMock()
    type(mock_backend).__name__ = "WindowsCredentialManager"
    with patch("keyring.get_keyring", return_value=mock_backend):
        healthy, backend_name, err = CredentialStore.check_backend_health()
        assert healthy is True
        assert backend_name == "WindowsCredentialManager"
        assert err is None


def test_credential_store_check_backend_health_unusable():
    """Verify check_backend_health returns (False, backend_name, err) when keyring is fail/null."""
    mock_backend = MagicMock()
    type(mock_backend).__name__ = "fail.Keyring"
    with patch("keyring.get_keyring", return_value=mock_backend):
        healthy, backend_name, err = CredentialStore.check_backend_health()
        assert healthy is False
        assert "No recommended backend" in err


def test_ensure_backend_configures_keyring():
    """CredentialStore ensures a usable backend is set."""
    store = CredentialStore(service_name="clairecoder_test_bk")
    is_healthy, backend_name, err = store.check_backend_health()
    assert is_healthy is True
    assert err is None
    assert "fail" not in backend_name.lower()


