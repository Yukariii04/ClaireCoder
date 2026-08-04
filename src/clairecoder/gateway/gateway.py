from typing import Dict, List, Optional
from .types import Model, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory, ModelProfile
from .interfaces import ModelGatewayInterface, ProviderAdapterInterface

class ModelGateway(ModelGatewayInterface):
    def __init__(self):
        self._adapters: Dict[str, ProviderAdapterInterface] = {}
        self._models: Dict[str, Model] = {}
        self._profiles: Dict[str, ModelProfile] = {}

    def register_adapter(self, adapter: ProviderAdapterInterface) -> None:
        self._adapters[adapter.provider_id] = adapter

    def register_model(self, model: Model) -> None:
        self._models[model.id] = model

    def register_profile(self, profile: ModelProfile) -> None:
        self._profiles[profile.id] = profile

    def resolve_profile(self, profile_id: str) -> Model:
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ModelError(
                category=ErrorCategory.MODEL_FAILURE,
                message=f"Profile not found: {profile_id}"
            )
        return self.get_model(profile.model_id)

    def get_model(self, model_id: str) -> Model:
        model = self._models.get(model_id)
        if not model:
            raise ModelError(
                category=ErrorCategory.MODEL_FAILURE,
                message=f"Model not found: {model_id}"
            )
        return model

    def check_capability(self, model_id: str, capability: Capability) -> bool:
        model = self.get_model(model_id)
        return capability in model.capabilities

    def execute(self, request: ModelRequest) -> ModelResponse:
        model = self.get_model(request.model_id)
        
        # Find adapter
        adapter = self._adapters.get(model.provider.id)
        if not adapter:
            raise ModelError(
                category=ErrorCategory.ENDPOINT_FAILURE,
                message=f"No adapter registered for provider: {model.provider.id}",
                provider_id=model.provider.id,
                model_id=request.model_id
            )
            
        try:
            # Delegate to provider adapter
            return adapter.execute(model, request)
        except ModelError:
            # Let ModelErrors propagate directly
            raise
        except Exception as e:
            # Wrap unexpected errors to maintain Gateway abstraction
            raise ModelError(
                category=ErrorCategory.UNKNOWN,
                message=f"Unexpected execution error: {str(e)}",
                provider_id=model.provider.id,
                model_id=model.id
            ) from e
