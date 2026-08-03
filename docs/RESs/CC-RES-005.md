###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Research Document
#
# Document Number : CC-RES-005
# Title           : Model Gateway & Provider Research
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document researches the Model Gateway required by ClaireCoder.

The objective is to establish how ClaireCoder SHALL support models from
multiple commercial providers, model routers, OpenAI-compatible endpoints,
and locally running inference systems through a common architecture.

The research covers major provider ecosystems including OpenAI, Anthropic,
Google Gemini, OpenRouter, DeepSeek, Groq, Ollama, LM Studio, vLLM, and
compatible custom endpoints.

A central requirement is that ClaireCoder SHALL NOT assume that every user
has access to multiple premium model providers.

ClaireCoder SHALL therefore support:

- one-model operation,
- multiple-model operation,
- hosted models,
- routed models,
- local models,
- custom endpoints,
- OpenAI-compatible servers,
- capability-aware model selection.

The Model Gateway SHALL abstract provider differences without reducing
provider-specific capabilities to the lowest common denominator.

-------------------------------------------------------------------------------

# 2. Background

Modern coding agents can use models through several fundamentally different
paths.

A model may be accessed through:

- a native provider API,
- an OpenAI-compatible API,
- an Anthropic-compatible API,
- a model router,
- a local inference server,
- a self-hosted deployment,
- a custom endpoint.

OpenRouter provides a unified API and provider routing, including provider
ordering, fallbacks, price, throughput, latency, and capability-based routing.
This demonstrates that a model identifier alone is insufficient to describe
the actual execution environment.

Ollama exposes OpenAI-compatible endpoints for local models and currently
supports features including streaming, JSON mode, vision, Tools, and
reasoning controls for supported models.

LM Studio provides OpenAI-compatible and Anthropic-compatible endpoints in
addition to its native API, including Responses, Chat Completions, embeddings,
tool use, structured output, and local model management.

vLLM provides an OpenAI-compatible server for self-hosted models and supports
Chat Completions, Responses, embeddings, and other interfaces depending on
the served model.

Google Gemini exposes model-specific thinking controls. Gemini 3 models use
thinking levels such as minimal, low, medium, and high depending on the model,
while Gemini 2.5 uses thinking budgets.

These differences demonstrate why ClaireCoder requires a dedicated Model
Gateway instead of embedding provider-specific logic throughout the
Engineering Engine.

-------------------------------------------------------------------------------

# 3. Purpose

This research SHALL determine:

- the responsibilities of the Model Gateway,
- the common model interface,
- provider adapter requirements,
- local model requirements,
- model routing requirements,
- capability detection,
- reasoning configuration,
- Tool calling compatibility,
- structured output compatibility,
- vision compatibility,
- context capability,
- streaming,
- authentication,
- fallback behavior,
- model selection,
- model profiles,
- provider-specific parameters,
- single-model operation,
- multi-model operation.

-------------------------------------------------------------------------------

# 4. Scope

## In Scope

- OpenAI.
- Anthropic.
- Google Gemini.
- OpenRouter.
- DeepSeek.
- Groq.
- Ollama.
- LM Studio.
- vLLM.
- OpenAI-compatible APIs.
- Anthropic-compatible APIs.
- Custom endpoints.
- Model routing.
- Provider adapters.
- Model discovery.
- Model capability detection.
- Context limits.
- Tool calling.
- Structured output.
- Vision.
- Reasoning/thinking controls.
- Streaming.
- Authentication.
- Fallbacks.
- Model profiles.
- Model selection.
- Local inference.
- Hosted inference.
- Provider-specific parameters.

## Out of Scope

- Training language models.
- Building an inference engine.
- Hosting ClaireCoder's own model service.
- Fine-tuning foundation models.
- Final provider adapter implementation.
- Final model configuration schema.
- Final model-selection UI.
- Final routing implementation.

-------------------------------------------------------------------------------

# 5. Research Questions

### RQ-071

What common interface can support fundamentally different model providers?

---

### RQ-072

Which capabilities should belong to the common Model Gateway interface?

---

### RQ-073

Which provider-specific capabilities should remain accessible without
polluting the common interface?

---

