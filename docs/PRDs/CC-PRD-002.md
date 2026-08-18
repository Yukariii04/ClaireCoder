###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                     Product Requirements Document
#
# Document Number : CC-PRD-002
# Title           : ClaireCoder Model Gateway & Provider System
# Version         : 2.0.0
# Status          : FINAL
#
###############################################################################


# 1. Executive Summary

The ClaireCoder Model Gateway SHALL provide the model-execution boundary
between the Engineering Engine and all supported local, hosted, routed,
self-hosted, or custom model sources.

The Model Gateway SHALL allow ClaireCoder to operate independently of:

    - individual language models,
    - model providers,
    - hosting methods,
    - inference runtimes,
    - routers,
    - API formats.

The Model Gateway SHALL support a pluggable provider-adapter architecture.

The Gateway SHALL distinguish:

    Provider
        The service, vendor, gateway, or model-serving system exposing models.

    Protocol / Adapter
        The communication implementation used to access the provider.

    Endpoint
        The actual address used for model execution.

    Runtime
        The inference environment executing the model.

    Router
        An intermediary capable of selecting or routing to an execution source.

    Model
        The logical model exposed to the Engineering Engine.

The Gateway SHALL support both:

    Native Provider Adapters

and:

    Protocol-Compatible Adapters.

The Gateway SHALL support, at minimum, the following V1 provider/runtime
families:

    Cloud / Hosted Providers

        - Groq
        - OpenAI
        - Anthropic
        - Google Gemini
        - OpenRouter

    Local / Self-Hosted Runtimes and Gateways

        - Ollama
        - LM Studio
        - vLLM
        - OmniRoute

    Custom

        - user-defined compatible endpoints.

Groq, OpenAI, OpenRouter, and OmniRoute SHALL be representable through the
OpenAI-compatible adapter family where the selected endpoint conforms to that
protocol.

Anthropic and Gemini SHALL have dedicated native adapter paths.

The architecture SHALL remain extensible so that a new provider or runtime
can be added without modifying the Engineering Engine.

The Engineering Engine SHALL communicate with models only through the Model
Gateway.


-------------------------------------------------------------------------------

# 2. Product Goal

The goal of CC-PRD-002 is to provide ClaireCoder with a unified, extensible,
provider-independent model execution system.

A ClaireCoder installation SHALL be able to operate using:

    Local Model
        ↓
        ├── Ollama
        ├── LM Studio
        ├── vLLM
        ├── OmniRoute
        └── Other Compatible Runtime

    Hosted Model
        ↓
        ├── Groq
        ├── OpenAI
        ├── Anthropic
        ├── Google Gemini
        ├── OpenRouter
        └── Other Compatible Provider

    Routed Model
        ↓
        ├── OpenRouter
        ├── OmniRoute
        └── Future Routers

    Custom Endpoint
        ↓
        └── User-defined model service

through the same Model Gateway.

A user with only one available model SHALL be able to use ClaireCoder without
configuring multiple providers.

Multiple providers MAY coexist simultaneously.

A user SHALL be able to configure local and cloud model sources at the same
time.


-------------------------------------------------------------------------------

# 3. Problem Statement

Models are exposed through substantially different interfaces.

A model may be accessed through:

    - native provider APIs,
    - OpenAI-compatible APIs,
    - Anthropic-compatible APIs,
    - local inference servers,
    - self-hosted gateways,
    - model routers,
    - custom endpoints.

Providers also differ in:

    - authentication,
    - request schemas,
    - Tool calling,
    - reasoning controls,
    - structured output,
    - vision,
    - streaming,
    - context limits,
    - response formats,
    - provider-specific parameters.

The OpenAI-compatible wire format SHALL NOT be treated as the universal
provider architecture.

The Gateway SHALL therefore distinguish between:

    Protocol compatibility

and:

    Provider identity.

For example:

    Groq
    OpenAI
    OpenRouter
    OmniRoute

MAY use one OpenAI-compatible adapter when their selected endpoint supports
that protocol.

Meanwhile:

    Anthropic
    Gemini

SHALL use their respective native adapter paths.

If provider differences are handled directly by the Engineering Engine,
ClaireCoder becomes provider-dependent.

The Model Gateway SHALL therefore isolate those differences behind a stable
execution boundary.


-------------------------------------------------------------------------------

# 4. Scope

## 4.1 In Scope

This PRD covers:

    - Model Gateway core.
    - Model abstraction.
    - Provider abstraction.
    - Protocol / adapter abstraction.
    - Endpoint abstraction.
    - Runtime abstraction.
    - Router abstraction.
    - Model Profiles.
    - Provider Profiles.
    - Credential references.
    - Native provider adapters.
    - OpenAI-compatible adapter.
    - Anthropic-compatible support where applicable.
    - Local model support.
    - Local gateway support.
    - Custom endpoint support.
    - Model discovery.
    - Provider discovery where available.
    - Model capability representation.
    - Capability negotiation.
    - Reasoning configuration.
    - Tool calling.
    - Structured output.
    - Vision.
    - Context-capacity information.
    - Streaming.
    - Authentication abstraction.
    - Per-provider credential configuration.
    - Provider/model fallback.
    - Single-model configuration.
    - Multi-provider configuration.
    - Multi-model configuration.
    - Provider-specific parameter extensions.
    - Model selection.
    - Local/cloud coexistence.
    - Adapter conformance testing.


## 4.2 Out of Scope

This PRD SHALL NOT define:

    - language model training,
    - foundation-model development,
    - inference-engine implementation,
    - provider infrastructure,
    - Engineering Engine planning logic,
    - Workflow implementation,
    - Skill implementation,
    - Tool implementation,
    - final CLI/TUI model-selection UI,
    - final Desktop model-selection UI,
    - advanced automatic benchmarking,
    - advanced cost optimization,
    - enterprise credential administration,
    - distributed model orchestration infrastructure.

Those systems SHALL remain outside the Model Gateway implementation.


-------------------------------------------------------------------------------

