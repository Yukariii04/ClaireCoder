import time
from typing import Any, Callable, Dict, List, Optional
from .types import Model, ModelRequest, ModelResponse, Capability, ModelError, ErrorCategory, ModelProfile
from .interfaces import ModelGatewayInterface, ProviderAdapterInterface
from .errors import ProviderError, ProviderUnavailableError
from .reliability import ReliabilityConfig, ProviderHealthTracker, RetryExecutor

class ModelGateway(ModelGatewayInterface):
    def __init__(
        self,
        reliability_config: Optional[ReliabilityConfig] = None,
        event_emitter: Optional[Any] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
        time_fn: Optional[Callable[[], float]] = None,
    ):
        self._adapters: Dict[str, ProviderAdapterInterface] = {}
        self._models: Dict[str, Model] = {}
        self._profiles: Dict[str, ModelProfile] = {}
        self.last_request_debug: Optional[Dict[str, Any]] = None
        self.reliability_config = reliability_config or ReliabilityConfig()
        self.event_emitter = event_emitter
        self._sleep_fn = sleep_fn
        self._time_fn = time_fn or time.time
        self.health_tracker = ProviderHealthTracker(
            failure_threshold=self.reliability_config.failure_threshold_for_cooldown,
            cooldown_seconds=self.reliability_config.cooldown_seconds,
            time_fn=self._time_fn,
        )
        self.retry_executor = RetryExecutor(
            config=self.reliability_config,
            health_tracker=self.health_tracker,
            event_emitter=self.event_emitter,
            sleep_fn=self._sleep_fn,
            time_fn=self._time_fn,
        )

    def set_event_emitter(self, emitter: Any) -> None:
        """Set or update the runtime event emitter for provider lifecycle events."""
        self.event_emitter = emitter
        self.retry_executor.event_emitter = emitter

    def register_adapter(self, adapter: ProviderAdapterInterface) -> None:
        self._adapters[adapter.provider_id] = adapter

    def register_model(self, model: Model) -> None:
        self._models[model.id] = model

    def get_registered_model_ids(self) -> List[str]:
        """Return list of registered model IDs."""
        return list(self._models.keys())

    def list_models(self) -> List[Model]:
        """Return list of registered Model objects."""
        return list(self._models.values())

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
        if not model_id:
            raise ModelError(
                category=ErrorCategory.CONFIGURATION_ERROR,
                message="No active model configured. Use '/model' or the setup wizard to select a model."
            )
        if model_id in self._models:
            return self._models[model_id]
        if "/" in model_id:
            pid, mid = model_id.split("/", 1)
            candidate = self._models.get(mid)
            if candidate and candidate.provider and candidate.provider.id == pid:
                return candidate
        raise ModelError(
            category=ErrorCategory.MODEL_FAILURE,
            message=f"Model not found: {model_id}"
        )

    def check_capability(self, model_id: str, capability: Capability) -> bool:
        model = self.get_model(model_id)
        return capability in model.capabilities

    def execute(self, request: ModelRequest) -> ModelResponse:
        model = self.get_model(request.model_id)
        
        # Find adapter
        adapter = self._adapters.get(model.provider.id)
        if not adapter:
            raise ProviderError(
                category=ErrorCategory.ENDPOINT_FAILURE,
                message=f"No adapter registered for provider: {model.provider.id}",
                provider=model.provider.id,
                model=request.model_id,
                retryable=False,
            )

        # Record safe debug inspection hook
        self.last_request_debug = {
            "provider_id": model.provider.id,
            "endpoint": model.endpoint.url,
            "model_id": request.model_id,
            "adapter": adapter.__class__.__name__,
        }

        def _do_execute() -> ModelResponse:
            try:
                response = adapter.execute(model, request)
                return response
            except ModelError:
                raise
            except Exception as e:
                raise ProviderError(
                    category=ErrorCategory.UNKNOWN,
                    message=f"Unexpected execution error: {str(e)}",
                    provider=model.provider.id,
                    model=model.id,
                    retryable=False,
                ) from e

        return self.retry_executor.execute_with_retry(
            provider_id=model.provider.id,
            model_id=request.model_id,
            operation="chat" if not request.stream else "stream",
            func=_do_execute,
        )
