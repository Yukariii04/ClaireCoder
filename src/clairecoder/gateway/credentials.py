"""Secure credential storage using OS-level keyring.

Uses the `keyring` library for platform-native credential storage:
  - Windows: Windows Credential Manager
  - macOS: macOS Keychain
  - Linux: SecretService (GNOME Keyring / KDE Wallet)

Credentials are NEVER stored in plaintext files, logs, or config.
"""
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# Keyring service namespace for all ClaireCoder credentials
_SERVICE_NAME = "clairecoder"

# Module-level flag to ensure backend is configured once
_backend_configured: bool = False


class CredentialStore:
    """OS-level secure credential storage backed by keyring.

    Each provider has a distinct credential reference:
        service = "clairecoder"
        username = "provider:<provider_profile_id>"
        password = <the actual API key / token>
    """

    def __init__(self, service_name: str = _SERVICE_NAME):
        self._service = service_name
        self._ensure_backend()

    def _make_ref(self, provider_profile_id: str) -> str:
        """Generate the keyring username from a provider profile ID."""
        return f"provider:{provider_profile_id}"

    @staticmethod
    def _ensure_backend() -> None:
        """Ensure the OS keyring backend is properly configured.

        On Windows, keyring's entry-point discovery can fail in conda/venv
        environments, falling back to the unusable ``keyring.backends.fail.Keyring`` backend.
        This method detects that situation and explicitly sets the
        ``WinVaultKeyring`` (Windows Credential Manager) backend.
        """
        global _backend_configured
        if _backend_configured:
            return
        _backend_configured = True

        try:
            import keyring as kr
            backend = kr.get_keyring()
            backend_mod = getattr(backend.__class__, "__module__", "").lower()
            backend_name = getattr(backend.__class__, "__name__", "").lower()
            priority_val = getattr(backend, "priority", 1)
            is_usable_prio = not isinstance(priority_val, (int, float)) or priority_val > 0
            if not any(u in backend_mod or u in backend_name for u in ("fail", "null", "chainer")):
                if is_usable_prio:
                    return
            # On Windows, explicitly set WinVaultKeyring
            if sys.platform == "win32":
                try:
                    from keyring.backends.Windows import WinVaultKeyring
                    win_backend = WinVaultKeyring()
                    if win_backend.viable:
                        kr.set_keyring(win_backend)
                        logger.debug("Configured Windows Credential Manager backend")
                        return
                except Exception as e:
                    logger.debug("WinVaultKeyring not available: %s", e)
            # On macOS, try macOS Keychain
            elif sys.platform == "darwin":
                try:
                    from keyring.backends.macOS import Keyring as MacKeyring
                    mac_backend = MacKeyring()
                    if mac_backend.viable:
                        kr.set_keyring(mac_backend)
                        logger.debug("Configured macOS Keychain backend")
                        return
                except Exception as e:
                    logger.debug("macOS Keychain not available: %s", e)
            # On Linux, try SecretService
            else:
                try:
                    from keyring.backends.SecretService import Keyring as SSKeyring
                    ss_backend = SSKeyring()
                    if ss_backend.viable:
                        kr.set_keyring(ss_backend)
                        logger.debug("Configured SecretService backend")
                        return
                except Exception as e:
                    logger.debug("SecretService not available: %s", e)
        except ImportError:
            pass

    def store_credential(self, provider_profile_id: str, secret: str) -> str:
        """Store a credential securely. Returns the credential reference string."""
        import keyring as kr

        ref = self._make_ref(provider_profile_id)
        try:
            kr.set_password(self._service, ref, secret)
        except Exception as e:
            logger.error("Failed to store credential for %s: %s", provider_profile_id, e)
            raise RuntimeError(f"Credential storage failed: {e}") from e
        return ref

    def get_credential(self, provider_profile_id: str) -> Optional[str]:
        """Retrieve a stored credential. Returns None if not found."""
        import keyring as kr

        ref = self._make_ref(provider_profile_id)
        try:
            secret = kr.get_password(self._service, ref)
            return secret
        except Exception as e:
            logger.error("Failed to retrieve credential for %s: %s", provider_profile_id, e)
            return None

    def delete_credential(self, provider_profile_id: str) -> bool:
        """Delete a stored credential. Returns True if deleted, False on error."""
        import keyring as kr

        ref = self._make_ref(provider_profile_id)
        try:
            kr.delete_password(self._service, ref)
            return True
        except (kr.errors.PasswordDeleteError, Exception):
            return False

    def has_credential(self, provider_profile_id: str) -> bool:
        """Check if a credential exists for the given provider profile."""
        return self.get_credential(provider_profile_id) is not None

    @staticmethod
    def check_backend_health() -> tuple:
        """Check if the OS keyring backend is available and usable.

        Triggers _ensure_backend() first to attempt automatic recovery
        on platforms where keyring auto-detection fails (e.g., Windows conda).

        Returns:
            (is_healthy: bool, backend_name: str, error_message: str | None)
        """
        # Trigger automatic backend configuration before checking
        CredentialStore._ensure_backend()
        try:
            import keyring as kr
            backend = kr.get_keyring()
            backend_mod = getattr(backend.__class__, "__module__", "").lower()
            backend_name = getattr(backend.__class__, "__name__", "")
            # Reject known-unusable backends
            priority_val = getattr(backend, "priority", 1)
            is_unusable_prio = isinstance(priority_val, (int, float)) and priority_val <= 0
            if any(u in backend_mod or u in backend_name.lower() for u in ("fail", "null", "chainer")) or is_unusable_prio:
                return (False, backend_name, f"No recommended backend was available (got {backend_mod}.{backend_name}).")
            return (True, backend_name, None)
        except Exception as e:
            return (False, "unknown", f"Keyring backend check failed: {e}")