# 5. Product Principles

## 5.1 Provider Independence

Provider-specific API logic SHALL NOT reach the Engineering Engine.

## 5.2 Model Independence

A Model SHALL remain a replaceable execution component.

Changing the active Model SHALL NOT require changing:

    - Skills,
    - Workflows,
    - Tools,
    - Engineering Engine logic.

## 5.3 Local-First Compatibility

Local models SHALL be first-class Model Gateway sources.

ClaireCoder SHALL NOT require cloud inference.

## 5.4 Multi-Provider by Design

Multiple providers SHALL be supported as a first-class configuration model.

The architecture SHALL NOT assume that only one provider or one credential
exists.

## 5.5 Single-Model Accessibility

A user SHALL be able to operate ClaireCoder with exactly one configured Model.

Multiple Models remain optional.

## 5.6 Capability Awareness

The Gateway SHALL represent actual Model capabilities rather than assuming
that Provider-level support applies to every Model.

## 5.7 Protocol / Provider Separation

The Gateway SHALL distinguish the provider identity from the communication
protocol.

A provider SHALL be able to reuse an existing adapter when its endpoint
conforms to the supported protocol.

## 5.8 Provider Feature Preservation

The common interface SHALL not remove important provider-specific capabilities
merely to maintain abstraction purity.

Provider-specific parameters SHALL remain accessible through controlled
extensions.

## 5.9 Transparent Model Changes

Material changes between Models SHALL be visible to the user.

ClaireCoder SHALL not silently replace a materially different Model when that
change may affect engineering behavior.

## 5.10 Simplicity

The V1 Model Gateway SHALL remain simple enough to add a provider, runtime,
router, or compatible endpoint without changing the Engineering Engine.


-------------------------------------------------------------------------------

# 6. Model Gateway Architecture

The conceptual architecture SHALL be:

                         ENGINEERING ENGINE
                                │
                                ▼
                         MODEL GATEWAY
                                │
                  ┌─────────────┼─────────────┐
                  │             │             │
                  ▼             ▼             ▼
              Provider       Adapter       Capability
              Registry       Registry       Registry
                  │             │
          ┌───────┼───────┐     │
          │       │       │     │
          ▼       ▼       ▼     ▼
        Native   Native  Native Compatibility
        APIs     APIs    APIs   Adapter Families
          │       │       │     │
          │       │       │     ├── OpenAI-compatible
          │       │       │     └── Anthropic-compatible
          │       │       │
          │       │       │
        OpenAI Anthropic Gemini
          │
          └──────────────────────────────────────┐
                                                 │
                       OpenAI-Compatible Family   │
                         ┌──────────┬──────────┬──┴─────────┐
                         │          │          │            │
                        Groq      OpenRouter OmniRoute    OpenAI
                         │          │          │
                         │          │          ├── local/self-hosted
                         │          │          │
                         │          │          └── routed
                         │          │
                         │          └── hosted router
                         │
                         └── hosted inference

Local runtimes:

    Ollama
    LM Studio
    vLLM

MAY also use the OpenAI-compatible adapter where their configured endpoint
supports that protocol.

The Engineering Engine SHALL communicate only with the Model Gateway.


-------------------------------------------------------------------------------

# 7. Model Abstraction

The Model Gateway SHALL represent a logical Model independently from its
execution source.

A Model SHOULD contain or reference:

    - model identifier,
    - display name,
    - provider,
    - adapter,
    - endpoint,
    - runtime,
    - router,
    - capabilities,
    - context capacity,
    - reasoning support,
    - configuration metadata.

The Model identifier SHALL NOT by itself determine the Provider, Runtime,
Endpoint, or Adapter.


-------------------------------------------------------------------------------

# 8. Provider Abstraction

A Provider SHALL represent the service, vendor, gateway, or model-serving
system exposing Models.

Initial supported providers/runtimes include:

    Cloud / Hosted:

        - Groq
        - OpenAI
        - Anthropic
        - Google Gemini
        - OpenRouter

    Local / Self-Hosted:

        - Ollama
        - LM Studio
        - vLLM
        - OmniRoute

    Custom:

        - User-defined provider profiles.

A Provider MAY expose multiple Models.

The Provider abstraction SHALL remain independent from the logical Model.

The Provider abstraction SHALL NOT imply a specific communication protocol.


-------------------------------------------------------------------------------

# 9. Protocol / Adapter Abstraction

The Model Gateway SHALL distinguish:

    Provider
        from
    Communication Adapter.

An Adapter SHALL provide the translation between the normalized Gateway
contract and a provider/API execution format.

Initial adapter families:

    OpenAICompatibleAdapter

    AnthropicNativeAdapter

    GeminiNativeAdapter

    FutureNativeAdapter

    FutureCompatibilityAdapter

A Provider MAY select an adapter based on its configured endpoint.

Examples:

    Groq
        → OpenAICompatibleAdapter

    OpenAI
        → OpenAICompatibleAdapter

    OpenRouter
        → OpenAICompatibleAdapter

    OmniRoute
        → OpenAICompatibleAdapter

    Anthropic
        → AnthropicNativeAdapter

    Gemini
        → GeminiNativeAdapter

    Ollama
        → OpenAICompatibleAdapter where configured endpoint is compatible

    LM Studio
        → OpenAICompatibleAdapter where configured endpoint is compatible

    vLLM
        → OpenAICompatibleAdapter where configured endpoint is compatible


-------------------------------------------------------------------------------

# 10. Endpoint Abstraction

An Endpoint SHALL represent the actual API location used for model execution.

Examples:

    Hosted Endpoint
        ↓
        Provider API

    Local Endpoint
        ↓
        http://localhost:<port>

    Custom Endpoint
        ↓
        User-defined base URL

An Endpoint SHALL be configurable independently from the logical Model.

An Endpoint MAY be:

    - cloud-hosted,
    - local,
    - LAN-hosted,
    - self-hosted,
    - router-backed.


-------------------------------------------------------------------------------

# 11. Runtime Abstraction

