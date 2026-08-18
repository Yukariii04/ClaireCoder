###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-002
# Title           : Model Gateway & Provider Architecture
# Version         : 2.0.0
# Status          : FINAL
#
###############################################################################


# 1. Decision Summary

ClaireCoder SHALL use a dedicated Model Gateway as the only model-execution
boundary between the Engineering Engine and external, local, self-hosted, or
routed models.

The Model Gateway SHALL support:

    - native provider adapters,
    - protocol-compatible adapters,
    - OpenAI-compatible endpoints,
    - local inference runtimes,
    - self-hosted gateways,
    - model routers,
    - custom endpoints.

The Engineering Engine SHALL NOT contain provider-specific API logic.

ClaireCoder SHALL distinguish:

    - Model,
    - Provider,
    - Adapter,
    - Endpoint,
    - Runtime,
    - Router,
    - Provider Profile,
    - Model Profile.

The Model Gateway SHALL expose normalized model capabilities while preserving
provider-specific options through an extension mechanism.

ClaireCoder SHALL support:

    - single-model operation,
    - multi-model operation,
    - multi-provider operation,
    - local/cloud coexistence.

A user SHALL NOT be required to have access to multiple paid model providers.

Local models SHALL be first-class citizens of the architecture.


-------------------------------------------------------------------------------

# 2. Context

Modern models can be accessed through substantially different interfaces.

Examples include:

    - native provider APIs,
    - OpenAI-compatible APIs,
    - Anthropic-compatible APIs,
    - local inference servers,
    - self-hosted gateways,
    - model routers,
    - custom endpoints.

The same logical Model may also be accessible through different Providers,
Endpoints, Runtimes, or Routers.

Provider APIs differ in:

    - authentication,
    - Tool calling,
    - reasoning controls,
    - structured output,
    - vision,
    - streaming,
    - context limits,
    - request formats,
    - response formats,
    - provider-specific parameters.

The OpenAI-compatible protocol is useful, but it is NOT the universal
provider architecture.

The system therefore requires:

    Protocol compatibility
        +
    Native provider support
        +
    Local runtime support
        +
    Router support.

The Model Gateway SHALL isolate these differences without forcing the
Engineering Engine to understand them.


-------------------------------------------------------------------------------

# 3. Problem

Without a dedicated Model Gateway, ClaireCoder would become tightly coupled
to individual providers and execution systems.

An unsuitable architecture would resemble:

    Engineering Engine
        ↓
    OpenAI API
        ↓
    Anthropic API
        ↓
    Gemini API
        ↓
    Ollama API
        ↓
    OpenRouter API
        ↓
    OmniRoute

This would spread provider-specific logic throughout the system.

It would also make it difficult to:

    - add a new provider,
    - replace a provider,
    - use a local model,
    - use a self-hosted gateway,
    - use a custom endpoint,
    - route between providers,
    - detect capabilities,
    - implement fallback,
    - maintain single-model operation,
    - maintain multiple provider configurations.

The architecture therefore requires one stable Model Gateway boundary.


-------------------------------------------------------------------------------

# 4. Decision

ClaireCoder SHALL implement:

                              ENGINEERING ENGINE
                                     │
                                     ▼
                              MODEL GATEWAY
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
                Provider          Adapter          Profile
                Registry          Registry          Registry
                    │                │
          ┌─────────┼─────────┐      │
          │         │         │      │
          ▼         ▼         ▼      ▼
       Native     Native    Native  Compatible
       Adapter    Adapter   Adapter  Adapter
          │         │         │      │
       Anthropic  Gemini   Future   OpenAI-Compatible
                                  │
              ┌───────────────────┼─────────────────────┐
              │         │         │         │           │
             Groq     OpenAI   OpenRouter OmniRoute   Local
                                                       │
                                              ┌────────┼────────┐
                                              │        │        │
                                            Ollama   LM Studio vLLM

The Engineering Engine SHALL communicate only with the Model Gateway.

