"""Configuration persistence and management for provider/model profiles.

All configuration is stored in `.clairecoder/config/` relative to the workspace root.
Credentials are stored via CredentialStore (OS keyring) and only referenced by ID.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import ProviderProfile
from .credentials import CredentialStore

logger = logging.getLogger(__name__)


class ConfigurationManager:
    """Manages persistent provider/model configuration and credential references.

    Directory layout:
        .clairecoder/
            config/
                providers/
                    <profile_id>.json    — ProviderProfile (no secrets)
                active.json              — active provider + model selection
    """

    def __init__(self, workspace_root: Optional[str] = None, credential_store: Optional[CredentialStore] = None):
        root = Path(workspace_root) if workspace_root else Path.cwd()
        self._config_dir = root / ".clairecoder" / "config"
        self._providers_dir = self._config_dir / "providers"
        self._active_path = self._config_dir / "active.json"
        self._credential_store = credential_store or CredentialStore()

    @property
    def credential_store(self) -> CredentialStore:
        return self._credential_store

    # ── Provider Profile CRUD ───────────────────────────────────────────────

    def save_provider_profile(self, profile: ProviderProfile) -> None:
        """Persist a provider profile (no secrets are written to disk)."""
        self._providers_dir.mkdir(parents=True, exist_ok=True)
        path = self._providers_dir / f"{profile.id}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2)

    def load_provider_profile(self, profile_id: str) -> Optional[ProviderProfile]:
        """Load a single provider profile by ID."""
        path = self._providers_dir / f"{profile_id}.json"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return ProviderProfile.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Corrupt provider profile %s: %s", profile_id, e)
            return None

    def list_provider_profiles(self) -> List[ProviderProfile]:
        """Load all persisted provider profiles."""
        if not self._providers_dir.exists():
            return []
        profiles = []
        for path in sorted(self._providers_dir.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(ProviderProfile.from_dict(data))
            except Exception as e:
                logger.warning("Skipping corrupt profile %s: %s", path.name, e)
        return profiles

    def delete_provider_profile(self, profile_id: str) -> bool:
        """Delete a provider profile and its associated credential."""
        path = self._providers_dir / f"{profile_id}.json"
        deleted = False
        if path.exists():
            path.unlink()
            deleted = True
        # Remove credential
        self._credential_store.delete_credential(profile_id)
        # If this was the active provider, clear active state
        active = self._load_active()
        if active.get("provider_profile_id") == profile_id:
            self._save_active({})
        return deleted

    # ── Active Selection ────────────────────────────────────────────────────

    def set_active(self, provider_profile_id: str, model_id: str) -> None:
        """Set the currently active provider and model."""
        self._save_active({
            "provider_profile_id": provider_profile_id,
            "model_id": model_id,
        })

    def get_active(self) -> Dict[str, str]:
        """Get the currently active provider and model.

        Returns dict with keys: provider_profile_id, model_id (may be empty).
        """
        return self._load_active()

    def _save_active(self, data: Dict[str, Any]) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with self._active_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_active(self) -> Dict[str, str]:
        if not self._active_path.exists():
            return {}
        try:
            with self._active_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return {}

    # ── Aggregate Status ────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Returns True if at least one valid provider profile exists with an active selection."""
        active = self.get_active()
        if not active.get("provider_profile_id"):
            return False
        profile = self.load_provider_profile(active["provider_profile_id"])
        return profile is not None and profile.enabled

    def needs_repair(self) -> bool:
        """Returns True if configuration exists but is incomplete or invalid."""
        profiles = self.list_provider_profiles()
        if not profiles:
            return False
        active = self.get_active()
        if not active.get("provider_profile_id"):
            return True  # profiles exist but nothing is active
        profile = self.load_provider_profile(active["provider_profile_id"])
        if profile is None:
            return True  # active references a deleted profile
        return False