A Runtime SHALL represent the environment executing the Model.

Examples include:

    - cloud inference,
    - Ollama,
    - LM Studio,
    - vLLM,
    - self-hosted inference,
    - routed execution,
    - other compatible runtimes.

The Runtime SHALL remain distinct from the Provider.

A local Model MAY have:

    Model
      ↓
    Runtime
      ↓
    Endpoint
      ↓
    Adapter

without requiring a traditional cloud Provider.


-------------------------------------------------------------------------------

# 12. Router Abstraction

A Router SHALL represent an intermediary capable of selecting an execution
source.

A Router MAY provide:

    - provider selection,
    - model selection,
    - fallback,
    - capability routing,
    - availability routing,
    - latency preference,
    - cost preference,
    - throughput preference.

Initial supported routed systems include:

    OpenRouter

    OmniRoute

OpenRouter and OmniRoute SHALL remain distinct Provider/Router configurations.

They SHALL NOT be treated as the same service or project.

Routing SHALL remain optional.

A direct provider or local runtime SHALL remain valid without a Router.


-------------------------------------------------------------------------------

# 13. Adapter Architecture

The Model Gateway SHALL use a pluggable adapter architecture.

The conceptual structure SHALL be:

    Model Gateway
         │
         ├── Native Adapters
         │      ├── Anthropic
         │      └── Gemini
         │
         ├── Compatibility Adapters
         │      ├── OpenAI-Compatible
         │      └── Anthropic-Compatible where applicable
         │
         ├── Router-capable Provider Profiles
         │      ├── OpenRouter
         │      └── OmniRoute
         │
         └── Future Native / Compatibility Adapters

Each adapter SHALL translate between:

    normalized Model Gateway contract

and:

    selected provider/API protocol.

Adapters SHALL NOT own Engineering Engine logic.


-------------------------------------------------------------------------------

# 14. Native Provider Adapters

The initial native adapter paths SHALL include:

    Anthropic

    Google Gemini

The architecture SHALL remain open to future native adapters.

The native adapter SHALL preserve provider-specific capabilities when the
common abstraction cannot represent them without loss.


-------------------------------------------------------------------------------

# 15. OpenAI-Compatible Adapter

ClaireCoder SHALL provide a generic OpenAI-compatible adapter.

The adapter SHALL support:

    - base URL,
    - authentication reference,
    - model identifier,
    - optional headers,
    - capability metadata,
    - compatible request parameters,
    - streaming where supported.

The adapter family SHALL be reusable for compatible endpoints rather than
requiring a dedicated implementation for every Provider.

The initial supported compatible providers/runtimes SHALL include:

    - Groq
    - OpenAI
    - OpenRouter
    - OmniRoute
    - Ollama
    - LM Studio
    - vLLM
    - other compatible endpoints.


-------------------------------------------------------------------------------

# 16. Anthropic Adapter

ClaireCoder SHALL provide a dedicated Anthropic adapter.

The adapter SHALL handle native Anthropic:

    - authentication,
    - request format,
    - response format,
    - streaming format,
    - Tool calling,
    - reasoning/thinking controls where supported,
    - provider-specific metadata.

The Engineering Engine SHALL remain unaware of the native adapter details.


-------------------------------------------------------------------------------

# 17. Gemini Adapter

ClaireCoder SHALL provide a dedicated Gemini adapter.

The adapter SHALL handle native Gemini:

    - authentication,
    - request format,
    - response format,
    - streaming format,
    - Tool calling,
    - structured output,
    - vision,
    - reasoning configuration where supported,
    - provider-specific metadata.

Gemini SHALL NOT be forced through an OpenAI-compatible adapter merely for
implementation convenience.


-------------------------------------------------------------------------------

# 18. Local Runtime Support

Local inference SHALL be first-class.

V1 SHALL support the architecture required for:

    - Ollama,
    - LM Studio,
    - vLLM,
    - OmniRoute,
    - other compatible local endpoints.

The Gateway SHALL allow:

    Local endpoint
        ↓
    Local runtime / gateway
        ↓
    Adapter
        ↓
    Model Gateway
        ↓
    Engineering Engine

The Engineering Engine SHALL not need to know whether the active Model is
local, remote, or routed.


-------------------------------------------------------------------------------

# 19. OmniRoute

OmniRoute SHALL be represented as a distinct self-hosted local AI gateway.

The Gateway configuration SHALL permit an OmniRoute profile with a local
endpoint.

A typical default installation MAY expose an endpoint at:

    http://localhost:20128

The implementation SHALL NOT hard-code this port as a universal requirement.

The endpoint SHALL remain configurable.

OmniRoute SHALL remain distinct from OpenRouter.

ClaireCoder SHALL treat:

    OpenRouter
        and
    OmniRoute

as separate provider/router profiles even when both expose compatible APIs.


-------------------------------------------------------------------------------

# 20. OpenRouter

OpenRouter SHALL be represented as a hosted routed provider.

The Gateway SHALL support:

    - OpenRouter endpoint configuration,
    - model selection,
    - compatible request handling,
    - provider/model metadata,
    - streaming where supported,
    - fallback metadata where available.

OpenRouter SHALL NOT be conflated with OmniRoute.

The user SHALL be able to configure either or both independently.


-------------------------------------------------------------------------------

# 21. Custom Endpoint Support

Users SHALL be able to configure custom model endpoints without modifying
ClaireCoder source.

A custom endpoint MAY define:

    - endpoint URL,
    - adapter family,
    - API format,
    - model identifier,
    - authentication reference,
    - headers,
    - capability declarations,
    - provider-specific parameters.

A custom endpoint SHALL be registered through the Model Gateway configuration
system.

The configuration SHALL NOT require modification to the Engineering Engine.


-------------------------------------------------------------------------------

# 22. Model Discovery

The Model Gateway SHOULD support model discovery where the selected Provider,
Runtime, or Router exposes sufficient information.

