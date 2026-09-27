"""Provider Profile, Model Profile, and Configuration types for Stage 7.

Extends the existing gateway types with persistent provider configuration,
credential references, and multi-provider support.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ProviderCategory(str, Enum):
    """Classification of provider types for UX grouping."""
    HOSTED = "hosted"
    LOCAL = "local"
    CUSTOM = "custom"


class AdapterType(str, Enum):
    """Adapter implementation type."""
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    CUSTOM = "custom"


# Canonical provider registry — static metadata used by wizard and config.
# Each entry defines the provider's identity, default endpoint, adapter type,
# category, and authentication requirements.
PROVIDER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "adapter": AdapterType.OPENAI_COMPATIBLE,
        "category": ProviderCategory.HOSTED,
        "default_endpoint": "https://api.openai.com/v1",
        "requires_api_key": True,
        "description": "OpenAI API (GPT-4o, o1, o3, etc.)",
    },
    "groq": {
        "name": "Groq",
        "adapter": AdapterType.OPENAI_COMPATIBLE,
        "category": ProviderCategory.HOSTED,
        "default_endpoint": "https://api.groq.com/openai/v1",
        "requires_api_key": True,
        "description": "Groq Cloud (fast inference)",
    },
    "anthropic": {
        "name": "Anthropic",
        "adapter": AdapterType.ANTHROPIC,
        "category": ProviderCategory.HOSTED,
        "default_endpoint": "https://api.anthropic.com",
        "requires_api_key": True,
        "description": "Anthropic API (Claude 4, Opus, Sonnet, Haiku)",
    },
    "gemini": {
        "name": "Google Gemini",
        "adapter": AdapterType.GEMINI,
        "category": ProviderCategory.HOSTED,
        "default_endpoint": "https://generativelanguage.googleapis.com",
        "requires_api_key": True,
        "description": "Google Gemini API (Gemini 2.5 Pro, Flash, etc.)",
    },
    "openrouter": {
        "name": "OpenRouter",
        "adapter": AdapterType.OPENAI_COMPATIBLE,
        "category": ProviderCategory.HOSTED,
        "default_endpoint": "https://openrouter.ai/api/v1",
        "requires_api_key": True,
        "description": "OpenRouter (multi-provider model router)",
    },
    "omniroute": {
        "name": "OmniRoute",
        "adapter": AdapterType.OPENAI_COMPATIBLE,
        "category": ProviderCategory.HOSTED,
        "default_endpoint": "",
        "requires_api_key": True,
        "description": "OmniRoute (self-hosted model gateway)",
    },
    "ollama": {
        "name": "Ollama",
        "adapter": AdapterType.OLLAMA,
        "category": ProviderCategory.LOCAL,
        "default_endpoint": "http://localhost:11434",
        "requires_api_key": False,
        "description": "Ollama (local model runtime)",
    },
    "lmstudio": {
        "name": "LM Studio",
        "adapter": AdapterType.OPENAI_COMPATIBLE,
        "category": ProviderCategory.LOCAL,
        "default_endpoint": "http://localhost:1234/v1",
        "requires_api_key": False,
        "description": "LM Studio (local OpenAI-compatible server)",
    },
    "vllm": {
        "name": "vLLM",
        "adapter": AdapterType.OPENAI_COMPATIBLE,
        "category": ProviderCategory.LOCAL,
        "default_endpoint": "http://localhost:8000/v1",
        "requires_api_key": False,
        "description": "vLLM (high-performance inference engine)",
    },
    "custom": {
        "name": "Custom Endpoint",
        "adapter": AdapterType.CUSTOM,
        "category": ProviderCategory.CUSTOM,
        "default_endpoint": "",
        "requires_api_key": False,
        "description": "Custom OpenAI-compatible endpoint",
    },
}


@dataclass
class ProviderProfile:
    """Persistent provider configuration.

    Stored in `.clairecoder/config/providers/<provider_id>.json`.
    Credentials are referenced by ID — never stored inline.
    """
    id: str
    provider_id: str  # Key into PROVIDER_REGISTRY
    name: str
    adapter_type: str  # AdapterType value
    endpoint: str
    category: str  # ProviderCategory value
    credential_ref: Optional[str] = None  # keyring service+username reference
    default_model_id: Optional[str] = None
    available_models: List[str] = field(default_factory=list)
    capabilities: Dict[str, List[str]] = field(default_factory=dict)  # model_id -> [capability values]
    provider_specific: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "name": self.name,
            "adapter_type": self.adapter_type,
            "endpoint": self.endpoint,
            "category": self.category,
            "credential_ref": self.credential_ref,
            "default_model_id": self.default_model_id,
            "available_models": self.available_models,
            "capabilities": self.capabilities,
            "provider_specific": self.provider_specific,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderProfile":
        return cls(
            id=data["id"],
            provider_id=data["provider_id"],
            name=data["name"],
            adapter_type=data["adapter_type"],
            endpoint=data["endpoint"],
            category=data.get("category", ProviderCategory.HOSTED.value),
            credential_ref=data.get("credential_ref"),
            default_model_id=data.get("default_model_id"),
            available_models=data.get("available_models", []),
            capabilities=data.get("capabilities", {}),
            provider_specific=data.get("provider_specific", {}),
            enabled=data.get("enabled", True),
        )
