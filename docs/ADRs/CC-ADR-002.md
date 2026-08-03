###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-002
# Title           : Model Gateway & Provider Architecture
# Version         : 1.0.0
# Status          : Accepted
#
###############################################################################

# 1. Decision Summary

ClaireCoder SHALL use a dedicated Model Gateway as the only model-execution
boundary between the Engineering Engine and external or local models.

The Model Gateway SHALL support:

- native provider adapters,
- OpenAI-compatible endpoints,
- local inference runtimes,
- model routers,
- custom endpoints.

The Engineering Engine SHALL NOT contain provider-specific API logic.

ClaireCoder SHALL distinguish:

- Model,
- Provider,
- Endpoint,
- Runtime,
- Router,
- Model Profile.

The Model Gateway SHALL expose normalized model capabilities while preserving
provider-specific options through an extension mechanism.

ClaireCoder SHALL support both single-model and multi-model operation.

A user SHALL NOT be required to have access to multiple paid model providers.

Local models SHALL be first-class citizens of the architecture.

-------------------------------------------------------------------------------

# 2. Context

CC-RES-005 established that modern models can be accessed through very
different interfaces.

Examples include:

- native provider APIs,
- OpenAI-compatible APIs,
- local inference servers,
- model routers,
- custom endpoints.

The same model may also be available through multiple providers or runtimes.

Provider APIs differ in:

- authentication,
- Tool calling,
- reasoning controls,
- structured output,
- vision,
- streaming,
- context limits,
- response formats,
- provider-specific parameters.

A simple abstraction such as:

    send(prompt) -> response

would therefore be insufficient for ClaireCoder.

At the same time, embedding every provider-specific difference directly into
the Engineering Engine would make the entire system difficult to maintain.

A dedicated Model Gateway is therefore required.

-------------------------------------------------------------------------------

# 3. Problem

Without a dedicated Model Gateway, ClaireCoder would become tightly coupled
to individual providers.

For example:

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

This would cause provider-specific logic to spread throughout the system.

It would also make it difficult to:

- add a new provider,
- replace a provider,
- use a local model,
- use a custom endpoint,
- route between providers,
- detect capabilities,
- implement model fallback,
- maintain single-model operation.

The architecture therefore requires one stable model-execution boundary.

-------------------------------------------------------------------------------

# 4. Decision

ClaireCoder SHALL implement the following conceptual architecture:

                        ENGINEERING ENGINE
                                │
                                ▼
                         MODEL GATEWAY
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
             ▼                  ▼                  ▼
      Native Providers    Compatibility Layer   Router Layer
             │                  │                  │
       ┌─────┼─────┐            │             OpenRouter
       │     │     │            │             Future Routers
       ▼     ▼     ▼            ▼
     OpenAI Anthropic Gemini   OpenAI-Compatible
       │      │      │         Endpoints
       │      │      │            │
       │      │      │       ┌────┼────┐
       │      │      │       ▼    ▼    ▼
       │      │      │     Ollama LM   vLLM
       │      │      │          Studio
       │      │      │
       └──────┴──────┴───────────────────────────┐
                                                  │
                                                  ▼
                                        MODEL EXECUTION

The Engineering Engine SHALL communicate only with the Model Gateway.

-------------------------------------------------------------------------------

# 5. Model Identity

ClaireCoder SHALL distinguish a logical Model from its execution source.

A Model represents the model requested by the Engineering Engine.

Examples:

- a specific OpenAI model,
- a specific Anthropic model,
- a Gemini model,
- a local model,
- a routed model.

The model identifier SHALL NOT by itself determine the provider.

-------------------------------------------------------------------------------

# 6. Provider

A Provider represents the service responsible for exposing the model.

Examples include:

- OpenAI,
- Anthropic,
- Google,
- DeepSeek,
- Groq,
- OpenRouter,
- a custom provider.

A Provider MAY expose multiple models.

-------------------------------------------------------------------------------

# 7. Endpoint

An Endpoint represents the actual API address through which ClaireCoder
communicates with a model.

For example:

Hosted provider endpoint
    ↓
https://provider.example/api

Local endpoint
    ↓
http://localhost:PORT

Custom endpoint
    ↓
user-defined base URL

The endpoint SHALL be configurable independently from the logical model.

-------------------------------------------------------------------------------