Discovery MAY return:

    - model identifier,
    - display name,
    - provider,
    - runtime,
    - endpoint,
    - router,
    - context capacity,
    - Tool support,
    - vision support,
    - reasoning support,
    - structured-output support,
    - streaming support.

When discovery is unavailable, manual model configuration SHALL remain valid.


-------------------------------------------------------------------------------

# 23. Model Capabilities

The Gateway SHALL represent model capabilities separately from Model identity.

The capability system SHALL support at least:

    - text generation,
    - Tool calling,
    - parallel Tool calling,
    - structured output,
    - JSON schema,
    - vision,
    - reasoning,
    - streaming,
    - long context.

The architecture SHOULD remain extensible for:

    - embeddings,
    - audio,
    - image generation,
    - code execution,
    - computer-use capabilities.

A capability SHALL only be considered available when the selected Model and
execution path actually support it.


-------------------------------------------------------------------------------

# 24. Capability Negotiation

The Engineering Engine SHALL be able to provide capability requirements to
the Model Gateway.

Conceptually:

    Engineering Requirement
          ↓
    Model Gateway
          ↓
    Capability Check
          │
        ┌─┴─────────┐
        ▼           ▼
    Supported    Unsupported
        │           │
        ▼           ▼
    Execute     Alternative /
                Reconfiguration /
                User Decision

The Gateway SHALL not falsely advertise unsupported capabilities.


-------------------------------------------------------------------------------

# 25. Reasoning Configuration

The Model Gateway SHALL expose a normalized reasoning abstraction.

The user-facing abstraction MAY include:

    - minimal,
    - low,
    - medium,
    - high,
    - maximum where supported.

The Gateway SHALL translate these settings into provider-specific controls.

Potential provider mechanisms include:

    - reasoning effort,
    - thinking level,
    - thinking budget,
    - provider-specific parameters,
    - unsupported.

Provider-specific reasoning controls SHALL remain accessible through the
extension mechanism when necessary.


-------------------------------------------------------------------------------

# 26. Planning Versus Reasoning

Planning Depth SHALL remain separate from Model reasoning configuration.

Planning belongs to:

    Workflow / Planning System

Reasoning configuration belongs to:

    Model Gateway

A Planning Requirement MAY request stronger reasoning where supported.

The Model Gateway SHALL not become responsible for planning.


-------------------------------------------------------------------------------

# 27. Tool Calling

Tool calling SHALL be represented as a Model capability.

The Gateway SHALL normalize:

    - Tool definitions,
    - Tool calls,
    - Tool arguments,
    - Tool-call responses,
    - streaming Tool events where supported.

Provider-specific Tool behavior MAY remain accessible through adapter metadata.

Provider-level Tool support SHALL not automatically imply Model-level Tool
support.


-------------------------------------------------------------------------------

# 28. Structured Output

Structured output SHALL be represented as a Model capability.

The Gateway SHOULD support:

    - structured JSON,
    - JSON schema,
    - provider-native structured responses.

When a Provider does not support a requested structured-output mechanism, the
Gateway SHALL report the limitation.


-------------------------------------------------------------------------------

# 29. Vision

Vision SHALL be represented as a Model capability.

The capability MAY be required for:

    - screenshot analysis,
    - UI implementation,
    - visual debugging,
    - image-based requirements,
    - design references.

The Engineering Engine SHALL be able to determine whether the active Model can
satisfy a vision requirement.


-------------------------------------------------------------------------------

# 30. Context Capacity

The Model Gateway SHALL expose context-capacity information where available.

The Context Engine MAY use this information to determine:

    - repository context,
    - Skill loading,
    - Tool results,
    - session history,
    - planning artifacts.

Models with smaller context capacities SHALL remain valid ClaireCoder Models.

The Context Engine SHALL adapt context rather than automatically rejecting the
Model.


-------------------------------------------------------------------------------

# 31. Streaming

The Model Gateway SHALL support streaming where the selected execution path
supports it.

Streaming SHALL be capable of representing:

    - generated text,
    - Tool-call events,
    - Tool-call arguments,
    - completion,
    - errors,
    - provider-specific event information where necessary.

The Gateway SHOULD normalize common events while preserving provider-specific
information through extensions.


-------------------------------------------------------------------------------

# 32. Authentication

Authentication SHALL be handled by the Model Gateway configuration layer.

Supported mechanisms MAY include:

    - environment variables,
    - secure local credential storage,
    - API tokens,
    - provider-specific authentication,
    - custom headers,
    - local endpoint authentication,
    - no-auth local endpoints.

The Engineering Engine SHALL NOT directly manage provider credentials.

The credential model SHALL support multiple providers simultaneously.


-------------------------------------------------------------------------------

# 33. Credential Profiles

Credentials SHALL be stored and referenced per Provider/Profile rather than
through one global credential slot.

Conceptually:

    CredentialStore
        │
        ├── groq
        ├── openai
        ├── anthropic
        ├── gemini
        ├── openrouter
        └── omniroute / local profile

A Provider Profile MAY reference:

    - credential identifier,
    - endpoint,
    - adapter,
    - model,
    - runtime,
    - router.

Multiple Provider Profiles MAY coexist simultaneously.

Example:

    Profile A
        Provider: OpenAI
        Credential: openai-primary

    Profile B
        Provider: OmniRoute
        Endpoint: http://localhost:20128
        Credential: omniroute-local

Both profiles SHALL remain independently configurable.

The Model Gateway SHALL not assume that selecting one Profile deletes,
replaces, or invalidates other Profiles.


-------------------------------------------------------------------------------

# 34. Credential Isolation

Credentials SHALL remain separate from:

    - Skills,
    - Workflows,
    - repository files,
    - ordinary model context.

Raw credentials SHALL not be inserted into model prompts by default.

Credential references MAY be stored in configuration.

The actual secret SHOULD remain in the secure credential mechanism selected by
the application configuration architecture.

The Gateway SHALL never expose raw credentials in ordinary logs or error
messages.


-------------------------------------------------------------------------------

# 35. Provider Failure