### RQ-074

How should ClaireCoder support native provider APIs and OpenAI-compatible
endpoints through the same architecture?

---

### RQ-075

How should local inference systems such as Ollama, LM Studio, and vLLM be
represented?

---

### RQ-076

How should ClaireCoder detect model capabilities such as:

- Tool calling,
- vision,
- structured output,
- reasoning,
- streaming,
- long context,
- embeddings?

---

### RQ-077

How should ClaireCoder represent model context limits?

---

### RQ-078

How should reasoning controls from different providers be normalized?

---

### RQ-079

How should ClaireCoder represent OpenAI reasoning effort, Gemini thinking
levels, provider-specific thinking budgets, and equivalent local-model
controls?

---

### RQ-080

How should ClaireCoder support model routers such as OpenRouter?

---

### RQ-081

How should provider fallback operate?

---

### RQ-082

How should ClaireCoder handle a provider that does not support a requested
capability?

---

### RQ-083

How should model profiles work when the user has access to only one model?

---

### RQ-084

How should ClaireCoder use multiple models when the user has access to them?

---

### RQ-085

How should provider credentials be stored and isolated?

---

### RQ-086

How should model-specific parameters be exposed without forcing users to
understand every provider's API?

---

### RQ-087

How should custom OpenAI-compatible endpoints be configured?

---

### RQ-088

How should ClaireCoder distinguish a model from the provider hosting it?

-------------------------------------------------------------------------------

# 6. Research

## 6.1 Native Provider APIs

ClaireCoder SHALL investigate native adapters for major providers where native
APIs expose capabilities that cannot be represented reliably through a generic
compatibility layer.

The initial provider research SHALL include:

- OpenAI,
- Anthropic,
- Google Gemini,
- DeepSeek,
- Groq.

Native adapters SHOULD preserve important provider capabilities rather than
forcing every provider into identical behavior.

-------------------------------------------------------------------------------

## 6.2 OpenAI-Compatible Providers

OpenAI-compatible APIs are particularly important because many hosted and
local systems expose this interface.

Ollama supports OpenAI-compatible Chat Completions and Responses interfaces,
including Tools and reasoning controls for supported models.

LM Studio provides OpenAI-compatible Responses, Chat Completions,
Completions, and embeddings endpoints, together with tool use and structured
output.

vLLM provides OpenAI-compatible serving for self-hosted models and supports
multiple OpenAI APIs.

Groq also provides substantial compatibility with OpenAI client libraries,
using a configurable base URL.

ClaireCoder SHOULD therefore support a generic OpenAI-compatible provider
adapter.

This adapter SHALL allow users to configure:

- base URL,
- API key,
- model identifier,
- optional headers,
- supported capabilities,
- provider-specific parameters.

-------------------------------------------------------------------------------

## 6.3 Local Models

Local models SHALL be first-class Model Gateway sources.

The initial local ecosystem SHALL investigate:

- Ollama,
- LM Studio,
- vLLM,
- other OpenAI-compatible local servers.

Ollama currently exposes local models through an OpenAI-compatible endpoint
and supports tools, vision, streaming, structured output-related features,
and reasoning controls depending on the model.

LM Studio supports local model serving through native and compatibility APIs,
including OpenAI-compatible and Anthropic-compatible endpoints.

vLLM provides self-hosted OpenAI-compatible serving and supports multiple
request interfaces.

ClaireCoder SHALL not require a user to use a cloud provider.

-------------------------------------------------------------------------------

## 6.4 Model Routers

OpenRouter provides a useful reference for model routing.

Its provider routing supports:

- ordered providers,
- fallbacks,
- capability requirements,
- price limits,
- latency preferences,
- throughput preferences,
- provider allowlists,
- provider exclusions,
- quantization filtering.

ClaireCoder SHALL investigate routing as a distinct layer.

Conceptually:

Model Request
    ↓
Model Selection
    ↓
Provider / Router
    ↓
Execution Endpoint
    ↓
Model Response

A router SHALL not become part of the core model identity.

-------------------------------------------------------------------------------

## 6.5 Model Identity

ClaireCoder SHALL distinguish between:

Model

The logical model being requested.

Provider