The Engineering Engine SHALL never communicate directly with a Provider,
Runtime, Router, or Adapter implementation.


-------------------------------------------------------------------------------

# 5. Model Identity

ClaireCoder SHALL distinguish a logical Model from its execution source.

A Model represents the model requested by the Engineering Engine.

A Model MAY reference:

    - model identifier,
    - display name,
    - Provider,
    - Adapter,
    - Endpoint,
    - Runtime,
    - Router,
    - capabilities,
    - context capacity,
    - reasoning support,
    - configuration metadata.

The Model identifier SHALL NOT by itself determine the Provider, Endpoint,
Runtime, Router, or Adapter.


-------------------------------------------------------------------------------

# 6. Provider Identity

A Provider represents the service, vendor, gateway, or model-serving system
exposing one or more Models.

The initial supported Provider/Runtime ecosystem SHALL include:

    Hosted / Cloud:

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

        - user-defined Providers / Endpoints.

A Provider MAY expose multiple Models.

Provider identity SHALL remain separate from protocol compatibility.


-------------------------------------------------------------------------------

# 7. Adapter Identity

An Adapter represents the communication implementation translating between the
normalized Model Gateway contract and an execution API.

The architecture SHALL support:

    Native Adapters

        - Anthropic
        - Gemini
        - future native Providers

    Compatibility Adapters

        - OpenAI-compatible
        - Anthropic-compatible where applicable
        - future compatibility families

An Adapter SHALL NOT own Engineering Engine orchestration.

An Adapter SHALL only translate and normalize provider/runtime interaction.


-------------------------------------------------------------------------------

# 8. Provider / Adapter Separation

Provider identity SHALL NOT automatically determine Adapter identity.

Example:

    Groq
        → OpenAI-Compatible Adapter

    OpenAI
        → OpenAI-Compatible Adapter

    OpenRouter
        → OpenAI-Compatible Adapter

    OmniRoute
        → OpenAI-Compatible Adapter

    Ollama
        → OpenAI-Compatible Adapter where endpoint supports it

    LM Studio
        → OpenAI-Compatible Adapter where endpoint supports it

    vLLM
        → OpenAI-Compatible Adapter where endpoint supports it

    Anthropic
        → Native Anthropic Adapter

    Gemini
        → Native Gemini Adapter

A Provider MAY use another Adapter in the future if the configured endpoint
requires it.


-------------------------------------------------------------------------------

# 9. Endpoint

An Endpoint represents the actual API address used for Model execution.

Examples:

    Hosted:
        https://provider.example/api

    Local:
        http://localhost:<port>

    LAN:
        http://192.168.x.x:<port>

    Custom:
        user-defined base URL

The Endpoint SHALL be configurable independently from the logical Model.

The architecture SHALL NOT hard-code a single endpoint for all Providers.


-------------------------------------------------------------------------------

# 10. Runtime

A Runtime represents the environment executing the Model.

Examples include:

    - cloud inference,
    - Ollama,
    - LM Studio,
    - vLLM,
    - self-hosted inference,
    - local gateways,
    - routed execution.

Runtime SHALL remain distinct from Provider.

A local Model MAY therefore be represented as:

    Model
      ↓
    Runtime
      ↓
    Endpoint
      ↓
    Adapter


-------------------------------------------------------------------------------

# 11. Router

A Router represents an intermediary capable of selecting an execution source.

A Router MAY provide:

    - provider selection,
    - model selection,
    - fallback,
    - capability routing,
    - availability routing,
    - latency optimization,
    - cost optimization,
    - throughput preference.

Routing SHALL remain optional.

A direct Provider or local Runtime SHALL remain valid without a Router.


-------------------------------------------------------------------------------

# 12. OpenRouter

OpenRouter SHALL be represented as a distinct hosted routed Provider.

The architecture SHALL allow:

    OpenRouter
        ↓
    OpenAI-Compatible Adapter
        ↓
    Configured hosted model

OpenRouter SHALL remain a separate identity from OmniRoute.