The Model Gateway SHALL distinguish at least:

    - authentication failure,
    - endpoint failure,
    - network failure,
    - rate limiting,
    - model failure,
    - capability mismatch,
    - temporary provider failure,
    - protocol mismatch,
    - configuration failure.

The Gateway SHALL return structured failure information to the Engineering
Engine.


-------------------------------------------------------------------------------

# 36. Fallback Architecture

Fallback behavior SHALL support multiple levels.

## Provider Fallback

Use another configured Provider capable of satisfying the same requirement.

## Model Fallback

Use another compatible Model.

## Capability Fallback

Use another Model or execution strategy that satisfies the required
capability.

## Execution Fallback

Retry or recover from a transient execution failure.

The Engineering Engine SHALL determine the appropriate engineering response
after receiving the Gateway result.

The Gateway SHALL not silently replace a materially different Model.


-------------------------------------------------------------------------------

# 37. Transparent Fallback

ClaireCoder SHALL avoid silently switching to a materially different Model
when that change may affect engineering behavior.

The system SHOULD expose:

    - previous Model,
    - selected fallback,
    - Provider,
    - reason for fallback.

Routine transient retries MAY remain transparent when no meaningful Model
change occurs.


-------------------------------------------------------------------------------

# 38. Provider Profiles

The Model Gateway SHALL support Provider Profiles as a configuration
abstraction.

A Provider Profile MAY define:

    - provider identity,
    - adapter family,
    - endpoint,
    - runtime,
    - router,
    - credential reference,
    - default model,
    - available models,
    - capability metadata,
    - provider-specific parameters.

Profiles SHALL remain independent from:

    - Skills,
    - Workflows,
    - Modes.

Multiple Profiles MAY exist for the same Provider.

Example:

    openai-primary
    openai-secondary
    groq-fast
    omni-local
    gemini-primary


-------------------------------------------------------------------------------

# 39. Model Profiles

The Model Gateway SHALL support Model Profiles as a user-facing model
configuration abstraction.

A Model Profile MAY define:

    - preferred model,
    - Provider Profile,
    - endpoint,
    - runtime,
    - adapter,
    - router,
    - reasoning level,
    - fallback model,
    - capability requirements,
    - latency preference,
    - cost preference.

Profiles SHALL remain independent of:

    - Skills,
    - Workflows,
    - Modes.


-------------------------------------------------------------------------------

# 40. Single-Model Configuration

Single-model operation SHALL be a first-class configuration.

A user MAY configure:

    One Provider Profile
        ↓
    One Model Profile
        ↓
    All compatible ClaireCoder stages

ClaireCoder SHALL not require:

    - separate planning model,
    - separate coding model,
    - separate review model,
    - separate research model.

The same Model MAY operate with different reasoning settings or context
strategies across different tasks.


-------------------------------------------------------------------------------

# 41. Multi-Provider Configuration

Multi-provider operation SHALL be a first-class V1 capability.

A user MAY configure simultaneously:

    Groq
    OpenAI
    Anthropic
    Gemini
    OpenRouter
    Ollama
    LM Studio
    vLLM
    OmniRoute
    custom endpoints

without requiring duplicate Engineering Engine instances.

The active Model/Profile MAY be selected explicitly by the user or by an
approved selection/fallback mechanism.


-------------------------------------------------------------------------------

# 42. Multi-Model Configuration

When multiple Models are available, ClaireCoder MAY assign different Models to
different responsibilities.

Potential responsibilities include:

    - planning,
    - implementation,
    - review,
    - research,
    - vision,
    - summarization.

Multi-model operation SHALL remain optional.

The Gateway SHALL not assume that multiple paid subscriptions are available.


-------------------------------------------------------------------------------

# 43. Provider-Specific Extensions

The common Model Gateway interface SHALL expose normalized functionality.

Provider-specific parameters SHALL remain accessible through an extension
mechanism.

The extension mechanism MAY contain:

    - provider-specific request parameters,
    - provider-specific response metadata,
    - provider-specific reasoning controls,
    - provider-specific Tool behavior,
    - provider-specific capabilities,
    - provider-specific streaming metadata.

Provider-specific functionality SHALL not become mandatory for ordinary
ClaireCoder operation.


-------------------------------------------------------------------------------

# 44. Model Selection

The Model Gateway SHALL support Model selection based on:

    - requested Model,
    - Model Profile,
    - Provider Profile,
    - capability requirements,
    - Provider availability,
    - context capacity,
    - reasoning requirements,
    - user preference,
    - local/remote preference,
    - router availability.

Advanced automatic cost and latency optimization MAY be added later.

V1 SHALL prioritize predictable selection over complex optimization.


-------------------------------------------------------------------------------

# 45. Model Configuration Lifecycle

The conceptual lifecycle SHALL be:

    DISCOVER / CONFIGURE
            ↓
        VALIDATE
            ↓
         REGISTER
            ↓
     CAPABILITY DETECTION
            ↓
      MODEL AVAILABLE
            ↓
          SELECT
            ↓
         EXECUTE

A manually configured Model SHALL be able to enter the same lifecycle even when
automatic discovery is unavailable.


-------------------------------------------------------------------------------

# 46. Model Validation

Before a configured Model becomes available for ordinary Engineering Engine
use, the Model Gateway SHOULD validate:

    - endpoint accessibility,
    - authentication,
    - model identifier,
    - basic invocation,
    - declared capabilities where practical,
    - adapter compatibility.

Validation SHALL not require a full benchmark.


-------------------------------------------------------------------------------

# 47. Error Handling

The Gateway SHALL return structured errors.

Errors SHOULD include:

    - error category,
    - Provider,
    - Model,
    - Endpoint,
    - Adapter,
    - operation,
    - recoverability,
    - provider-specific information where useful.

The Gateway SHALL not expose raw credentials in error messages.


-------------------------------------------------------------------------------

# 48. Interface Contract

The Model Gateway SHALL expose a normalized interface to the Engineering Engine.

