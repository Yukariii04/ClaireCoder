from abc import ABC, abstractmethod
from typing import List, Optional
from .types import Model, ModelRequest, ModelResponse, Capability, ModelProfile

class ProviderAdapterInterface(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """The unique identifier for this provider."""
        pass

    @abstractmethod
    def execute(self, model: Model, request: ModelRequest) -> ModelResponse:
        """Execute the request against the provider."""
        pass

class ModelGatewayInterface(ABC):
    @abstractmethod
    def register_adapter(self, adapter: ProviderAdapterInterface) -> None:
        """Register a provider adapter."""
        pass

    @abstractmethod
    def register_model(self, model: Model) -> None:
        """Register an available model."""
        pass
        
    @abstractmethod
    def register_profile(self, profile: ModelProfile) -> None:
        """Register a model profile."""
        pass

    @abstractmethod
    def resolve_profile(self, profile_id: str) -> Model:
        """Resolve a profile to its configured model."""
        pass

    @abstractmethod
    def get_model(self, model_id: str) -> Model:
        """Retrieve a model by ID."""
        pass

    @abstractmethod
    def check_capability(self, model_id: str, capability: Capability) -> bool:
        """Check if a model supports a specific capability."""
        pass

    @abstractmethod
    def execute(self, request: ModelRequest) -> ModelResponse:
        """Execute a normalized request through the gateway."""
        pass