It SHALL NOT be represented as the same Provider or Runtime as OmniRoute.


-------------------------------------------------------------------------------

# 13. OmniRoute

OmniRoute SHALL be represented as a distinct self-hosted local AI gateway.

A typical local endpoint MAY be:

    http://localhost:20128

The port SHALL remain configurable.

The architecture SHALL NOT hard-code `20128` as a universal requirement.

OmniRoute MAY expose an OpenAI-compatible endpoint and therefore MAY use the
OpenAI-compatible Adapter.

OmniRoute SHALL remain distinct from OpenRouter.

The conceptual relationship is:

    OmniRoute
        ↓
    local gateway/router
        ↓
    selected execution source
        ↓
    Model Gateway


-------------------------------------------------------------------------------

# 14. Local Runtime Architecture

Local inference SHALL be first-class.

Initial local runtime targets include:

    - Ollama,
    - LM Studio,
    - vLLM,
    - OmniRoute,
    - other compatible local runtimes.

Local runtimes SHALL use the same Model Gateway abstraction as hosted models.

The Engineering Engine SHALL not need to know whether execution is:

    local,
    cloud,
    self-hosted,
    or routed.


-------------------------------------------------------------------------------

# 15. OpenAI-Compatible Adapter

ClaireCoder SHALL provide a generic OpenAI-compatible Adapter.

The Adapter SHALL support configuration of:

    - base URL,
    - credential reference where required,
    - model identifier,
    - optional headers,
    - capability metadata,
    - compatible request parameters,
    - streaming behavior.

The Adapter MAY serve:

    - Groq,
    - OpenAI,
    - OpenRouter,
    - OmniRoute,
    - Ollama,
    - LM Studio,
    - vLLM,
    - other compatible endpoints.

ClaireCoder SHALL NOT require a dedicated Adapter implementation for every
OpenAI-compatible endpoint.


-------------------------------------------------------------------------------

# 16. Native Anthropic Adapter

ClaireCoder SHALL provide a dedicated native Anthropic Adapter.

The Adapter SHALL be responsible for:

    - authentication,
    - request translation,
    - response normalization,
    - streaming normalization,
    - Tool calling,
    - reasoning/thinking controls where supported,
    - Provider-specific metadata.

Anthropic-specific API behavior SHALL remain inside this Adapter.


-------------------------------------------------------------------------------

# 17. Native Gemini Adapter

ClaireCoder SHALL provide a dedicated native Gemini Adapter.

The Adapter SHALL be responsible for:

    - authentication,
    - request translation,
    - response normalization,
    - streaming normalization,
    - Tool calling,
    - structured output,
    - vision,
    - reasoning controls where supported,
    - Provider-specific metadata.

Gemini SHALL NOT be forced through an OpenAI-compatible Adapter merely for
implementation convenience.


-------------------------------------------------------------------------------

# 18. Custom Adapter / Endpoint

Users SHALL be able to configure custom model endpoints.

A custom configuration MAY define:

    - endpoint URL,
    - adapter family,
    - API format,
    - model identifier,
    - credential reference,
    - headers,
    - capabilities,
    - provider-specific parameters.

A custom endpoint SHALL NOT require modification of the Engineering Engine.


-------------------------------------------------------------------------------

# 19. Provider Profile

ClaireCoder SHALL introduce a Provider Profile as a persistent/configuration
abstraction.

A Provider Profile MAY define:

    - Provider identity,
    - Adapter,
    - Endpoint,
    - Runtime,
    - Router,
    - Credential reference,
    - default Model,
    - available Models,
    - capability metadata,
    - Provider-specific parameters.

Multiple Provider Profiles MAY exist for the same Provider.

Examples:

    openai-primary
    openai-secondary
    groq-fast
    anthropic-main
    gemini-main
    openrouter-main
    omni-local
    ollama-local
    lmstudio-local


-------------------------------------------------------------------------------

# 20. Model Profile

ClaireCoder SHALL continue to support Model Profiles.