# 8. Runtime

A Runtime represents the environment executing the model.

Examples include:

- cloud inference,
- Ollama,
- LM Studio,
- vLLM,
- another self-hosted runtime.

The Runtime is therefore distinct from the Provider.

A user may run a model locally without a traditional hosted Provider.

-------------------------------------------------------------------------------

# 9. Router

A Router represents an intermediary that determines where model execution
should occur.

A router MAY provide:

- provider selection,
- fallback,
- latency optimization,
- cost optimization,
- availability routing,
- capability routing.

A Router SHALL remain separate from the logical Model identity.

ClaireCoder SHALL support routers without making routing mandatory.

-------------------------------------------------------------------------------

# 10. Model Profile

ClaireCoder SHALL introduce the concept of a Model Profile.

A Model Profile MAY define:

- preferred model,
- provider,
- endpoint,
- reasoning level,
- fallback model,
- capability requirements,
- latency preference,
- cost preference.

The profile SHALL be a user-facing configuration abstraction.

It SHALL NOT replace the underlying Model Gateway entities.

-------------------------------------------------------------------------------

# 11. Provider Adapter Architecture

The Model Gateway SHALL use provider adapters.

The conceptual structure SHALL be:

Model Gateway
     │
     ├── Native Provider Adapter
     │      ├── OpenAI
     │      ├── Anthropic
     │      ├── Gemini
     │      ├── DeepSeek
     │      └── Other Providers
     │
     ├── Compatibility Adapter
     │      └── OpenAI-Compatible
     │
     ├── Router Adapter
     │      └── OpenRouter / Future Routers
     │
     └── Custom Adapter
            └── User-defined Endpoint

Each adapter SHALL translate between the Model Gateway interface and the
provider-specific interface.

-------------------------------------------------------------------------------

# 12. Native Providers

ClaireCoder SHOULD support native adapters where provider-specific APIs expose
important capabilities that cannot be represented reliably through a generic
compatibility API.

Initial providers SHALL be considered for native integration based on:

- capability,
- adoption,
- API stability,
- usefulness to coding workflows.

The initial architecture SHALL not hard-code a permanently closed provider
list.

New providers SHALL be addable through the adapter mechanism.

-------------------------------------------------------------------------------

# 13. OpenAI-Compatible Adapter

ClaireCoder SHALL provide a generic OpenAI-compatible adapter.

This is particularly important because many hosted and local systems expose
OpenAI-compatible interfaces.

The adapter SHALL support configuration of:

- base URL,
- API key where required,
- model identifier,
- optional headers,
- capability metadata,
- compatible request parameters.

The adapter SHALL be usable for:

- hosted providers,
- local runtimes,
- self-hosted inference servers,
- custom endpoints.

ClaireCoder SHALL not require a dedicated adapter for every OpenAI-compatible
service.

-------------------------------------------------------------------------------

# 14. Local Model Support

Local inference SHALL be first-class.

The initial architecture SHALL support systems such as:

- Ollama,
- LM Studio,
- vLLM,
- other compatible local servers.

Local models SHALL use the same Model Gateway abstraction as hosted models.

Conceptually:

Local Model
    ↓
Local Runtime
    ↓
Model Adapter
    ↓
Model Gateway
    ↓
Engineering Engine

The Engineering Engine SHALL not need to know whether a model is local or
remote.

-------------------------------------------------------------------------------

# 15. Custom Endpoints

Users SHALL be able to configure custom model endpoints.

A custom endpoint MAY specify:

- endpoint URL,
- API format,
- model identifier,
- authentication,
- headers,
- capability declarations,
- optional provider-specific parameters.

Custom endpoints SHALL not require modification of ClaireCoder source code.

-------------------------------------------------------------------------------

# 16. Model Capabilities

The Model Gateway SHALL expose capabilities separately from model identity.

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
- code execution.

A model SHALL only be considered capable when the actual selected model and
execution path support the capability.

Provider-level capability declarations SHALL not automatically be applied to
every model.

-------------------------------------------------------------------------------

# 17. Capability Negotiation

When the Engineering Engine requires a capability, it SHALL be able to ask
the Model Gateway whether the active model can satisfy that requirement.

Conceptually:

Engineering Requirement
        │
        ▼
Capability Request
        │
        ▼
