###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-001
# Title           : ClaireCoder Core Architecture
# Version         : 1.0.0
# Status          : Accepted
#
###############################################################################

# 1. Decision Summary

ClaireCoder SHALL use a modular, backend-agnostic agent architecture.

The architecture SHALL separate the major responsibilities of the system
instead of implementing ClaireCoder as one monolithic agent loop.

The core architecture SHALL consist of:

- Interaction Layer
- Command System
- Engineering Engine
- Workflow & Planning
- Context Engine
- Model Gateway
- Tool Ecosystem
- Skill System
- Permission Engine
- Engineering Session
- Extension Layer

The Engineering Engine SHALL coordinate these components.

Models SHALL provide reasoning and generation capabilities.

Tools SHALL provide executable capabilities.

Skills SHALL provide reusable expertise and methodology.

Workflows SHALL define engineering processes.

The Permission Engine SHALL control execution authority.

The Context Engine SHALL determine what information is supplied to the
selected model.

The Model Gateway SHALL provide model and provider independence.

The architecture SHALL support local models, hosted models, model routers,
and custom compatible endpoints.

-------------------------------------------------------------------------------

# 2. Context

The initial ClaireCoder V1 research phase established the following:

- Tools must be modular and extensible.
- Skills must be independently installable and progressively loaded.
- Planning must adapt to task complexity.
- Multiple model providers must be supported.
- Local models must be first-class.
- Context, Memory, and Engineering Sessions must remain distinct.
- Modes and Commands must remain separate from Skills and Tools.
- Permissions must be centralized.
- Third-party extensions must remain controlled.
- ClaireCoder must remain usable with only one available model.
- The architecture must avoid unnecessary complexity.

The system is intended to provide the capabilities expected from modern coding
agents while allowing ClaireCoder to implement its own behavior, extension
system, Skills, interface, and provider architecture.

-------------------------------------------------------------------------------

# 3. Problem

A monolithic architecture would create several problems.

If model-provider logic is embedded directly into the agent:

- provider lock-in increases,
- local models become harder to support,
- provider-specific features become difficult to manage.

If Tools contain workflow logic:

- Skills become tightly coupled to implementation,
- permissions become difficult to centralize,
- Tool reuse becomes limited.

If Skills contain execution logic:

- third-party Skills become harder to trust,
- Skill portability decreases,
- Tool boundaries become unclear.

If Context is handled directly by individual Tools:

- context usage becomes unpredictable,
- session persistence becomes difficult,
- large repositories become inefficient.

If permissions are implemented only in the interface:

- commands,
- Skills,
- MCP,
- subagents,
- and autonomous workflows

could potentially bypass the intended security boundary.

Therefore ClaireCoder requires explicit architectural boundaries.

-------------------------------------------------------------------------------

# 4. Decision

ClaireCoder SHALL use a layered modular architecture centered around the
Engineering Engine.

The conceptual architecture SHALL be:

                              CLAIRECODER
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
             Interaction Layer              Extension Layer
                    │                             │
          ┌─────────┴─────────┐          ┌────────┴────────┐
          │                   │          │                 │
       Commands             Modes      Skills            MCP
          │                   │          │                 │
          └─────────────┬─────┘          │                 │
                        │                 │                 │
                        ▼                 ▼                 ▼
                 ┌────────────────────────────────────────────┐
                 │            ENGINEERING ENGINE              │
                 └──────────────────────┬─────────────────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             │                          │                          │
             ▼                          ▼                          ▼
       Workflow &                 Context Engine             Permission
        Planning                       │                     Engine
             │                         │                          │
             │                         ▼                          │
             │                 Repository Intelligence             │
             │                                                    │
             └──────────────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
                    ▼                                       ▼
              Model Gateway                            Tool Ecosystem
                    │                                       │
          ┌─────────┼─────────┐                ┌────────────┼────────────┐
          │         │         │                │            │            │
       Hosted     Router     Local          Filesystem   Terminal      Git
       Models     Models     Models          Search       Tests       Web
                                             Browser       LSP        MCP
                    │
                    ▼
             Engineering Session
                    │
                    ▼
             Persistent State

This diagram represents the conceptual responsibility boundaries.

The final implementation MAY differ internally as long as these architectural
responsibilities remain preserved.

-------------------------------------------------------------------------------

# 5. Architectural Components

## 5.1 Interaction Layer

The Interaction Layer SHALL provide the user-facing interface.

It SHALL support:

- interactive operation,
- commands,
- Modes,
- status,
- progress,
- approvals,
- model selection,
- Skill controls,
- session controls.

The Interaction Layer SHALL NOT contain core agent reasoning logic.

