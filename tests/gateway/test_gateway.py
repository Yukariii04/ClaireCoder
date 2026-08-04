import pytest
from clairecoder.gateway.types import (
    Model, Provider, Endpoint, Capability, ModelRequest, ModelResponse, 
    ModelError, ErrorCategory, ModelProfile
)
from clairecoder.gateway.gateway import ModelGateway
from clairecoder.gateway.adapters.openai import OpenAICompatibleAdapter

class MockHttpClient:
    def __init__(self, response_data=None, error_code=None, error_body=None):
        self.response_data = response_data
        self.error_code = error_code
        self.error_body = error_body
        self.last_request = None
        
    def post(self, url, headers, data):
        self.last_request = {"url": url, "headers": headers, "data": data}
        if self.error_code:
            import urllib.error
            from io import BytesIO
            resp = urllib.error.HTTPError(url, self.error_code, "Error", headers, BytesIO(self.error_body.encode()))
            raise resp
        return self.response_data

def test_gateway_registration_and_discovery():
    gateway = ModelGateway()
    
    provider = Provider(id="test-provider", name="Test Provider")
    endpoint = Endpoint(url="http://localhost:8080/v1")
    model = Model(
        id="test-model",
        display_name="Test Model",
        provider=provider,
        endpoint=endpoint,
        capabilities=[Capability.TEXT]
    )
    
    adapter = OpenAICompatibleAdapter(provider_id="test-provider")
    
    gateway.register_adapter(adapter)
    gateway.register_model(model)
    
    assert gateway.get_model("test-model").id == "test-model"
    assert gateway.check_capability("test-model", Capability.TEXT) == True
    assert gateway.check_capability("test-model", Capability.VISION) == False
    
    with pytest.raises(ModelError) as exc_info:
        gateway.get_model("unknown")
    assert exc_info.value.category == ErrorCategory.MODEL_FAILURE

def test_openai_adapter_execution():
    http_mock = MockHttpClient(
        response_data={
            "choices": [{"message": {"content": "Hello world!"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }
    )
    adapter = OpenAICompatibleAdapter(provider_id="test-provider", http_client=http_mock)
    
    provider = Provider(id="test-provider", name="Test Provider")
    endpoint = Endpoint(url="http://localhost:8080/v1")
    model = Model(id="test-model", display_name="Test Model", provider=provider, endpoint=endpoint)
    
    request = ModelRequest(model_id="test-model", messages=[{"role": "user", "content": "hi"}])
    
    response = adapter.execute(model, request)
    
    assert response.text == "Hello world!"
    assert response.usage["prompt_tokens"] == 10
    
    assert http_mock.last_request is not None
    assert http_mock.last_request["url"] == "http://localhost:8080/v1/chat/completions"

def test_gateway_execution_flow():
    gateway = ModelGateway()
    
    http_mock = MockHttpClient(
        response_data={
            "choices": [{"message": {"content": "Integration test passed"}, "finish_reason": "stop"}],
            "usage": {}
        }
    )
    adapter = OpenAICompatibleAdapter(provider_id="test-provider", http_client=http_mock)
    gateway.register_adapter(adapter)
    
    provider = Provider(id="test-provider", name="Test Provider")
    endpoint = Endpoint(url="http://test.local")
    model = Model(id="test-model", display_name="Test Model", provider=provider, endpoint=endpoint)
    gateway.register_model(model)
    
    request = ModelRequest(model_id="test-model", messages=[{"role": "user", "content": "test"}])
    response = gateway.execute(request)
    
    assert response.text == "Integration test passed"

def test_openai_adapter_error_handling():
    http_mock = MockHttpClient(error_code=401, error_body="Invalid API key")
    adapter = OpenAICompatibleAdapter(provider_id="test-provider", http_client=http_mock)
    provider = Provider(id="test-provider", name="Test")
    endpoint = Endpoint(url="http://localhost:8080/v1")
    model = Model(id="m1", display_name="m1", provider=provider, endpoint=endpoint)
    request = ModelRequest(model_id="m1", messages=[])
    
    with pytest.raises(ModelError) as exc_info:
        adapter.execute(model, request)
    assert exc_info.value.category == ErrorCategory.AUTHENTICATION

def test_gateway_profiles():
    gateway = ModelGateway()
    model = Model(id="m1", display_name="M1", provider=Provider(id="p1", name="P1"), endpoint=Endpoint(url="url"))
    gateway.register_model(model)
    
    profile = ModelProfile(id="pro1", model_id="m1")
    gateway.register_profile(profile)
    
    resolved = gateway.resolve_profile("pro1")
    assert resolved.id == "m1"
    
    with pytest.raises(ModelError):
        gateway.resolve_profile("unknown")

def test_structured_output():
    http_mock = MockHttpClient(
        response_data={
            "choices": [{"message": {"content": "{\"key\": \"value\"}"}}],
            "usage": {}
        }
    )
    adapter = OpenAICompatibleAdapter(provider_id="test-provider", http_client=http_mock)
    
    provider = Provider(id="test-provider", name="Test Provider")
    endpoint = Endpoint(url="http://localhost:8080/v1")
    model = Model(id="test-model", display_name="Test Model", provider=provider, endpoint=endpoint)
    
    request = ModelRequest(model_id="test-model", messages=[], structured_output_schema={"type": "object"})
    response = adapter.execute(model, request)
    
    assert response.structured_output == {"key": "value"}
    
    # Test invalid json
    http_mock.response_data = {"choices": [{"message": {"content": "invalid json"}}]}
    with pytest.raises(ModelError) as exc:
        adapter.execute(model, request)
    assert exc.value.category == ErrorCategory.ENDPOINT_FAILURE
    assert exc.value.provider_id == "test-provider"

class MockStreamHttpClient:
    def post_stream(self, url, headers, data):
        return [
            b'data: {"choices": [{"delta": {"content": "hello "}}]}\n',
            b'data: {"choices": [{"delta": {"content": "world"}}]}\n',
            b'data: [DONE]\n'
        ]

def test_streaming():
    http_mock = MockStreamHttpClient()
    adapter = OpenAICompatibleAdapter(provider_id="test-provider", http_client=http_mock)
    model = Model(id="m1", display_name="m1", provider=Provider(id="p1", name="p1"), endpoint=Endpoint(url="url"))
    request = ModelRequest(model_id="m1", messages=[], stream=True)
    
    response = adapter.execute(model, request)
    assert response.stream_generator is not None
    
    chunks = list(response.stream_generator)
    assert len(chunks) == 2
    assert chunks[0].text == "hello "
    assert chunks[1].text == "world"