Model Gateway
        │
   ┌────┴────┐
   ▼         ▼
Supported  Unsupported
   │         │
   ▼         ▼
Execute    Adapt / Select
           Alternative

This allows ClaireCoder to adapt to models with different capabilities.

-------------------------------------------------------------------------------

# 18. Reasoning Controls

The Model Gateway SHALL expose a normalized reasoning abstraction.

The user-facing abstraction MAY include:

- minimal,
- low,
- medium,
- high,
- maximum where supported.

The Gateway SHALL translate these settings into provider-specific controls.

Examples MAY include:

- reasoning effort,
- thinking level,
- thinking budget,
- provider-specific reasoning parameter.

The Gateway SHALL preserve provider-specific controls where necessary.

-------------------------------------------------------------------------------

# 19. Planning Versus Reasoning

Planning Depth SHALL remain separate from model reasoning configuration.

Planning determines:

- how much planning ClaireCoder performs,
- whether decomposition is required,
- whether validation loops are used,
- whether subagents are used.

Reasoning configuration determines:

- how much reasoning effort the selected model applies.

The two systems MAY influence each other, but SHALL remain separate
architecturally.

-------------------------------------------------------------------------------

# 20. Tool Calling

Tool calling SHALL be represented as a model capability.

The Model Gateway SHALL normalize:

- Tool definitions,
- Tool calls,
- Tool arguments,
- Tool-call responses,
- streaming Tool events where supported.

Provider-specific Tool behavior MAY be preserved through adapter metadata.

A provider supporting Tools does not guarantee that every model exposed by
that provider supports Tools.

-------------------------------------------------------------------------------

# 21. Structured Output

Structured output SHALL be represented as a capability.

The Model Gateway SHOULD support:

- JSON output,
- schema-based output,
- structured responses.

When a provider does not support the requested structured-output mechanism,
the Engineering Engine MAY use an alternative strategy.

The Gateway SHALL communicate capability availability rather than silently
pretending support exists.

-------------------------------------------------------------------------------

# 22. Vision

Vision SHALL be represented as a model capability.

If a Workflow requires image understanding, the Engineering Engine SHALL be
able to determine whether the active Model Profile supports vision.

If it does not, ClaireCoder MAY:

- request another model,
- use another Model Profile,
- change the workflow,
- ask the user,
- continue without vision where possible.

The Gateway SHALL not silently claim vision support.

-------------------------------------------------------------------------------

# 23. Context Capacity

The Model Gateway SHALL expose context-capacity information where available.

The Context Engine MAY use this information to determine:

- context budget,
- Tool-result limits,
- Skill loading,
- repository retrieval,
- compression requirements.

The system SHALL not assume every model has the same context capacity.

-------------------------------------------------------------------------------

# 24. Streaming

The Model Gateway SHALL support streaming where the provider supports it.

Streaming events SHOULD be normalized sufficiently for the Interaction Layer
to display:

- generated text,
- Tool calls,
- Tool results,
- status,
- completion,
- errors.

Provider-specific event data MAY remain accessible through an extension
mechanism.

-------------------------------------------------------------------------------

# 25. Authentication

Authentication SHALL be handled by the Model Gateway configuration layer.

The Engineering Engine SHALL not directly manage API keys.

Credentials MAY originate from:

- environment variables,
- local configuration,
- secure credential storage,
- provider-specific authentication mechanisms.

Raw credentials SHALL NOT be inserted into model context.

-------------------------------------------------------------------------------

# 26. Provider Failure

The Model Gateway SHALL distinguish between:

- model failure,
- provider failure,
- endpoint failure,
- authentication failure,
- rate limiting,
- capability mismatch,
- temporary network failure.

The Gateway SHOULD return structured failure information to the Engineering
Engine.

The Engineering Engine SHALL then determine whether to:

- retry,
- fallback,
- switch model,
- ask the user,
- terminate.

-------------------------------------------------------------------------------

# 27. Fallback Architecture

Fallbacks SHALL exist at multiple levels.

Provider Fallback:

Use another provider capable of serving the requested model or task.

Model Fallback:

Use another compatible model.

Capability Fallback:

Use another model capable of the required capability.

Execution Fallback:

Retry or recover from a transient failure.

Fallback behavior SHALL not silently change the model in situations where the
difference may materially affect the engineering result.