It SHALL communicate with the Engineering Engine through defined interfaces.

-------------------------------------------------------------------------------

## 5.2 Command System

The Command System SHALL translate explicit user commands into actions.

Commands MAY invoke:

- Workflows,
- Modes,
- Skills,
- Tools,
- Session operations,
- Model operations,
- configuration operations.

The Command System SHALL NOT bypass the Permission Engine when the resulting
operation requires permission.

-------------------------------------------------------------------------------

## 5.3 Engineering Engine

The Engineering Engine SHALL be the central orchestration component.

It SHALL coordinate:

- user objectives,
- planning,
- context retrieval,
- model interaction,
- Tool execution,
- Skills,
- validation,
- recovery,
- replanning,
- session state.

The Engineering Engine SHALL NOT directly implement provider-specific model
logic.

It SHALL request model capabilities through the Model Gateway.

-------------------------------------------------------------------------------

## 5.4 Workflow & Planning

The Workflow & Planning subsystem SHALL determine how an engineering
objective is decomposed and executed.

It SHALL support:

- direct execution,
- lightweight planning,
- structured planning,
- deep planning,
- validation,
- recovery,
- replanning,
- bounded subagents,
- task dependencies.

Planning depth SHALL remain adaptive.

-------------------------------------------------------------------------------

## 5.5 Context Engine

The Context Engine SHALL determine what information is relevant to the current
model operation.

It SHALL coordinate:

- repository context,
- conversation context,
- active plan,
- Tool results,
- Skill instructions,
- session state,
- relevant Memory,
- model context limits.

The Context Engine SHALL NOT assume that the entire repository or session can
fit into the model context.

-------------------------------------------------------------------------------

## 5.6 Model Gateway

The Model Gateway SHALL abstract model execution from the Engineering Engine.

It SHALL support the conceptual categories established by CC-RES-005:

- native providers,
- OpenAI-compatible endpoints,
- local runtimes,
- model routers,
- custom endpoints.

The Model Gateway SHALL expose model capabilities such as:

- Tool calling,
- reasoning,
- vision,
- structured output,
- streaming,
- context capacity.

The Engineering Engine SHALL interact with models through this abstraction.

-------------------------------------------------------------------------------

## 5.7 Tool Ecosystem

The Tool Ecosystem SHALL provide executable capabilities.

Core Tool categories SHALL include:

- filesystem,
- file discovery,
- code search,
- editing,
- terminal,
- Git,
- testing,
- diagnostics.

Optional Tool categories MAY include:

- LSP,
- web search,
- web retrieval,
- browser,
- image-related capabilities,
- external integrations.

Tools SHALL remain independently permission-controlled.

-------------------------------------------------------------------------------

## 5.8 Skill System

The Skill System SHALL provide reusable expertise and methodology.

Skills SHALL remain separate from Tools.

Skills MAY:

- influence planning,
- provide specialized methodology,
- establish engineering practices,
- provide references,
- provide templates,
- provide supporting resources.

Skills SHALL NOT automatically receive unrestricted Tool access.

The Skill System SHALL support the three acquisition paths established by
research:

1. Manual selection.
2. Curated Collections.
3. Third-party sources.

-------------------------------------------------------------------------------

## 5.9 Permission Engine

The Permission Engine SHALL provide the centralized execution boundary.

The conceptual decision model SHALL remain:

Tool / Extension Request
            │
            ▼
      Permission Engine
            │
       ┌────┼────┐
       ▼    ▼    ▼
     ALLOW ASK DENY
            │
            ▼
       Tool Execution

Commands, Skills, Workflows, subagents, and MCP SHALL NOT bypass this layer.

-------------------------------------------------------------------------------

## 5.10 Engineering Session

The Engineering Session SHALL represent the persistent state of an
engineering task.

It MAY contain:

- objective,
- current Mode,
- current plan,
- task state,
- completed work,
- pending work,
- validation state,
- important decisions,
- unresolved issues,
- relevant repository state,
- session metadata.

Session state SHALL remain separate from active model context.

-------------------------------------------------------------------------------

## 5.11 Extension Layer

The Extension Layer SHALL provide mechanisms for capabilities outside the
ClaireCoder core.

Potential extension mechanisms include:

- third-party Skills,
- MCP,
- external Tools,
- future integrations.

Extensions SHALL use the same fundamental security boundaries as built-in
capabilities.

-------------------------------------------------------------------------------

# 6. Core Architectural Principles

## 6.1 Model Independence

ClaireCoder SHALL not depend on a single model provider.

The Engineering Engine SHALL operate through the Model Gateway.

-------------------------------------------------------------------------------

