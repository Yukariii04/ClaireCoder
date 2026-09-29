from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

class Capability(str, Enum):
    TEXT = "text"
    TOOL_CALLING = "tool_calling"
    PARALLEL_TOOL_CALLING = "parallel_tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    JSON_SCHEMA = "json_schema"
    VISION = "vision"
    REASONING = "reasoning"
    STREAMING = "streaming"

@dataclass
class Provider:
    id: str
    name: str

@dataclass
class Endpoint:
    url: str
    headers: Dict[str, str] = field(default_factory=dict)

@dataclass
class Runtime:
    name: str

@dataclass
class Router:
    id: str

@dataclass
class Model:
    id: str
    display_name: str
    provider: Provider
    endpoint: Endpoint
    runtime: Optional[Runtime] = None
    router: Optional[Router] = None
    capabilities: List[Capability] = field(default_factory=list)
    context_capacity: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelProfile:
    id: str
    model_id: str
    fallback_model_id: Optional[str] = None
    reasoning_level: Optional[str] = None
    capabilities_required: List[Capability] = field(default_factory=list)

@dataclass
class ModelRequest:
    model_id: str
    messages: List[Dict[str, Any]]
    tools: Optional[List[Dict[str, Any]]] = None
    structured_output_schema: Optional[Dict[str, Any]] = None
    reasoning_level: Optional[str] = None
    stream: bool = False
    provider_specific: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelResponse:
    text: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    structured_output: Optional[Any] = None
    usage: Dict[str, int] = field(default_factory=dict)
    provider_specific: Dict[str, Any] = field(default_factory=dict)
    stream_generator: Optional[Any] = None

class ErrorCategory(str, Enum):
    AUTHENTICATION = "authentication"
    ENDPOINT_FAILURE = "endpoint_failure"
    NETWORK_FAILURE = "network_failure"
    TIMEOUT = "timeout"
    RATE_LIMITING = "rate_limiting"
    MODEL_FAILURE = "model_failure"
    CAPABILITY_MISMATCH = "capability_mismatch"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN = "unknown"

class ModelError(Exception):
    def __init__(
        self,
        category: Any = ErrorCategory.CONFIGURATION_ERROR,
        message: Optional[str] = None,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        is_recoverable: bool = False,
        provider_specific: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            if isinstance(category, str):
                message = category
                category = ErrorCategory.CONFIGURATION_ERROR
            else:
                message = str(category)
        super().__init__(message)
        self.category = category
        self.message = message
        self.provider_id = provider_id
        self.model_id = model_id
        self.is_recoverable = is_recoverable
        self.provider_specific = provider_specific or {}