A Model Profile MAY define:

    - preferred Model,
    - Provider Profile,
    - reasoning level,
    - fallback Model,
    - capability requirements,
    - latency preference,
    - cost preference.

The Model Profile SHALL remain a user-facing abstraction.

It SHALL NOT replace the underlying Model Gateway entities.


-------------------------------------------------------------------------------

# 21. Credential Architecture

Credentials SHALL be associated with Provider Profiles rather than one global
credential slot.

Conceptually:

    Credential Store
        │
        ├── groq-primary
        ├── openai-primary
        ├── anthropic-primary
        ├── gemini-primary
        ├── openrouter-primary
        └── local / omni profile

The same installation MAY contain multiple credentials simultaneously.

Example:

    Provider Profile:
        openai-primary
        credential_ref = openai-primary

    Provider Profile:
        omni-local
        endpoint = http://localhost:20128
        credential_ref = omni-local

Selecting one Profile SHALL NOT delete, replace, or invalidate another.

Credential values SHALL remain below the Model Gateway configuration boundary.


-------------------------------------------------------------------------------

# 22. Credential Security

Raw Provider credentials SHALL NOT be exposed to:

    - Engineering Engine,
    - Skills,
    - Workflows,
    - normal Model context,
    - ordinary logs,
    - frontend presentation state.

The preferred persistent storage mechanism SHALL be the operating system
secure credential store as established by the Desktop architecture.

Environment variables MAY remain a supported configuration mechanism.

Credential references SHALL be safe to expose to ordinary configuration code
without exposing the secret value itself.


-------------------------------------------------------------------------------

# 23. Model Capabilities

The Model Gateway SHALL expose capabilities separately from Model identity.

Capabilities MAY include:

    - text generation,
    - Tool calling,
    - parallel Tool calling,
    - structured output,
    - JSON schema,
    - vision,
    - reasoning,
    - streaming,
    - long context,
    - embeddings,
    - audio,
    - image generation,
    - code execution,
    - computer-use capabilities.

The actual selected Model and execution path SHALL determine capability
availability.

Provider-wide capability declarations SHALL NOT automatically apply to every
Model.


-------------------------------------------------------------------------------

# 24. Capability Negotiation

When the Engineering Engine requires a capability, it SHALL be able to query
the Model Gateway.

Conceptually:

    Engineering Requirement
            ↓
    Model Gateway
            ↓
    Capability Check
            │
       ┌────┴────┐
       ▼         ▼
    Supported  Unsupported
       │         │
       ▼         ▼
    Execute    Alternative /
               Reconfiguration /
               User Decision

The Gateway SHALL not falsely advertise unsupported capabilities.


-------------------------------------------------------------------------------

# 25. Reasoning

The Model Gateway SHALL expose normalized reasoning controls.

The user-facing abstraction MAY include:

    minimal
    low
    medium
    high
    maximum

where supported.

The Gateway SHALL translate these into provider-specific mechanisms.

Provider-specific reasoning parameters SHALL remain available through Adapter
extensions where required.

Planning Depth SHALL remain owned by the Workflow system and SHALL not be
implemented inside the Model Gateway.


-------------------------------------------------------------------------------

# 26. Tool Calling

Tool calling SHALL be represented as a Model capability.

The Gateway SHALL normalize:

    - Tool definitions,
    - Tool calls,
    - Tool arguments,
    - Tool results,
    - streaming Tool events where supported.

Provider-specific Tool behavior MAY remain available through Adapter metadata.

Provider-level Tool support SHALL NOT imply Model-level Tool support.


-------------------------------------------------------------------------------

# 27. Structured Output

Structured output SHALL be represented as a capability.

The Gateway SHOULD support:

    - JSON,
    - JSON schema,
    - provider-native structured output.

Unsupported mechanisms SHALL be reported rather than falsely emulated.


-------------------------------------------------------------------------------

# 28. Vision

Vision SHALL be represented as a Model capability.