The service or runtime exposing the model.

Endpoint

The actual API location used for inference.

Router

An intermediary that selects an execution provider.

Runtime

The infrastructure executing the model, such as a local inference server.

This distinction is important because the same model may be available through
multiple providers and runtimes.

-------------------------------------------------------------------------------

## 6.6 Capability Detection

The Model Gateway SHALL investigate capability metadata.

Potential capabilities include:

- text generation,
- vision,
- Tool calling,
- parallel Tool calling,
- structured output,
- JSON schema,
- reasoning,
- streaming,
- long context,
- embeddings,
- image generation,
- audio,
- code execution,
- native computer use.

Capability information SHOULD be available to the Engineering Engine.

The system SHALL not assume that a model supports a capability merely because
the provider generally supports it.

-------------------------------------------------------------------------------

## 6.7 Reasoning and Thinking Controls

Different providers expose reasoning controls differently.

Google Gemini currently provides thinking levels for Gemini 3 models and
thinking budgets for Gemini 2.5.

Ollama's OpenAI-compatible interface exposes reasoning controls for supported
thinking models.

This indicates that reasoning configuration should be represented at two
levels.

User-facing abstraction:

- minimal,
- low,
- medium,
- high,
- maximum where supported.

Provider mapping:

- reasoning effort,
- thinking level,
- thinking budget,
- provider-specific parameter,
- unsupported.

ClaireCoder SHALL investigate this abstraction rather than exposing raw
provider parameters as the primary user experience.

-------------------------------------------------------------------------------

## 6.8 Planning and Reasoning Are Not Identical

The Model Gateway SHALL NOT equate reasoning effort with Planning Depth.

Planning Depth belongs to the Workflow and Planning system.

Reasoning configuration belongs to the Model Gateway.

The relationship should therefore be:

Planning Profile
    ↓
Workflow Requirement
    ↓
Model Capability
    ↓
Provider-Specific Reasoning Configuration

A high planning profile MAY request stronger model reasoning where available,
but the workflow architecture SHALL remain independent of that parameter.

-------------------------------------------------------------------------------

## 6.9 Tool Calling

Tool calling is essential for ClaireCoder.

The Model Gateway SHALL investigate:

- standard function calling,
- parallel Tool calls,
- Tool-call streaming,
- structured Tool arguments,
- Tool-call validation,
- provider-specific Tool behavior.

vLLM documents support for parallel Tool calls through its OpenAI-compatible
server, while noting that actual support remains model dependent.


ClaireCoder SHALL therefore represent Tool calling as a model capability, not
as a guaranteed provider property.

-------------------------------------------------------------------------------

## 6.10 Structured Output

Structured output can be important for:

- planning artifacts,
- Tool arguments,
- workflow state,
- model capability detection,
- machine-readable responses.

LM Studio currently supports structured JSON output through JSON schemas in
its OpenAI-compatible API.

ClaireCoder SHALL investigate structured-output support as a capability that
can be requested when available.

-------------------------------------------------------------------------------

## 6.11 Vision

Vision capability may be required for:

- screenshot analysis,
- UI implementation,
- visual debugging,
- image-based requirements,
- design references.

Ollama documents vision support for supported models through its
OpenAI-compatible API.

ClaireCoder SHALL treat vision as capability-dependent.

A workflow requiring image understanding SHALL be able to determine whether
the selected model can satisfy that requirement.

-------------------------------------------------------------------------------

## 6.12 Context Limits

Different models expose different context limits.

The Model Gateway SHALL represent context capacity rather than assuming a
universal context window.

This information SHALL be available to the Context Engine so that it can
adjust:

- repository context,
- Skill loading,
- Tool results,
- session history,
- planning artifacts.

A model with a smaller context window SHALL remain usable.

ClaireCoder SHALL adapt context rather than automatically rejecting the model.

-------------------------------------------------------------------------------

## 6.13 Streaming

Streaming SHALL be investigated as a standard Model Gateway capability.

Streaming is important for:

- CLI responsiveness,
- long model responses,
- Tool-call visibility,
- progress feedback,
- user interruption.

The gateway SHOULD normalize streaming events while preserving provider
specific information when required.