Conceptually, the interface SHALL support:

    MODEL DISCOVERY
    PROVIDER DISCOVERY
    MODEL SELECTION
    PROVIDER PROFILE SELECTION
    CAPABILITY QUERY
    MODEL INVOCATION
    STREAMING
    TOOL CALL HANDLING
    STRUCTURED OUTPUT
    ERROR REPORTING
    FALLBACK
    VALIDATION

The exact class names, function names, schemas, and transport mechanisms SHALL
be determined during implementation.


-------------------------------------------------------------------------------

# 49. Performance Requirements

The Model Gateway SHALL remain lightweight enough for local ClaireCoder
execution.

The V1 implementation SHALL not require:

    - a separate model gateway server,
    - microservices,
    - distributed queues,
    - Kubernetes,
    - a remote orchestration service.

The Gateway SHOULD operate as a local application subsystem.

Local provider endpoints MAY themselves be separate user-run processes.


-------------------------------------------------------------------------------

# 50. Compatibility Requirements

The Model Gateway SHALL remain compatible with:

    - hosted models,
    - local models,
    - self-hosted models,
    - model routers,
    - OpenAI-compatible endpoints,
    - Anthropic-compatible endpoints where applicable,
    - native Anthropic APIs,
    - native Gemini APIs,
    - custom endpoints,
    - future provider adapters.

Adding a new Provider SHALL not require changes to the Engineering Engine.


-------------------------------------------------------------------------------

# 51. Security Requirements

The Model Gateway SHALL:

    - isolate credentials,
    - avoid placing secrets in Model context,
    - respect Permission Engine boundaries,
    - prevent Provider configuration from bypassing security policy,
    - treat custom endpoints as configurable execution sources,
    - avoid storing raw credentials in normal logs,
    - maintain independent credential references per Provider Profile.

The Gateway SHALL not become an alternate Tool-permission system.


-------------------------------------------------------------------------------

# 52. Acceptance Criteria

CC-PRD-002 SHALL be considered successfully implemented when:

## AC-001 — Model Gateway Boundary

The Engineering Engine communicates with Models only through the Model
Gateway.

## AC-002 — Provider Independence

Provider-specific API logic is isolated within adapters.

## AC-003 — Adapter Architecture

Native and compatibility adapter families can coexist under the same Gateway.

## AC-004 — OpenAI-Compatible Family

A configurable OpenAI-compatible endpoint can be registered and used.

## AC-005 — Native Anthropic

A native Anthropic Model can be registered and invoked.

## AC-006 — Native Gemini

A native Gemini Model can be registered and invoked.

## AC-007 — Groq

A Groq Model can be configured and invoked through its supported adapter path.

## AC-008 — OpenAI

An OpenAI Model can be configured and invoked through its supported adapter
path.

## AC-009 — OpenRouter

An OpenRouter Model can be configured and invoked independently.

## AC-010 — OmniRoute

An OmniRoute local gateway can be configured as a distinct Provider/Router
Profile and used without conflating it with OpenRouter.

## AC-011 — Local Models

At least one supported local runtime can provide a Model through the same
Gateway interface.

## AC-012 — Local Runtime Family

The architecture can represent:

    Ollama
    LM Studio
    vLLM

through compatible local endpoint profiles where supported.

## AC-013 — Custom Endpoints

A user can register a custom endpoint without modifying ClaireCoder source.

## AC-014 — Model Identity

Model, Provider, Endpoint, Runtime, Adapter, and Router remain distinct
concepts.

## AC-015 — Capability Detection

The Gateway can represent and query Model capabilities.

## AC-016 — Capability Negotiation

The Gateway can report whether a selected Model satisfies a requested
capability.

## AC-017 — Reasoning Controls

Normalized reasoning settings can be mapped to supported Provider controls.

## AC-018 — Tool Calling

Supported Tool-calling Models can return normalized Tool-call information.

## AC-019 — Structured Output

Supported structured-output Models can be invoked through the Gateway.

## AC-020 — Vision

Vision capability can be represented and queried.

## AC-021 — Context Capacity

Model context capacity can be represented when available.

## AC-022 — Streaming

Supported execution paths can stream normalized Model events.

## AC-023 — Authentication

Provider credentials remain isolated from the Engineering Engine.

## AC-024 — Per-Provider Credentials

Multiple Provider Profiles can coexist with independent credential references.

## AC-025 — Single Model

ClaireCoder works with exactly one configured Model.

## AC-026 — Multi Provider

ClaireCoder can represent multiple configured Providers simultaneously.

## AC-027 — Multi Model

ClaireCoder can represent multiple configured Models.

## AC-028 — Model Profile

A Model Profile can select a preferred Model and associated configuration.

## AC-029 — Provider Profile

A Provider Profile can define Provider, adapter, endpoint, runtime/router, and
credential reference.

## AC-030 — Fallback

A Provider or Model failure can return structured fallback information.

## AC-031 — Provider Extension

Provider-specific parameters can be preserved without changing the common
Engineering Engine interface.

## AC-032 — Error Handling

Gateway failures are returned as structured errors.

## AC-033 — Adapter Extensibility

A new adapter can be added without modifying the Engineering Engine.

## AC-034 — Adapter Conformance

Every production adapter conforms to the normalized Gateway contract.

## AC-035 — Local/Cloud Coexistence

A local Model and cloud Model can be configured simultaneously and selected
independently.

## AC-036 — V1 Simplicity

The implementation does not require distributed model infrastructure.


-------------------------------------------------------------------------------

# 53. Provider Validation Matrix

Stage 7 SHALL validate the Provider architecture using at least:

    OpenAI-Compatible Family

        Required representative:
            Groq

    Native Family

        Required representative:
            Anthropic OR Gemini

The final V1 validation SHOULD include all explicitly supported providers:

    Groq
    OpenAI
    Anthropic
    Gemini
    OpenRouter
    OmniRoute
    Ollama
    LM Studio
    vLLM

Providers that are unavailable during CI or development MAY use mocked/fake
adapter tests, while live-provider integration tests SHALL be run where
credentials and services are available.