The Engineering Engine SHALL be able to determine whether the active Model
satisfies a required vision capability.

Possible responses to unsupported vision MAY include:

    - Model switch,
    - Profile switch,
    - Workflow adaptation,
    - user intervention.


-------------------------------------------------------------------------------

# 29. Context Capacity

The Model Gateway SHALL expose context-capacity information where available.

The Context Engine MAY use it to determine:

    - repository context,
    - Skill loading,
    - Tool results,
    - session history,
    - planning artifacts.

Models with smaller context capacities SHALL remain valid.


-------------------------------------------------------------------------------

# 30. Streaming

The Model Gateway SHALL support streaming where the selected execution path
supports it.

Normalized streaming SHALL support:

    - generated text,
    - Tool-call events,
    - Tool arguments,
    - completion,
    - errors.

Provider-specific event metadata MAY remain available through Adapter
extensions.


-------------------------------------------------------------------------------

# 31. Failure Model

The Model Gateway SHALL distinguish:

    - authentication failure,
    - endpoint failure,
    - network failure,
    - rate limiting,
    - Model failure,
    - capability mismatch,
    - protocol mismatch,
    - Adapter failure,
    - configuration failure,
    - temporary Provider failure.

The Gateway SHALL return structured failure information.

The Engineering Engine SHALL determine the appropriate engineering response.


-------------------------------------------------------------------------------

# 32. Fallback

Fallback SHALL support:

    Provider Fallback
        Use another configured Provider.

    Model Fallback
        Use another compatible Model.

    Capability Fallback
        Use another Model satisfying the requirement.

    Execution Fallback
        Retry or recover from a transient failure.

The Gateway SHALL NOT silently switch to a materially different Model when
that change may alter engineering behavior.

Material Model changes SHOULD be visible to the user.


-------------------------------------------------------------------------------

# 33. Single-Model Operation

Single-model operation SHALL remain fully supported.

A user may configure:

    Provider Profile
        ↓
    Model Profile
        ↓
    One Model
        ↓
    All compatible ClaireCoder stages

Multiple subscriptions SHALL NOT be required.


-------------------------------------------------------------------------------

# 34. Multi-Provider / Multi-Model Operation

Multiple Provider Profiles MAY coexist simultaneously.

Multiple Model Profiles MAY coexist simultaneously.

The system MAY assign different Models to:

    - planning,
    - implementation,
    - review,
    - research,
    - vision,
    - summarization.

This remains optional.

The architecture SHALL work for users with a single Model as well.


-------------------------------------------------------------------------------

# 35. Model Selection

Model selection MAY consider:

    - explicit Model selection,
    - Model Profile,
    - Provider Profile,
    - capability requirements,
    - Provider availability,
    - context capacity,
    - reasoning requirements,
    - user preference,
    - local/remote preference,
    - Router availability.

Explicit user configuration SHALL take precedence over speculative automatic
optimization.


-------------------------------------------------------------------------------

# 36. Model Discovery

Discovery SHOULD be supported where a Provider, Runtime, or Router exposes
sufficient information.

Discovery MAY provide:

    - Model identifier,
    - display name,
    - Provider,
    - Runtime,
    - Endpoint,
    - Router,
    - capabilities,
    - context capacity,
    - Tool support,
    - vision support,
    - reasoning support,
    - streaming support.

Manual configuration SHALL remain valid when discovery is unavailable.


-------------------------------------------------------------------------------

# 37. Model Configuration Lifecycle

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

Manual configurations SHALL use the same lifecycle.


-------------------------------------------------------------------------------

# 38. Interface Contract

The Model Gateway SHALL expose a normalized interface to the Engineering
Engine supporting, conceptually:

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

Exact class names and schemas SHALL be determined during implementation.


-------------------------------------------------------------------------------

# 39. Compatibility

The architecture SHALL remain compatible with:

    - hosted Models,
    - local Models,
    - self-hosted Models,
    - OpenAI-compatible endpoints,
    - native Anthropic APIs,
    - native Gemini APIs,
    - routed Models,
    - custom endpoints,
    - future Providers.