-------------------------------------------------------------------------------

# 28. Single-Model Configuration

A configuration containing only one available model SHALL be valid.

Example:

Model Profile
    ↓
One Model
    ↓
All compatible ClaireCoder workflows

ClaireCoder SHALL not require:

- separate planning model,
- separate coding model,
- separate review model,
- separate research model.

Multiple models are an optimization, not a requirement.

-------------------------------------------------------------------------------

# 29. Multi-Model Configuration

When multiple models are available, ClaireCoder MAY assign different models
to different responsibilities.

Potential responsibilities include:

- planning,
- coding,
- review,
- research,
- vision,
- summarization.

This assignment SHALL remain configurable.

The Engineering Engine SHALL not assume that multiple models are always
available.

-------------------------------------------------------------------------------

# 30. Router Integration

Model routers SHALL be represented as provider-routing components.

A router MAY perform:

- provider selection,
- fallback,
- latency optimization,
- cost optimization,
- availability selection.

ClaireCoder SHALL treat router configuration separately from Model Profiles.

A Model Profile MAY select a router as its execution source.

-------------------------------------------------------------------------------

# 31. Provider-Specific Parameters

The common Model Gateway interface SHALL expose normalized parameters.

However, it SHALL also support provider-specific parameters through an
extension mechanism.

This prevents the common interface from becoming either:

Too restrictive:

where provider features are lost.

Or too provider-specific:

where the Engineering Engine becomes coupled to individual APIs.

Provider-specific parameters SHALL not become required for ordinary
ClaireCoder operation.

-------------------------------------------------------------------------------

# 32. Model Selection

Model selection SHALL be performed through the Model Gateway.

Selection MAY consider:

- requested model,
- Model Profile,
- capabilities,
- provider availability,
- context capacity,
- reasoning requirements,
- user preference,
- cost preference,
- latency preference,
- local/remote preference.

The Engineering Engine SHALL provide requirements.

The Model Gateway SHALL determine available execution options.

-------------------------------------------------------------------------------

# 33. Model Discovery

The Gateway SHOULD support model discovery where the provider or runtime
allows it.

Discovery MAY return:

- model identifier,
- display name,
- provider,
- runtime,
- capabilities,
- context capacity,
- reasoning support,
- vision support,
- Tool support.

Local runtimes SHOULD be discoverable where their APIs provide sufficient
information.

Users SHALL also be able to manually configure models when discovery is not
available.

-------------------------------------------------------------------------------

# 34. Model Configuration

The configuration hierarchy SHOULD conceptually be:

Provider
    ↓
Endpoint
    ↓
Model
    ↓
Capabilities
    ↓
Model Profile

This SHALL remain a conceptual architecture.

The final configuration schema SHALL be determined during implementation
planning.

-------------------------------------------------------------------------------

# 35. Decision Rationale

This architecture was selected because it satisfies the major Model Gateway
requirements identified during RES research.

It provides:

- provider independence,
- local model support,
- hosted model support,
- router support,
- custom endpoints,
- capability awareness,
- single-model operation,
- multi-model operation,
- provider-specific extensibility.

It also prevents model-provider logic from spreading into:

- Workflows,
- Skills,
- Tools,
- Context,
- Sessions,
- Permissions.

-------------------------------------------------------------------------------

# 36. Alternatives Considered

## Alternative A — Direct Provider Calls From Engineering Engine

Decision:

REJECTED.

Reason:

This creates provider coupling throughout the core agent.

-------------------------------------------------------------------------------

## Alternative B — OpenAI-Compatible API Only

Decision:

REJECTED.

Reason:

Compatibility APIs are useful but may not expose every provider-specific
capability.

Native adapters remain necessary for important providers.

-------------------------------------------------------------------------------

## Alternative C — One Adapter Per Provider With No Generic Layer

Decision:

REJECTED.

Reason:

This would unnecessarily duplicate adapters for the large number of
OpenAI-compatible endpoints.

-------------------------------------------------------------------------------

## Alternative D — Router-Only Architecture

Decision:

REJECTED.

Reason:

ClaireCoder must work without a router and must support local models and
direct providers.

-------------------------------------------------------------------------------

## Alternative E — Require Multiple Specialized Models

Decision:

REJECTED.

Reason:

This would make ClaireCoder inaccessible to users with only one available
model or limited resources.