## 6.2 Local-First Capability

Local models SHALL be treated as first-class models.

ClaireCoder SHALL remain functional when the user has no cloud model access.

-------------------------------------------------------------------------------

## 6.3 Single-Model Operation

ClaireCoder SHALL NOT require multiple models.

A single available model SHALL be capable of supporting the complete workflow
within its capabilities.

Multiple models MAY be used when available.

-------------------------------------------------------------------------------

## 6.4 Capability Awareness

ClaireCoder SHALL not assume that every model supports:

- Tool calling,
- vision,
- reasoning,
- structured output,
- large context,
- streaming.

The Model Gateway SHALL expose these capabilities.

The Engineering Engine SHALL adapt accordingly.

-------------------------------------------------------------------------------

## 6.5 Progressive Context

ClaireCoder SHALL prefer relevant context over indiscriminate context.

Skills, repository information, Tool results, and Memory SHALL be retrieved
when required.

-------------------------------------------------------------------------------

## 6.6 Centralized Permissions

Every executable capability SHALL pass through the Permission Engine.

No extension mechanism SHALL create an alternate security path.

-------------------------------------------------------------------------------

## 6.7 Extensibility

ClaireCoder SHALL support extensions without requiring changes to the core
Engineering Engine.

Third-party Skills and Tools SHALL be able to integrate through defined
interfaces.

-------------------------------------------------------------------------------

## 6.8 Simplicity

ClaireCoder SHALL avoid unnecessary architectural complexity.

A capability SHALL only become a separate subsystem when there is a clear
responsibility or lifecycle requiring separation.

-------------------------------------------------------------------------------

# 7. Data Flow

The primary engineering flow SHALL conceptually be:

User Request
     │
     ▼
Interaction Layer
     │
     ▼
Engineering Engine
     │
     ├──────────────► Context Engine
     │                     │
     │                     ▼
     │               Relevant Context
     │
     ├──────────────► Workflow / Planning
     │                     │
     │                     ▼
     │                  Plan
     │
     ├──────────────► Model Gateway
     │                     │
     │                     ▼
     │                Model Decision
     │
     ├──────────────► Permission Engine
     │                     │
     │                     ▼
     │                 Tool Access
     │
     ├──────────────► Tool Ecosystem
     │                     │
     │                     ▼
     │                  Result
     │
     ├──────────────► Validation
     │                     │
     │              ┌──────┴──────┐
     │              │             │
     │             PASS          FAIL
     │              │             │
     │              ▼             ▼
     │          Complete       Replan
     │
     ▼
Engineering Session

The actual implementation MAY introduce additional internal stages.

-------------------------------------------------------------------------------

# 8. Component Dependency Rules

The following dependency rules SHALL apply.

### Rule 001

The Engineering Engine MAY depend on:

- Model Gateway,
- Context Engine,
- Workflow,
- Tools,
- Skills,
- Permission Engine,
- Session.

### Rule 002

The Model Gateway SHALL NOT depend on the Engineering Engine.

### Rule 003

Tools SHALL NOT directly control Workflow state.

### Rule 004

Skills SHALL NOT directly bypass the Permission Engine.

### Rule 005

The Interaction Layer SHALL NOT directly execute privileged operations.

### Rule 006

The Context Engine SHALL NOT become a provider-specific model component.

### Rule 007

The Permission Engine SHALL remain independent from any individual Tool.

### Rule 008

Third-party extensions SHALL use public extension interfaces rather than
internal implementation details.

-------------------------------------------------------------------------------

# 9. Decision Rationale

This architecture was selected because it preserves the major requirements
identified throughout the RES phase.

It supports:

- Claude Code-style agentic workflows,
- Codex-style engineering execution,
- OpenCode-style extensibility,
- Hermes-style Skills and sessions,
- local models,
- hosted models,
- model routers,
- third-party Skills,
- MCP,
- adaptive planning,
- persistent engineering sessions,
- centralized permissions.

At the same time, it avoids implementing every feature as an independent
service or requiring unnecessary infrastructure.

The architecture therefore provides separation where it is useful while
remaining practical for a V1 implementation.

-------------------------------------------------------------------------------

# 10. Alternatives Considered

## Alternative A — Monolithic Agent

A single component would contain:

- model calls,
- Tools,
- Skills,
- planning,
- context,
- permissions,
- sessions.

Decision:

REJECTED.

Reason:

This would make provider replacement, Tool extension, Skill extension,
testing, security, and long-term maintenance unnecessarily difficult.

-------------------------------------------------------------------------------

## Alternative B — Microservice Architecture

Each subsystem would run as a separate service.

Decision:

REJECTED FOR V1.