Adding a new Provider SHALL NOT require Engineering Engine modification.


-------------------------------------------------------------------------------

# 40. Security Boundary

The Model Gateway SHALL:

    - isolate credentials,
    - prevent secrets from entering Model context,
    - preserve Permission Engine boundaries,
    - prevent Provider configuration from becoming an alternate security system,
    - avoid raw credentials in normal logs.

Provider configuration SHALL not bypass Tool authorization.


-------------------------------------------------------------------------------

# 41. Alternatives Considered

## Alternative A — Direct Provider Calls

    REJECTED.

Provider-specific logic would spread into the Engineering Engine.

## Alternative B — OpenAI-Compatible Only

    REJECTED.

Not all required Providers expose the same API semantics.

Native Anthropic and Gemini adapters are therefore required.

## Alternative C — One Adapter Per Provider

    REJECTED.

This duplicates implementations for compatible endpoints.

## Alternative D — Router-Only

    REJECTED.

ClaireCoder must work with direct Providers and local runtimes without a Router.

## Alternative E — One Global Credential

    REJECTED.

Users may simultaneously configure multiple Providers and local gateways.

## Alternative F — Treat OpenRouter and OmniRoute as the Same Provider

    REJECTED.

They are distinct systems with different deployment models and ownership.


-------------------------------------------------------------------------------

# 42. Consequences

## Positive

    - Strong provider independence.
    - First-class local inference.
    - Native support for incompatible APIs.
    - Reuse of compatibility adapters.
    - Multiple providers can coexist.
    - Multiple credentials can coexist.
    - OpenRouter and OmniRoute remain distinct.
    - Custom endpoints remain possible.
    - Cleaner Engineering Engine.
    - Easier provider expansion.

## Negative

    - Adapter interfaces require maintenance.
    - Capability normalization adds complexity.
    - Provider-specific testing is required.
    - Local and cloud environments behave differently.
    - Fallback design requires careful validation.
    - Credential/profile configuration becomes richer.

These costs are accepted because provider independence and local-first
compatibility are core ClaireCoder requirements.


-------------------------------------------------------------------------------

# 43. V1 Boundary

The following SHALL be part of the V1 Model Gateway architecture:

    - Model Gateway
    - Provider abstraction
    - Adapter abstraction
    - OpenAI-compatible adapter
    - native Anthropic adapter
    - native Gemini adapter
    - Model abstraction
    - Endpoint abstraction
    - Runtime abstraction
    - Router abstraction
    - Provider Profile
    - Model Profile
    - credential references
    - local endpoint support
    - OpenRouter support
    - OmniRoute support
    - custom endpoint support
    - capability representation
    - capability negotiation
    - streaming
    - Tool capability representation
    - reasoning capability representation
    - context-capacity representation
    - authentication abstraction

The following MAY remain optional extensions:

    - advanced automatic routing,
    - automatic cost optimization,
    - advanced latency optimization,
    - complex provider scoring,
    - automatic model benchmarking,
    - advanced model recommendation.

ClaireCoder SHALL remain fully functional without those features.


-------------------------------------------------------------------------------

# 44. Implementation Guidance

The Model Gateway SHOULD initially favor:

    - explicit Provider interfaces,
    - explicit Adapter interfaces,
    - explicit capability structures,
    - simple Adapter implementations,
    - structured Model responses,
    - normalized streaming events,
    - deterministic error types,
    - configuration-driven endpoints,
    - independent Provider Profiles,
    - adapter conformance tests.

The implementation SHALL avoid:

    - embedding Provider logic into the Engineering Engine,
    - forcing every Provider into identical behavior,
    - requiring a Router,
    - requiring multiple Models,
    - requiring cloud inference,
    - creating unnecessary distributed infrastructure,
    - conflating OpenRouter and OmniRoute.


-------------------------------------------------------------------------------

# 45. Verification Strategy

## Architecture Tests