-------------------------------------------------------------------------------

# 37. Consequences

## Positive Consequences

- Strong provider independence.
- First-class local model support.
- Easy custom endpoint support.
- Router support.
- Capability-aware execution.
- Easier provider expansion.
- Single-model accessibility.
- Multi-model flexibility.
- Cleaner Engineering Engine.
- Provider-specific extensibility.

## Negative Consequences

- Adapter interfaces must be maintained.
- Capability normalization introduces abstraction complexity.
- Provider-specific behavior requires adapter-specific testing.
- Model discovery may be inconsistent between providers.
- Fallback behavior requires careful design.

These costs are accepted because model independence is a core ClaireCoder
requirement.

-------------------------------------------------------------------------------

# 38. V1 Boundary

The following SHALL be part of the V1 Model Gateway architecture:

- Model Gateway.
- Provider adapter interface.
- OpenAI-compatible adapter.
- Model abstraction.
- Provider abstraction.
- Endpoint abstraction.
- Capability representation.
- Model Profile concept.
- Local endpoint support.
- Custom endpoint support.
- Streaming support where available.
- Tool capability representation.
- Reasoning capability representation.
- Context-capacity representation.
- Authentication abstraction.

The following MAY remain optional implementation extensions:

- advanced automatic model routing,
- automatic cost optimization,
- advanced latency optimization,
- complex provider scoring,
- automatic model benchmarking,
- advanced model recommendation.

ClaireCoder SHALL remain fully functional without these features.

-------------------------------------------------------------------------------

# 39. Implementation Guidance

The Model Gateway SHOULD initially favor:

- explicit provider interfaces,
- explicit capability structures,
- simple adapter classes,
- structured model responses,
- normalized streaming events,
- deterministic error types,
- configuration-driven endpoints.

The implementation SHALL avoid:

- embedding provider logic into the Engineering Engine,
- forcing every provider into identical behavior,
- requiring a router,
- requiring multiple models,
- requiring cloud inference,
- creating unnecessary distributed infrastructure.

-------------------------------------------------------------------------------

# 40. Decision Status

STATUS

ACCEPTED

This ADR establishes the Model Gateway architecture for ClaireCoder V1.

Later ADRs MAY refine:

- Tool integration,
- Skills,
- Workflows,
- Context,
- Sessions,
- Interaction,
- Permissions.

A later decision SHALL explicitly supersede this ADR if it changes the Model
Gateway's fundamental architecture.

-------------------------------------------------------------------------------

# 41. Relationship With Other ADRs

CC-ADR-001

ClaireCoder Core Architecture

Defines the overall system boundaries.

CC-ADR-002

Model Gateway & Provider Architecture

Defines the model execution boundary.

CC-ADR-003

Tool & Skill Extension Architecture

Defines how Tools and Skills integrate with the Engineering Engine.

CC-ADR-004

Workflow, Context & Engineering Session Architecture

Defines engineering execution state and context.

CC-ADR-005

Interaction, Modes & Command Architecture

Defines the user interaction system.

CC-ADR-006

Permission, Autonomy & Security Architecture

Defines execution security and autonomy.

-------------------------------------------------------------------------------

# 42. AI Instructions

When implementing or documenting ClaireCoder after this ADR:

1. Treat the Model Gateway as the only model execution boundary.
2. Keep provider-specific API logic inside adapters.
3. Keep the Engineering Engine provider independent.
4. Support native provider adapters where necessary.
5. Support generic OpenAI-compatible endpoints.
6. Keep local runtimes first-class.
7. Support custom endpoints.
8. Keep routers optional.
9. Keep single-model operation valid.
10. Keep multi-model operation optional.
11. Represent capabilities explicitly.
12. Do not assume provider capability equals model capability.
13. Keep Planning Depth separate from model reasoning configuration.
14. Preserve provider-specific parameters through an extension mechanism.
15. Keep credentials outside model context.
16. Preserve streaming where supported.
17. Preserve structured output where supported.
18. Preserve Tool and vision capability detection.
19. Keep fallback behavior visible when model changes materially.
20. Do not introduce unnecessary provider-specific logic into other
    subsystems.
21. Treat this ADR as the authoritative Model Gateway architecture unless
    explicitly superseded.

###############################################################################

END OF CC-ADR-002

###############################################################################