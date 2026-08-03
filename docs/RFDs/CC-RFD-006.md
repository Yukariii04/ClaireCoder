###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                  Research Foundation Document
#
# Document Number : CC-RFD-006
# Title           : Model Gateway & Provider Independence
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document defines the foundational model architecture philosophy of
ClaireCoder.

ClaireCoder SHALL remain independent of individual language models, model
providers, and model hosting methods.

The Model Gateway SHALL provide a consistent interface through which the
Engineering Engine can use hosted APIs, routing services, custom endpoints,
and locally running models without requiring changes to the core engineering
architecture.

-------------------------------------------------------------------------------

# 2. Background

Modern coding agents can access models through many different mechanisms,
including direct provider APIs, model routers, OpenAI-compatible endpoints,
local inference servers, and hosted services.

OpenCode currently demonstrates broad provider abstraction, supporting more
than 75 providers as well as local models and configurable endpoints.
Its architecture also allows models to be selected independently of the
provider configuration.

ClaireCoder SHALL adopt the underlying principle of model independence without
being architecturally dependent on any particular provider implementation.

-------------------------------------------------------------------------------

# 3. Purpose

The Model Gateway SHALL:

- provide a common model interface,
- support multiple hosted providers,
- support model routing services,
- support local models,
- support custom endpoints,
- isolate provider-specific behavior,
- expose model capabilities to the Engineering Engine,
- allow models to be changed without redesigning ClaireCoder.

-------------------------------------------------------------------------------

# 4. Design Philosophy

The Model Gateway is **not**:

- a language model,
- a model router by itself,
- an engineering planner,
- a workflow engine,
- a provider-specific abstraction.

The model is a replaceable execution capability of ClaireCoder.

The Engineering Engine SHALL remain independent of which model performs the
reasoning.

A user SHALL be able to change models without changing Skills, Workflows,
Tools, or the Engineering Engine.

-------------------------------------------------------------------------------

# 5. Responsibilities

The Model Gateway SHALL:

- connect ClaireCoder to supported model providers,
- manage model selection,
- provide a common invocation interface,
- support streaming where available,
- expose model capabilities,
- support provider-specific configuration,
- support local and remote execution,
- provide a foundation for future provider integrations.

-------------------------------------------------------------------------------

# 6. Scope

## In Scope

- Hosted model providers.
- Local model providers.
- Model routers.
- OpenAI-compatible endpoints.
- Custom endpoints.
- Model selection.
- Model capability information.
- Provider configuration.
- Model variants and parameters.
- Authentication handling.

## Out of Scope

- Training language models.
- Creating foundation models.
- Defining engineering workflows.
- Defining Skills.
- Defining Tools.
- Provider-specific engineering behavior.

-------------------------------------------------------------------------------

# 7. Design Principles

The Model Gateway SHALL:

- remain provider independent,
- remain model independent,
- support local and remote models,
- support extensible providers,
- expose model capabilities,
- isolate provider-specific implementation,
- avoid unnecessary provider lock-in,
- preserve user choice.

-------------------------------------------------------------------------------

# 8. Research Questions

### RQ-030

What common interface can support fundamentally different model providers?

---

### RQ-031

How should ClaireCoder support local inference servers and hosted APIs through
the same architecture?

---

### RQ-032

How should model capabilities such as tool calling, structured output,
vision, context length, and reasoning capabilities be represented?

---

### RQ-033

How should ClaireCoder support model routers such as OpenRouter without
coupling the Engineering Engine to the router?

---

### RQ-034

How should provider-specific parameters and features be exposed without
polluting the common model interface?

---

### RQ-035

How should ClaireCoder handle models with different capabilities while
preserving the same Skills and Workflows?

-------------------------------------------------------------------------------

# 9. Expected Outcomes

Successful completion establishes:

- one canonical model abstraction,
- provider independence,
- local-model compatibility,
- hosted-model compatibility,
- routing compatibility,
- capability-aware model selection,
- a foundation for future model providers.

-------------------------------------------------------------------------------

# 10. Risks

Potential risks include:

- provider-specific coupling,
- inconsistent model capabilities,
- incompatible APIs,
- excessive abstraction,
- inaccurate capability metadata,
- dependence on external model catalogs.

The Model Gateway SHALL remain simple enough to support new providers without
requiring changes throughout ClaireCoder.

-------------------------------------------------------------------------------

# 11. Success Criteria

This document succeeds when:

- models can be replaced independently of the Engineering Engine,
- local and hosted models share the same conceptual interface,
- provider-specific behavior remains isolated,
- model capabilities can be represented,
- future providers can be added without architectural redesign.

-------------------------------------------------------------------------------

# 12. Future Work

Future documents SHALL determine:

- the canonical model interface,
- provider adapter architecture,
- authentication mechanisms,
- model capability representation,
- local inference support,
- router integration,
- model discovery,
- model selection,
- model parameter handling,
- fallback and compatibility behavior.

-------------------------------------------------------------------------------

# 13. AI Instructions

When producing ClaireCoder Model Gateway architecture:

1. Treat models as replaceable execution components.
2. Preserve complete separation between models and the Engineering Engine.
3. Do not couple Skills or Workflows to specific providers.
4. Support both hosted and locally running models.
5. Preserve compatibility with OpenAI-compatible endpoints.
6. Preserve support for model routing services.
7. Isolate provider-specific behavior behind the Model Gateway.
8. Prefer capability-based behavior over hardcoded model names.
9. Do not require users to have access to multiple paid models.
10. Preserve user choice and provider independence.

###############################################################################

END OF CC-RFD-006

###############################################################################