Verify:

    - Engineering Engine accesses only Model Gateway.
    - Provider-specific APIs do not leak into core Engine code.
    - Adapter registration works.
    - Provider/Profile separation works.

## Adapter Tests

Verify:

    - OpenAI-compatible adapter,
    - Anthropic adapter,
    - Gemini adapter,
    - local-compatible endpoint path.

## Provider Tests

Where practical, validate independently:

    - Groq,
    - OpenAI,
    - Anthropic,
    - Gemini,
    - OpenRouter,
    - OmniRoute,
    - Ollama,
    - LM Studio,
    - vLLM.

Live tests MAY require credentials or running local services.

Mocked adapter-conformance tests SHALL remain independent from external
services.

## Configuration Tests

Verify:

    - single-provider configuration,
    - multi-provider configuration,
    - single-model configuration,
    - multi-model configuration,
    - independent credential references,
    - local/cloud coexistence,
    - custom endpoints.

## Capability Tests

Verify:

    - Tool calling,
    - structured output,
    - vision,
    - reasoning,
    - streaming,
    - context-capacity reporting.

## Failure Tests

Verify:

    - authentication failure,
    - endpoint failure,
    - rate limiting,
    - capability mismatch,
    - protocol mismatch,
    - adapter failure,
    - Provider failure,
    - fallback behavior.


-------------------------------------------------------------------------------

# 46. Decision Status

STATUS

    DRAFT

This ADR revises the V1 Model Gateway architecture to make the existing
adapter-based design explicitly multi-provider and protocol-aware.

The fundamental Model Gateway boundary remains unchanged.

The Provider / Adapter distinction is now explicit.

OpenAI-compatible providers and local runtimes may share one Adapter family.

Anthropic and Gemini retain native adapter paths.

OpenRouter and OmniRoute remain distinct systems.

Credential configuration is Profile-scoped rather than globally singular.

This ADR SHALL become final only after:

    CC-PRD-002 V2.0
        +
    CC-ADR-002 V2.0
        ↓
    Independent review
        ↓
    Documentation approval


-------------------------------------------------------------------------------

# 47. AI Instructions

When implementing or documenting ClaireCoder after this ADR:

    1. Treat the Model Gateway as the only model-execution boundary.
    2. Keep Provider-specific API logic inside Adapters.
    3. Keep Engineering Engine Provider-independent.
    4. Keep Model, Provider, Adapter, Endpoint, Runtime, Router,
       Provider Profile, and Model Profile distinct.
    5. Support native Provider Adapters where required.
    6. Support OpenAI-compatible endpoints.
    7. Keep local runtimes first-class.
    8. Support Ollama.
    9. Support LM Studio.
    10. Support vLLM.
    11. Support OmniRoute as a distinct self-hosted gateway.
    12. Support OpenRouter as a distinct hosted routed Provider.
    13. Never conflate OpenRouter with OmniRoute.
    14. Support custom endpoints.
    15. Keep Routers optional.
    16. Preserve single-model operation.
    17. Preserve multi-provider operation.
    18. Preserve optional multi-model operation.
    19. Represent capabilities explicitly.
    20. Do not assume Provider capability equals Model capability.
    21. Keep Planning Depth separate from reasoning configuration.
    22. Preserve Provider-specific parameters through Adapter extensions.
    23. Keep credentials outside Model context.
    24. Support independent credential references per Provider Profile.
    25. Preserve streaming where supported.
    26. Preserve structured output where supported.
    27. Preserve Tool and vision capability detection.
    28. Keep fallback behavior visible when Model changes materially.
    29. Do not introduce unnecessary distributed infrastructure.
    30. Do not hard-code OmniRoute's default port.
    31. Prefer adapter conformance tests before Provider-specific special cases.
    32. Keep ClaireCoder independent from other Claire ecosystem projects.
    33. Treat this ADR as the authoritative Model Gateway architecture unless
        explicitly superseded.


###############################################################################

END OF CC-ADR-002

###############################################################################