-------------------------------------------------------------------------------

## 6.14 Authentication

Provider credentials SHALL be isolated from model configuration.

The Model Gateway SHALL investigate:

- environment variables,
- local credential storage,
- provider-specific authentication,
- API tokens,
- custom headers,
- local endpoint authentication.

Credentials SHALL never be embedded directly into Skills, Workflows, or
repository files by default.

-------------------------------------------------------------------------------

## 6.15 Fallbacks

Fallbacks SHALL be investigated at multiple levels.

Provider fallback:

Use another provider for the same model when available.

Model fallback:

Use another compatible model.

Capability fallback:

Use a different workflow or Tool strategy when a model lacks a capability.

Execution fallback:

Retry or recover from a transient provider failure.

ClaireCoder SHALL avoid silently switching to a materially different model
when the change could affect engineering behavior without making the change
visible to the user.

-------------------------------------------------------------------------------

## 6.16 Model Profiles

ClaireCoder SHALL investigate Model Profiles as a user-facing abstraction.

A Profile MAY define:

- preferred model,
- fallback model,
- reasoning level,
- context strategy,
- Tool capability requirements,
- cost preference,
- latency preference.

Profiles SHOULD remain independent of Skills and Workflows.

A user MAY have:

- one model,
- several models,
- several providers,
- local models only,
- a mixture of local and hosted models.

All of these configurations SHALL remain valid.

-------------------------------------------------------------------------------

## 6.17 Single-Model Operation

Single-model operation SHALL be a first-class scenario.

ClaireCoder SHALL NOT assume:

- one planning model,
- one coding model,
- one review model,
- one research model.

If the user has only one model available, ClaireCoder SHALL use that model
for all compatible stages.

The system MAY change reasoning settings, context strategy, Tools, and
planning depth according to the task without requiring another model.

-------------------------------------------------------------------------------

## 6.18 Multi-Model Operation

When multiple models are available, ClaireCoder MAY assign different models
to different responsibilities.

Potential responsibilities include:

- planning,
- implementation,
- review,
- research,
- vision,
- summarization.

This SHALL remain optional.

Users SHALL NOT be forced to configure multiple models.

-------------------------------------------------------------------------------

# 7. Model Gateway Classification

The initial conceptual architecture SHALL contain:

Provider Layer

- OpenAI.
- Anthropic.
- Google.
- DeepSeek.
- Groq.
- Other native providers.

Compatibility Layer

- OpenAI-compatible endpoints.
- Anthropic-compatible endpoints.

Routing Layer

- OpenRouter.
- Future routing providers.
- Local routing.

Local Runtime Layer

- Ollama.
- LM Studio.
- vLLM.
- Other compatible runtimes.

Capability Layer

- Tool calling.
- Vision.
- Reasoning.
- Structured output.
- Streaming.
- Context.
- Embeddings.

Configuration Layer

- Models.
- Providers.
- Profiles.
- Credentials.
- Fallbacks.

This classification is provisional and SHALL be finalized during architecture
design.

-------------------------------------------------------------------------------

# 8. Analysis

The research demonstrates that a simple "provider adapter" abstraction is
insufficient.

ClaireCoder needs to represent the difference between:

- model identity,
- provider,
- endpoint,
- runtime,
- router,
- capabilities,
- configuration.

The architecture should therefore avoid both extremes:

Too abstract:

Everything becomes a generic chat completion and provider-specific features
are lost.

Too provider-specific:

The Engineering Engine becomes coupled to individual APIs.

The preferred direction is a capability-aware Model Gateway.

The Engineering Engine asks for a capability or model requirement.

The Model Gateway determines how that requirement can be fulfilled.

-------------------------------------------------------------------------------

# 9. Recommendations

Based on the current research, ClaireCoder SHOULD:

1. Build a dedicated Model Gateway.
2. Keep the Engineering Engine independent of providers.
3. Support native adapters for major providers where useful.
4. Support a generic OpenAI-compatible endpoint adapter.
5. Support local Ollama models.
6. Support LM Studio.
7. Support vLLM.
8. Support model routers such as OpenRouter.
9. Distinguish model, provider, endpoint, router, and runtime.
10. Represent model capabilities explicitly.
11. Represent context limits explicitly.
12. Treat Tool calling as a capability.
13. Treat vision as a capability.
14. Treat structured output as a capability.
15. Treat reasoning as a capability.
16. Normalize reasoning controls into higher-level user-facing settings.
17. Keep Planning Depth separate from reasoning parameters.
18. Support streaming.
19. Support provider and model fallbacks.
20. Preserve visibility when materially changing models.
21. Support single-model operation as a first-class configuration.
22. Support multi-model operation as an optional enhancement.
23. Keep credentials separate from Skills and Workflows.
24. Support custom endpoints.
25. Preserve provider-specific parameters through an extension mechanism rather
    than removing them entirely.
26. Avoid forcing every provider into the lowest common denominator.
27. Allow local-only ClaireCoder installations.
28. Allow cloud-only ClaireCoder installations.
29. Allow mixed local and cloud configurations.
30. Keep the Model Gateway replaceable and extensible.

These recommendations SHALL guide later architecture decisions but SHALL NOT
become final implementation requirements until the appropriate ADRs are
completed.

-------------------------------------------------------------------------------

# 10. Expected Outcomes

Successful completion of this research SHALL establish:

- a candidate Model Gateway architecture,
- provider abstraction requirements,
- compatibility-layer requirements,
- local-model requirements,
- routing requirements,
- capability-detection requirements,
- reasoning-control requirements,
- context-capability requirements,
- Tool-calling requirements,
- fallback requirements,
- Model Profile requirements,
- single-model requirements,
- multi-model requirements.

-------------------------------------------------------------------------------

# 11. Risks

Potential risks include:

- excessive provider-specific logic,
- lowest-common-denominator abstractions,
- inaccurate capability detection,
- unsupported provider parameters,
- silent model switching,
- excessive configuration complexity,
- provider lock-in,
- dependence on external routers,
- local-model incompatibility,
- credential leakage,
- inconsistent Tool calling,
- incompatible reasoning controls.

ClaireCoder SHALL prioritize provider independence without hiding meaningful
differences between models.

-------------------------------------------------------------------------------

# 12. Success Criteria

This research succeeds when:

- the Model Gateway responsibility is clearly defined,
- provider and model identity are separated,
- hosted and local models are supported conceptually,
- routing is supported conceptually,
- model capabilities can be represented,
- reasoning controls can be normalized,
- single-model operation is preserved,
- multi-model operation remains optional,
- provider-specific capabilities can remain accessible,
- the architecture can proceed to ADR without repeating the provider
  research.

-------------------------------------------------------------------------------

# 13. Future Work

The next research document SHALL be:

CC-RES-006 — Context, Memory & Engineering Session Research

It SHALL investigate:

- conversation context,
- repository context,
- context hierarchy,
- context compression,
- repository maps,
- memory,
- Engineering Sessions,
- session persistence,
- session resumption,
- engineering journals,
- plan persistence,
- context prioritization,
- model context limits,
- context retrieval,
- stale-context handling.

The research SHALL determine how ClaireCoder can maintain useful engineering
state without continuously sending the entire repository or conversation to
the selected model.

-------------------------------------------------------------------------------

# 14. AI Instructions

When continuing ClaireCoder Model Gateway research:

1. Treat models as replaceable execution components.
2. Preserve complete provider independence.
3. Support local and hosted models.
4. Support custom OpenAI-compatible endpoints.
5. Support model routers.
6. Distinguish model identity from provider and runtime.
7. Represent model capabilities explicitly.
8. Do not assume provider support means every model supports the capability.
9. Keep Planning Depth separate from model reasoning parameters.
10. Normalize reasoning controls without hiding important provider differences.
11. Preserve provider-specific capabilities through extensible mechanisms.
12. Preserve single-model operation.
13. Do not require multiple paid model subscriptions.
14. Preserve secure credential handling.
15. Make material model changes visible.
16. Preserve streaming and Tool calling where supported.
17. Do not lock provider architecture before the appropriate ADR.
18. Preserve ClaireCoder's architectural simplicity.

###############################################################################

END OF CC-RES-005

###############################################################################