The architectural acceptance requirement is that both:

    compatibility adapter path

and:

    native adapter path

are independently proven.


-------------------------------------------------------------------------------

# 54. Non-Functional Requirements

## NFR-001 — Modularity

Provider adapters SHALL remain independently replaceable.

## NFR-002 — Extensibility

New Providers, runtimes, routers, and compatible endpoints SHOULD be addable
without modifying the Engineering Engine.

## NFR-003 — Predictability

Model selection SHALL remain deterministic when explicit user configuration
exists.

## NFR-004 — Capability Accuracy

The Gateway SHALL avoid claiming capabilities that the selected execution path
does not support.

## NFR-005 — Local Compatibility

The Gateway SHALL remain usable with local-only Model configurations.

## NFR-006 — Multi-Provider Compatibility

The Gateway SHALL support multiple configured Provider Profiles
simultaneously.

## NFR-007 — Resource Efficiency

The Gateway SHALL not require unnecessary background infrastructure.

## NFR-008 — Security

Credentials SHALL remain isolated from normal Model context and logs.

## NFR-009 — Observability

Model selection, fallback, capability mismatch, adapter failure, and execution
errors SHOULD be diagnosable.

## NFR-010 — Adapter Consistency

All adapters SHALL expose consistent normalized semantics for shared Gateway
operations.


-------------------------------------------------------------------------------

# 55. Deliverables

Implementation of CC-PRD-002 SHALL produce:

    1. Model Gateway core.
    2. Model abstraction.
    3. Provider abstraction.
    4. Protocol/adapter abstraction.
    5. Endpoint abstraction.
    6. Runtime abstraction.
    7. Router abstraction.
    8. Provider Profile support.
    9. Model Profile support.
    10. Credential reference support.
    11. Provider adapter interface.
    12. Native provider adapter framework.
    13. OpenAI-compatible adapter.
    14. Native Anthropic adapter.
    15. Native Gemini adapter.
    16. Local runtime integration.
    17. OpenRouter profile/integration.
    18. OmniRoute profile/integration.
    19. Custom endpoint support.
    20. Capability representation.
    21. Capability negotiation.
    22. Reasoning configuration.
    23. Tool-calling normalization.
    24. Structured-output support.
    25. Vision capability support.
    26. Context-capacity representation.
    27. Streaming support.
    28. Authentication configuration.
    29. Per-provider credential references.
    30. Fallback handling.
    31. Structured Gateway errors.
    32. Model discovery/configuration.
    33. Adapter conformance tests.
    34. Provider validation tests.
    35. Automated tests covering the Gateway lifecycle.


-------------------------------------------------------------------------------

# 56. Implementation Constraints

The implementation SHALL NOT:

    - place Provider-specific API logic inside the Engineering Engine,
    - require multiple paid Providers,
    - require cloud inference,
    - require a Router,
    - require a dedicated adapter for every OpenAI-compatible endpoint,
    - force native providers through an incompatible protocol adapter,
    - expose raw credentials to Skills or Workflows,
    - force every Provider into the lowest common denominator,
    - silently switch materially different Models,
    - require distributed infrastructure,
    - conflate OpenRouter and OmniRoute,
    - hard-code OmniRoute's endpoint as a universal fixed port,
    - make a single global credential the only configuration mechanism.


-------------------------------------------------------------------------------

# 57. Relationship With Other PRDs

## CC-PRD-001

ClaireCoder Core Engineering Engine.

Uses the Model Gateway as its model-execution boundary.

## CC-PRD-002

ClaireCoder Model Gateway & Provider System.

Defines:

    - Models,
    - Providers,
    - Adapters,
    - Endpoints,
    - Runtimes,
    - Routers,
    - Profiles,
    - Capabilities,
    - Credentials.

## CC-PRD-003

ClaireCoder Tool & Skill System.

Defines the executable Tool system and reusable Skill system that consume model
capabilities.

## CC-PRD-004

ClaireCoder Workflow, Context & Engineering Session System.

Defines Context, Workflow, Memory, and Engineering Sessions that interact with
Model capabilities.

## CC-PRD-005

ClaireCoder Interaction, Modes & Commands.

Defines how users configure and interact with Models, Modes, Commands, and
Sessions.

## CC-PRD-006

ClaireCoder Permission, Autonomy & Security.

Defines the security and authorization architecture governing execution.


-------------------------------------------------------------------------------

# 58. Implementation Order

The recommended implementation order for this PRD is:

    1. Model / Provider / Endpoint / Runtime / Router abstractions
            ↓
    2. Provider Profile and Credential Reference model
            ↓
    3. Adapter interface
            ↓
    4. Common invocation contract
            ↓
    5. Capability representation
            ↓
    6. OpenAI-compatible adapter
            ↓
    7. Native provider adapter framework
            ↓
    8. Anthropic adapter
            ↓
    9. Gemini adapter
            ↓
    10. Local runtime integration
            ↓
    11. OpenRouter integration
            ↓
    12. OmniRoute integration
            ↓
    13. Model Profiles
            ↓
    14. Reasoning configuration
            ↓
    15. Tool / structured-output normalization
            ↓
    16. Streaming
            ↓
    17. Authentication / secure credential integration
            ↓
    18. Fallback handling
            ↓
    19. Model discovery / validation
            ↓
    20. Provider / adapter conformance tests
            ↓
    21. Provider validation tests
            ↓
    22. Integration tests
            ↓
    23. Engineering Engine integration

The implementation SHALL validate the adapter architecture before expanding the
Provider list.


-------------------------------------------------------------------------------

# 59. Verification Strategy

## Unit Tests

Test:

    - Model representation,
    - Provider representation,
    - Endpoint configuration,
    - Runtime representation,
    - Router representation,
    - Provider Profile,
    - Model Profile,
    - credential references,
    - capability detection,
    - capability negotiation,
    - reasoning mapping,
    - fallback decisions,
    - error normalization.

## Adapter Tests