Reason:

ClaireCoder is primarily a local/CLI coding agent.

Separate services would introduce unnecessary:

- networking,
- deployment,
- synchronization,
- failure modes,
- configuration,
- resource overhead.

Modularity SHALL exist primarily through internal interfaces rather than
mandatory network services.

-------------------------------------------------------------------------------

## Alternative C — Model-Centric Architecture

The selected model would control most system behavior directly.

Decision:

REJECTED.

Reason:

This would couple ClaireCoder's architecture to individual model behavior and
make local, hosted, and future providers harder to support consistently.

-------------------------------------------------------------------------------

## Alternative D — Tool-Centric Architecture

Tools would contain planning and workflow behavior.

Decision:

REJECTED.

Reason:

Tools should provide capabilities, not own the overall engineering process.

-------------------------------------------------------------------------------

# 11. Consequences

## Positive Consequences

- Provider independence.
- Local model support.
- Easier Tool extension.
- Easier Skill extension.
- Centralized security.
- Adaptive planning.
- Better context management.
- Session persistence.
- Clear architectural boundaries.
- Easier testing.
- Future MCP support.
- Future extension support.

## Negative Consequences

- More interfaces must be defined.
- Component coordination becomes more complex than a simple agent loop.
- Some functionality may require additional abstraction.
- Debugging cross-component behavior may require tracing.

These costs are considered acceptable because they directly support the
project's core requirements.

-------------------------------------------------------------------------------

# 12. V1 Boundary

The following SHALL be considered part of the V1 architectural foundation:

Core:

- Engineering Engine.
- Model Gateway.
- Context Engine.
- Workflow & Planning.
- Tool Ecosystem.
- Skill System.
- Permission Engine.
- Engineering Session.
- Command System.
- Interaction Layer.

The following SHALL remain optional extensions:

- advanced browser automation,
- advanced sandboxing,
- advanced worktree orchestration,
- external Tool registries,
- advanced memory retrieval,
- complex multi-agent orchestration.

ClaireCoder SHALL not require these capabilities to operate as a useful
coding agent.

-------------------------------------------------------------------------------

# 13. Implementation Guidance

This ADR establishes architecture, not implementation details.

The implementation SHOULD initially favor:

- clear Python interfaces,
- small modules,
- explicit data structures,
- structured events,
- deterministic state transitions,
- testable components.

The architecture SHALL NOT require:

- microservices,
- distributed databases,
- vector databases,
- Kubernetes,
- remote orchestration,
- complex event buses

for V1.

Those technologies MAY be introduced later only if justified by a separate
architectural decision.

-------------------------------------------------------------------------------

# 14. Decision Status

STATUS

ACCEPTED

This ADR establishes the baseline architecture for ClaireCoder V1.

Later ADRs MAY refine individual subsystems.

A later ADR SHALL NOT silently contradict this architecture.

If a later decision requires changing this architecture, the affected ADR
SHALL explicitly identify the conflict and supersede the relevant decision.

-------------------------------------------------------------------------------

# 15. Relationship With Other ADRs

CC-ADR-001 establishes the overall architecture.

The following ADRs SHALL define the major subsystem decisions:

CC-ADR-002

Model Gateway & Provider Architecture

CC-ADR-003

Tool & Skill Extension Architecture

CC-ADR-004

Workflow, Context & Engineering Session Architecture

CC-ADR-005

Interaction, Modes & Command Architecture

CC-ADR-006

Permission, Autonomy & Security Architecture

These ADRs SHALL refine the corresponding areas without unnecessarily
duplicating this document.

-------------------------------------------------------------------------------

# 16. AI Instructions

When implementing or documenting ClaireCoder after this ADR:

1. Preserve the component boundaries established here.
2. Do not turn ClaireCoder into a monolithic agent.
3. Keep the Engineering Engine as the central orchestrator.
4. Keep the Model Gateway provider independent.
5. Keep local models first-class.
6. Keep single-model operation supported.
7. Keep Tools separate from Skills.
8. Keep Skills separate from Workflows.
9. Keep Context separate from Memory and Session state.
10. Keep Permissions centralized.
11. Keep Commands separate from execution capabilities.
12. Do not bypass the Permission Engine.
13. Do not introduce microservices for V1 without an explicit ADR.
14. Do not introduce unnecessary infrastructure.
15. Preserve extension support.
16. Preserve the three Skill acquisition paths.
17. Preserve adaptive planning.
18. Preserve model capability awareness.
19. Preserve ClaireCoder's simplicity.
20. Treat this ADR as the baseline architecture for subsequent ADRs.

###############################################################################

END OF CC-ADR-001

###############################################################################