Test:

    - normalized adapter contract,
    - OpenAI-compatible adapter,
    - Anthropic adapter,
    - Gemini adapter,
    - local endpoint compatibility,
    - router-backed compatibility.

## Provider Tests

Test independently where practical:

    - Groq,
    - OpenAI,
    - Anthropic,
    - Gemini,
    - OpenRouter,
    - OmniRoute,
    - Ollama,
    - LM Studio,
    - vLLM.

Live tests MAY be credential/service dependent.

Mocked conformance tests SHALL remain provider-independent.

## Integration Tests

Test:

    - Gateway + Engineering Engine,
    - Gateway + local model,
    - Gateway + hosted model,
    - Gateway + native provider,
    - Gateway + compatibility provider,
    - Gateway + router,
    - Gateway + custom endpoint.

## Capability Tests

Test:

    - Tool calling,
    - structured output,
    - vision,
    - reasoning,
    - streaming,
    - context-capacity reporting.

## Configuration Tests

Test:

    - single-model configuration,
    - multi-provider configuration,
    - multi-model configuration,
    - Provider Profiles,
    - Model Profiles,
    - credential isolation,
    - local/cloud coexistence,
    - custom endpoint configuration.

## Failure Tests

Test:

    - authentication failure,
    - endpoint failure,
    - rate limiting,
    - unsupported capability,
    - provider failure,
    - adapter failure,
    - protocol mismatch,
    - fallback behavior.


-------------------------------------------------------------------------------

# 60. Out-of-Scope Implementation Decisions

This PRD SHALL NOT prematurely decide:

    - exact provider SDK libraries,
    - exact Python package structure,
    - exact secure credential-store implementation,
    - exact database technology,
    - exact Model Profile file format,
    - exact Provider Profile storage format,
    - exact adapter class names,
    - exact event transport,
    - exact routing algorithm,
    - exact cost optimization algorithm,
    - exact model benchmarking system.

These decisions SHALL be finalized through:

    CC-ADR-002

or implementation-level design where appropriate.


-------------------------------------------------------------------------------

# 61. Success Definition

ClaireCoder V1 satisfies CC-PRD-002 when the Engineering Engine can use a Model
without knowing:

    - which Provider exposes it,
    - which Adapter communicates with it,
    - where it is hosted,
    - which Runtime executes it,
    - whether a Router is involved,
    - which API format is used.

The resulting architecture SHALL allow:

    Engineering Engine
          │
          ▼
     Model Gateway
          │
     ┌────┼──────────────────────┐
     ▼    ▼          ▼           ▼
   Local Hosted    Native      Routed
   Model  Model    Provider     Model
     │      │          │           │
     └──────┴──────────┴───────────┘
                    │
                    ▼
                 Execution

while preserving Model capabilities and Provider-specific functionality.

The Gateway SHALL support local/cloud coexistence and multiple configured
Provider Profiles without duplicating the Engineering Engine.


-------------------------------------------------------------------------------

# 62. AI Instructions

When implementing CC-PRD-002:

    1. Treat the Model Gateway as the only model-execution boundary.
    2. Keep the Engineering Engine provider independent.
    3. Keep Model, Provider, Adapter, Endpoint, Runtime, and Router distinct.
    4. Use a pluggable Provider/Adapter architecture.
    5. Support native provider adapters.
    6. Support OpenAI-compatible endpoints.
    7. Support Anthropic-native APIs.
    8. Support Gemini-native APIs.
    9. Support local inference as a first-class configuration.
    10. Support Ollama.
    11. Support LM Studio.
    12. Support vLLM.
    13. Support OmniRoute as a distinct self-hosted gateway.
    14. Support OpenRouter as a distinct hosted routed provider.
    15. Never conflate OpenRouter with OmniRoute.
    16. Support custom endpoints.
    17. Preserve single-model operation.
    18. Preserve multi-provider operation.
    19. Preserve optional multi-model operation.
    20. Represent Model capabilities explicitly.
    21. Do not assume Provider capability equals Model capability.
    22. Preserve Tool calling capability.
    23. Preserve structured output capability.
    24. Preserve vision capability.
    25. Preserve streaming.
    26. Preserve context-capacity information.
    27. Keep Planning Depth separate from reasoning configuration.
    28. Normalize reasoning controls without hiding Provider-specific controls.
    29. Preserve Provider-specific parameters through extensions.
    30. Keep credentials outside normal Model context.
    31. Support multiple independent Provider credential references.
    32. Preserve transparent material Model changes.
    33. Keep fallback behavior structured.
    34. Do not create unnecessary distributed infrastructure.
    35. Keep the Gateway lightweight and extensible.
    36. Do not hard-code one universal OmniRoute port.
    37. Use adapter conformance tests before adding provider-specific special
        cases.
    38. Keep ClaireCoder independent from other Claire ecosystem projects.
    39. Treat this PRD as the authoritative product requirement for the Model
        Gateway unless explicitly superseded.


-------------------------------------------------------------------------------

# 63. V1 Design Lock

CC-PRD-002 defines the V1 Model Gateway product contract.

The following are locked:

    Provider
        ≠ Adapter
        ≠ Endpoint
        ≠ Runtime
        ≠ Router
        ≠ Model

    OpenAI-compatible
        = protocol/adapter family

    Native Anthropic
        = dedicated adapter path

    Native Gemini
        = dedicated adapter path

    Local runtimes
        = first-class Gateway sources

    OpenRouter
        = distinct hosted routed Provider

    OmniRoute
        = distinct self-hosted local gateway

    Credentials
        = independent per Provider/Profile references

    Engineering Engine
        = communicates only through Model Gateway

    Provider addition
        = SHALL NOT require Engineering Engine modification.

The Gateway SHALL preserve both abstraction and Provider-specific capabilities.

The product requirements, provider architecture, adapter boundaries, credential
model, and capability semantics SHALL remain stable unless this PRD is
explicitly superseded.


###############################################################################

END OF CC-PRD-002

###############################################################################