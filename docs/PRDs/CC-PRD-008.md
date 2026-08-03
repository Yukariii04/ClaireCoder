###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                  Product Requirements Document
#
# Document Number : CC-PRD-008
# Title           : Engineering Context & Memory
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

CC-PRD-008 defines the Context and Memory subsystem of ClaireCoder.

ClaireCoder is intended to understand projects, plan engineering work, execute
workflows, review results, test implementations, document changes, and
continuously improve software projects.

The Engineering Engine requires controlled access to information about:

- the current engineering Session,
- the active Workflow,
- active Tasks,
- repository state,
- Tool results,
- previous decisions,
- relevant project information,
- developer instructions.

The Context and Memory subsystem SHALL provide this information without
coupling ClaireCoder to a specific language model, provider, storage system, or
IDE.

The subsystem SHALL distinguish between:

    CONTEXT
        Information currently required to perform an operation.

    MEMORY
        Information retained for possible future use.

The system SHALL NOT treat all available information as equally relevant.

The architecture SHALL prioritize controlled context construction over
unbounded accumulation of information.

-------------------------------------------------------------------------------

# 2. Purpose

The purpose of CC-PRD-008 is to define:

- Engineering Context,
- Context sources,
- Context construction,
- Context boundaries,
- Memory categories,
- Memory lifecycle,
- Memory relevance,
- Memory retrieval,
- memory provenance,
- context isolation,
- context invalidation,
- session memory,
- project memory,
- decision memory,
- execution history integration.

The subsystem SHALL support both local and hosted models because ClaireCoder's
architecture is required to support both execution environments.

-------------------------------------------------------------------------------

# 3. Architectural Position

The Context and Memory subsystem SHALL operate as an infrastructure layer
between the Engineering Engine and model interaction.

    Engineering Engine
           │
           ├── Workflow
           ├── Tasks
           ├── Tools
           └── Skills
                  │
                  ▼
        Context & Memory
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
     Context              Memory
        │                   │
        └─────────┬─────────┘
                  ▼
             Model Gateway
                  │
                  ▼
                Model

The Engineering Engine remains the primary orchestration layer.

Models, Tools, Workflows, and Skills SHALL remain replaceable components,
consistent with the ClaireCoder architectural foundation.

-------------------------------------------------------------------------------

# 4. Scope

## 4.1 In Scope

Implement:

- Context model.
- Context sources.
- Context assembly.
- Context prioritization.
- Context limits.
- Session memory.
- Project memory.
- Decision memory.
- Task-related memory.
- Execution-result references.
- Memory metadata.
- Memory provenance.
- Memory relevance.
- Memory retrieval.
- Memory invalidation.
- Context isolation.
- Memory safety boundaries.
- Context serialization.
- Context inspection.

-------------------------------------------------------------------------------

## 4.2 Out of Scope

Do NOT implement:

- a specific database,
- vector database requirements,
- embeddings,
- semantic-search implementation,
- model inference,
- model provider selection,
- autonomous memory creation without policy,
- user profiling,
- external knowledge graph,
- IDE-specific memory,
- cross-user memory,
- secret storage,
- authentication.

Future PRDs MAY introduce specialized retrieval implementations.

-------------------------------------------------------------------------------

# 5. Design Principles

ClaireCoder SHALL:

- remain model independent,
- remain provider independent,
- remain workflow driven,
- remain repository aware,
- remain modular,
- remain extensible,
- preserve user control,
- support local and remote execution.

The Context and Memory subsystem SHALL additionally be:

- bounded,
- inspectable,
- provenance-aware,
- deterministic where practical,
- relevance-oriented,
- privacy-conscious,
- replaceable,
- failure-safe.

The architecture SHALL remain architecture-first rather than implementation-
first.

-------------------------------------------------------------------------------

# 6. Context Definition

Context is information supplied to an engineering operation because it is
relevant to that operation.

Context MAY include:

    Current Session
    Current Workflow
    Current Task
    Task Dependencies
    Repository State
    Relevant Files
    Tool Results
    Previous Decisions
    Developer Instructions
    Relevant Memory

Context SHALL be assembled for a specific operation.

The system SHALL NOT assume that one global context is appropriate for every
operation.

-------------------------------------------------------------------------------

# 7. Memory Definition

Memory is retained information that MAY become useful to future engineering
operations.

Memory SHALL have an explicit category.

V1 SHALL support:

    SESSION_MEMORY
    PROJECT_MEMORY
    DECISION_MEMORY
    TASK_MEMORY

No additional memory categories SHALL be required for V1.

-------------------------------------------------------------------------------

# 8. Session Memory

Session Memory represents information relevant to the current engineering
Session.

Examples:

- current objective,
- current Workflow,
- active Tasks,
- recent Tool results,
- current execution state,
- temporary decisions,
- current developer instructions.

Session Memory SHALL normally expire when the engineering Session ends unless
explicitly promoted to another memory category.

-------------------------------------------------------------------------------

# 9. Project Memory

Project Memory represents information that remains relevant across engineering
Sessions for the same project.

Examples:

- project architecture,
- established conventions,
- important configuration decisions,
- repository structure,
- recurring engineering constraints.

Project Memory SHALL be scoped to the relevant project.

The system SHALL NOT assume that Project Memory applies to unrelated projects.

-------------------------------------------------------------------------------

# 10. Decision Memory

Decision Memory represents an engineering decision that should remain available
to future operations.

Example:

    Decision:
        Use PostgreSQL for persistent storage.

    Reason:
        Existing deployment infrastructure already supports PostgreSQL.

    Scope:
        Project

    Status:
        Active

Decision Memory SHALL preserve both the decision and its relevant reasoning
where available.

-------------------------------------------------------------------------------

# 11. Task Memory

Task Memory represents information specifically associated with a Task.

Examples:

- Task-specific assumptions,
- failed attempts,
- successful approaches,
- relevant Tool output,
- verification results.

Task Memory SHALL remain associated with the Task identity.

-------------------------------------------------------------------------------

# 12. Memory Record

Conceptual model:

    MemoryRecord
        │
        ├── memoryId
        ├── category
        ├── content
        ├── scope
        ├── source
        ├── provenance
        ├── createdAt
        ├── updatedAt
        └── status

Memory records SHALL have stable identities.

-------------------------------------------------------------------------------

# 13. Memory Scope

V1 SHALL support:

    SESSION
    TASK
    PROJECT

A memory record SHALL have exactly one primary scope.

Scope determines where the memory MAY be retrieved.

-------------------------------------------------------------------------------

# 14. Memory Provenance

Every retained memory SHOULD identify its source.

Possible sources:

    USER
    WORKFLOW
    TOOL
    REPOSITORY
    SYSTEM
    MODEL

The source SHALL NOT automatically determine trust.

Provenance exists to allow the Engineering Engine to understand where
information originated.

-------------------------------------------------------------------------------

# 15. User Information

Developer-provided information SHALL be treated as explicitly sourced
information.

Examples:

    "This project must use Python."

    "Do not modify the production database."

Such information MAY be retained according to its scope.

The system SHALL distinguish explicit developer instructions from model-generated
assumptions.

-------------------------------------------------------------------------------

# 16. Model-Generated Memory

The model MAY propose a memory item.

A model proposal SHALL NOT automatically become authoritative Project Memory.

Conceptually:

    Model
      ↓
    Memory Proposal
      ↓
    Memory Policy
      ↓
    ACCEPT / REJECT / REVIEW

This prevents generated assumptions from silently becoming project facts.

-------------------------------------------------------------------------------

# 17. Repository-Derived Memory

Repository information MAY be used as context.

Examples:

- directory structure,
- configuration,
- documentation,
- source code,
- dependency information.

Repository-derived information SHALL remain distinguishable from manually
declared project decisions.

-------------------------------------------------------------------------------

# 18. Context Sources

V1 SHALL recognize the following Context sources:

    SYSTEM
    USER
    SESSION
    WORKFLOW
    TASK
    REPOSITORY
    TOOL
    MEMORY

The source ordering SHALL be explicit.

-------------------------------------------------------------------------------

# 19. Context Priority

When information conflicts, the system SHALL preserve source provenance and
apply an explicit priority policy.

At minimum:

    SYSTEM
       ↓
    DEVELOPER / USER CONSTRAINTS
       ↓
    CURRENT WORKFLOW
       ↓
    CURRENT TASK
       ↓
    VERIFIED REPOSITORY FACTS
       ↓
    VERIFIED TOOL RESULTS
       ↓
    MEMORY
       ↓
    MODEL INFERENCE

Memory SHALL not silently override an explicit current instruction.

-------------------------------------------------------------------------------

# 20. Current Context Over Historical Memory

Current authoritative information SHALL take precedence over stale historical
memory.

Example:

    Old Memory:
        "Project uses React 18."

    Current Repository:
        package.json → React 19

The current repository state SHALL be treated as more relevant than the stale
memory.

The stale memory SHOULD be marked for invalidation or review.

-------------------------------------------------------------------------------

# 21. Context Construction

Context construction SHALL follow:

    Identify Operation
          ↓
    Identify Required Sources
          ↓
    Retrieve Relevant Information
          ↓
    Validate Provenance
          ↓
    Prioritize
          ↓
    Apply Context Limits
          ↓
    Build Context
          ↓
    Send to Model

The model SHALL receive only the context required for the operation whenever
practical.

-------------------------------------------------------------------------------

# 22. Context Object

Conceptual model:

    EngineeringContext
        │
        ├── contextId
        ├── session
        ├── workflow
        ├── task
        ├── repository
        ├── memories
        ├── toolResults
        ├── instructions
        └── metadata

The Context object SHALL be immutable after construction.

If context changes, a new Context SHALL be constructed.

-------------------------------------------------------------------------------

# 23. Context Snapshot

Every model interaction SHOULD operate against a Context snapshot.

Example:

    Context #001
        ↓
    Model Request
        ↓
    Tool Execution
        ↓
    Repository Changes
        ↓
    Context #002

The system SHALL not assume that Context #001 remains valid after repository
mutation.

-------------------------------------------------------------------------------

# 24. Context Invalidation

Context MAY become invalid when:

- repository files change,
- Task state changes,
- Workflow changes,
- permissions change,
- Tool results change,
- developer instructions change,
- relevant memory changes.

Invalidated context SHALL not be silently reused when correctness depends on
the changed information.

-------------------------------------------------------------------------------

# 25. Context Version

Context SHOULD have a version or immutable identity.

This allows:

    Request → Context A

to remain distinguishable from:

    Request → Context B

even when both belong to the same Session.

-------------------------------------------------------------------------------

# 26. Context Size

The system SHALL support configurable Context limits.

The implementation SHALL NOT assume that an unlimited amount of repository
content can be provided to a model.

Context limits MAY be based on:

- token budget,
- item count,
- byte size,
- source priority.

The specific model tokenizer SHALL not be required by this PRD.

-------------------------------------------------------------------------------

# 27. Context Budget

A Context budget SHOULD be divided according to priority.

Conceptually:

    Mandatory Context
        +
    Task Context
        +
    Relevant Repository Context
        +
    Relevant Memory
        +
    Optional Context

When the budget is exceeded, lower-priority information SHALL be removed
before mandatory information.

-------------------------------------------------------------------------------

# 28. Context Relevance

A memory item SHOULD be retrieved only when it is relevant to the current
operation.

Relevance MAY be determined by:

- explicit scope,
- Task relationship,
- Workflow relationship,
- repository relationship,
- keywords,
- metadata,
- future semantic retrieval mechanisms.

The PRD SHALL not mandate a specific retrieval algorithm.

-------------------------------------------------------------------------------

# 29. Memory Retrieval

Public API:

    createMemory()
    getMemory()
    updateMemory()
    deleteMemory()
    retrieveMemory()
    invalidateMemory()
    buildContext()

Only these APIs SHALL be public within the Context and Memory subsystem boundary in V1. They SHALL NOT automatically become top-level ClaireCoder package APIs.

-------------------------------------------------------------------------------

# 30. Memory Creation

Memory creation SHALL require:

- category,
- scope,
- content,
- provenance.

The system SHOULD additionally record:

- source identity,
- creation time,
- related Task,
- related Workflow,
- related repository.

-------------------------------------------------------------------------------

# 31. Memory Update

Memory MAY be updated when new verified information supersedes the previous
record.

Updates SHOULD preserve the memory identity where practical.

The system SHOULD preserve revision information for important Project and
Decision Memory.

-------------------------------------------------------------------------------

# 32. Memory Deletion

Memory deletion SHALL be explicit.

Deletion MAY be triggered by:

- developer instruction,
- invalidation,
- expiration,
- project removal,
- policy.

The system SHALL not silently delete important Project or Decision Memory
merely because it was not recently retrieved.

-------------------------------------------------------------------------------

# 33. Memory Invalidation

Invalidation differs from deletion.

    DELETE
        Memory no longer exists.

    INVALIDATE
        Memory exists historically but SHALL no longer be treated as active
        context.

This distinction SHALL be preserved.

-------------------------------------------------------------------------------

# 34. Memory Status

V1 SHALL support:

    ACTIVE
    INVALID
    ARCHIVED

ACTIVE memories MAY be retrieved.

INVALID memories SHALL not be automatically included in Context.

ARCHIVED memories MAY be explicitly retrieved for historical purposes.

-------------------------------------------------------------------------------

# 35. Memory Conflict

If two memories conflict:

    Memory A
        "Use SQLite."

    Memory B
        "Use PostgreSQL."

The system SHALL not silently choose one merely because it was retrieved first.

The conflict SHALL be surfaced to the Engineering Engine.

-------------------------------------------------------------------------------

# 36. Decision Conflicts

Decision Memory conflicts SHOULD result in:

    CONFLICT DETECTED
          ↓
    ENGINEERING REVIEW
          ↓
    RESOLVE
          ↓
    UPDATE DECISION MEMORY

The model MAY recommend a resolution, but the resolution SHALL remain subject
to the project's decision policy.

-------------------------------------------------------------------------------

# 37. Memory Trust

V1 SHALL distinguish:

    VERIFIED
    UNVERIFIED

An unverified memory SHALL not be treated as equivalent to a verified
repository fact.

Model-generated assumptions SHOULD default to UNVERIFIED.

Explicit developer declarations MAY be considered authoritative according to
their scope.

-------------------------------------------------------------------------------

# 38. Memory Promotion

Information MAY be promoted:

    Session Memory
          ↓
    Project Memory

or:

    Task Memory
          ↓
    Decision Memory

Promotion SHALL require an explicit policy decision.

The system SHALL not promote every useful-looking observation into permanent
memory.

-------------------------------------------------------------------------------

# 39. Memory Expiration

Session Memory SHOULD expire when the Session ends.

Task Memory MAY expire after Task completion unless it remains relevant.

Project Memory and Decision Memory SHOULD persist until explicitly invalidated,
superseded, or archived.

-------------------------------------------------------------------------------

# 40. Execution Integration

CC-PRD-007 establishes explicit Task and Execution lifecycle.

Context MAY contain:

- current Task state,
- current Execution state,
- previous attempts,
- failure information,
- verification results.

The Context subsystem SHALL consume this information.

It SHALL not replace the execution state machine.

-------------------------------------------------------------------------------

# 41. Tool Result Integration

Tool results MAY become Context.

However:

    Tool Result
        ≠
    Permanent Memory

A Tool result SHALL be retained as memory only when memory policy determines
that it has future value.

-------------------------------------------------------------------------------

# 42. Repository Integration

Repository information SHALL be treated as dynamic.

A repository can change during an engineering Session.

Therefore:

    Repository Context
          ↓
       Snapshot
          ↓
      Execution
          ↓
    Repository Mutation
          ↓
      New Snapshot

The system SHALL avoid treating stale repository Context as current fact.

-------------------------------------------------------------------------------

# 43. Workflow Integration

Workflows MAY define required Context.

Example:

    Code Review Workflow
        ↓
    Relevant source files
        +
    Tests
        +
    Recent changes
        +
    Architecture decisions

The Context subsystem SHALL provide the requested information without owning
Workflow logic.

-------------------------------------------------------------------------------

# 44. Skill Integration

Skills MAY request Context.

A Skill SHALL receive only the Context necessary for its operation whenever
practical.

Skills SHALL not automatically receive all available Project Memory.

-------------------------------------------------------------------------------

# 45. Model Integration

The Model Gateway SHALL receive a constructed EngineeringContext.

The model SHALL not directly access the underlying Memory Store.

Conceptually:

    Model
      ↓
    Context Request
      ↓
    Context Builder
      ↓
    Memory Retrieval
      ↓
    EngineeringContext
      ↓
    Model

This keeps memory architecture independent of model providers.

-------------------------------------------------------------------------------

# 46. Security Boundary

Memory SHALL NOT become a secret-storage mechanism.

The system SHALL avoid storing:

- passwords,
- API keys,
- access tokens,
- private credentials,
- authentication secrets.

Sensitive Tool results SHALL not automatically become Memory.

-------------------------------------------------------------------------------

# 47. Context Isolation

Contexts SHALL be isolated by project and Session where appropriate.

Information from Project A SHALL not automatically appear in Project B.

Information from one unrelated Session SHALL not automatically appear in
another Session.

-------------------------------------------------------------------------------

# 48. Cross-Project Memory

V1 SHALL NOT implement unrestricted cross-project memory.

Any future cross-project memory mechanism SHALL require an explicit scope and
security model.

-------------------------------------------------------------------------------

# 49. Developer Inspection

The developer SHOULD be able to inspect:

- active Context,
- Context sources,
- retrieved memories,
- memory provenance,
- memory status,
- context version,
- omitted information due to limits.

The purpose is transparency.

ClaireCoder's foundation explicitly prioritizes engineering quality,
transparency, extensibility, and developer control.

-------------------------------------------------------------------------------

# 50. Context Explainability

The system SHOULD be capable of answering:

    Why was this memory included?

and:

    Why was this information excluded?

Each Context item SHOULD therefore retain metadata describing its source and
selection reason where practical.

-------------------------------------------------------------------------------

# 51. Memory Retrieval Failure

If memory retrieval fails:

    Context construction
           ↓
    Memory unavailable
           ↓
    Continue without optional memory

unless the requested memory is explicitly required for safe execution.

The system SHALL distinguish:

    OPTIONAL MEMORY FAILURE

from:

    REQUIRED CONTEXT FAILURE

-------------------------------------------------------------------------------

# 52. Required Context Failure

If required Context cannot be constructed:

    Context Construction Failure
             ↓
          BLOCKED

The Engineering Engine SHALL not pretend that execution can safely proceed.

-------------------------------------------------------------------------------

# 53. Context Determinism

Given the same:

- Session,
- Workflow,
- Task,
- repository snapshot,
- memory state,
- context policy,

the Context Builder SHOULD produce equivalent Context.

External nondeterministic retrieval MAY be introduced by future systems but
SHALL remain observable.

-------------------------------------------------------------------------------

# 54. Memory Versioning

Important Project and Decision Memory SHOULD support revisions.

Example:

    Decision v1
        ↓
    Decision v2
        ↓
    Decision v3

Only the current ACTIVE revision SHOULD normally enter Context.

Historical revisions MAY be inspected.

-------------------------------------------------------------------------------

# 55. Memory Auditability

The system SHOULD preserve:

- who or what created memory,
- when it was created,
- why it was created,
- what scope it belongs to,
- whether it was verified,
- whether it was invalidated.

This supports engineering transparency.

-------------------------------------------------------------------------------

# 56. Failure Safety

The system SHALL prefer:

    Missing Context

over:

    Incorrect Context

when the missing information is known to be required for correctness.

ClaireCoder SHALL not manufacture missing project facts merely to fill a
Context budget.

-------------------------------------------------------------------------------

# 57. Autonomy Integration

Autonomous operation MAY create or update memory only within defined policy.

At lower autonomy:

    Memory Proposal
        ↓
    Developer Review
        ↓
    Accept

At higher autonomy:

    Memory Proposal
        ↓
    Policy Validation
        ↓
    Accept / Reject

Autonomy SHALL not grant authority to store secrets or cross-project
information.

-------------------------------------------------------------------------------

# 58. Acceptance Criteria

CC-PRD-008 SHALL be considered complete when:

### AC-001 — Context Model

EngineeringContext exists as a distinct object.

### AC-002 — Memory Model

MemoryRecord exists with explicit identity and metadata.

### AC-003 — Memory Categories

Session, Project, Decision, and Task Memory are supported.

### AC-004 — Memory Scope

Memory can be scoped to Session, Task, or Project.

### AC-005 — Provenance

Memory records preserve their source.

### AC-006 — Context Sources

System, User, Session, Workflow, Task, Repository, Tool, and Memory sources
are distinguishable.

### AC-007 — Context Construction

Context can be assembled for a specific engineering operation.

### AC-008 — Context Priority

Higher-priority information is preserved when context limits are reached.

### AC-009 — Context Immutability

Constructed Context snapshots cannot be silently mutated.

### AC-010 — Invalidation

Stale Context can be invalidated.

### AC-011 — Memory Invalidation

Memory can be invalidated without necessarily being deleted.

### AC-012 — Memory Conflict

Conflicting memories are detected rather than silently reconciled.

### AC-013 — Memory Promotion

Temporary information is not automatically promoted to permanent memory.

### AC-014 — Repository Awareness

Repository Context can reflect changing repository state.

### AC-015 — Execution Integration

Task and Execution state can be included in Context.

### AC-016 — Model Independence

Memory architecture does not depend on one model.

### AC-017 — Provider Independence

Memory architecture does not depend on one provider.

### AC-018 — Project Isolation

Project memory cannot automatically leak into unrelated projects.

### AC-019 — Secret Safety

Memory does not become unrestricted credential storage.

### AC-020 — Developer Inspection

Context sources and memory provenance can be inspected.

### AC-021 — Required Context Failure

Missing required Context prevents unsafe execution.

### AC-022 — Optional Memory Failure

Optional memory retrieval failure does not necessarily stop execution.

### AC-023 — Memory Status

ACTIVE, INVALID, and ARCHIVED are represented.

### AC-024 — Memory Verification

Verified and unverified memory can be distinguished.

### AC-025 — Context Versioning

Context snapshots can be uniquely identified.

### AC-026 — Auditability

Important memory operations preserve provenance and timestamps.

### AC-027 — Autonomy

Memory behavior respects the configured autonomy level.

-------------------------------------------------------------------------------

# 59. Non-Functional Requirements

## NFR-001 — Modularity

Memory implementation SHALL remain replaceable.

## NFR-002 — Transparency

Context construction SHALL be inspectable.

## NFR-003 — Isolation

Project and Session boundaries SHALL be enforceable.

## NFR-004 — Boundedness

Context SHALL support explicit limits.

## NFR-005 — Provenance

Important Context information SHALL retain source metadata.

## NFR-006 — Safety

Missing or uncertain information SHALL not be silently fabricated.

## NFR-007 — Extensibility

Future retrieval systems SHALL be introducible without changing the Context
contract.

## NFR-008 — Provider Independence

No memory mechanism SHALL require a specific AI provider.

-------------------------------------------------------------------------------

# 60. Deliverables

Implementation SHALL produce:

1. EngineeringContext model.
2. MemoryRecord model.
3. Context source model.
4. Memory category model.
5. Memory scope model.
6. Memory status model.
7. Provenance model.
8. Context Builder.
9. Memory Store interface.
10. Memory retrieval interface.
11. Context prioritization.
12. Context budgeting.
13. Context invalidation.
14. Memory invalidation.
15. Memory promotion policy.
16. Memory conflict detection.
17. Context serialization.
18. Context inspection mechanism.
19. Project isolation.
20. Security boundaries.
21. Unit tests.
22. Integration tests.

-------------------------------------------------------------------------------

# 61. Verification Strategy

## Unit Tests

Test:

- memory creation,
- retrieval,
- update,
- deletion,
- invalidation,
- status transitions,
- provenance,
- scope.

## Context Tests

Test:

- Context construction,
- source ordering,
- prioritization,
- context limits,
- snapshot identity,
- invalidation.

## Conflict Tests

Test:

    Memory A
       +
    Memory B
       ↓
    Conflict

Verify that the system does not silently select one.

## Repository Tests

Verify that repository changes invalidate stale Context.

## Isolation Tests

Verify:

    Project A Memory
        X
    Project B Context

## Security Tests

Verify that credential-like information does not automatically become Memory.

## Execution Tests

Verify that Task state and Execution state can be incorporated into Context.

-------------------------------------------------------------------------------

# 62. Forbidden

Do NOT:

- make memory provider-specific,
- make Context provider-specific,
- require a vector database,
- require embeddings,
- require a specific database,
- automatically store every model response,
- automatically promote every observation to Project Memory,
- allow model-generated assumptions to silently become authoritative facts,
- mix unrelated project memory,
- use Memory as unrestricted credential storage,
- allow stale repository information to masquerade as current state,
- silently resolve conflicting memories,
- allow missing required Context to be replaced with fabricated information,
- allow memory retrieval to bypass security boundaries,
- create unrestricted cross-project memory,
- couple Context construction to one model tokenizer,
- replace the Engineering Engine,
- replace Workflow architecture,
- replace Task execution state.

-------------------------------------------------------------------------------

# 63. Relationship With Previous PRDs

## CC-PRD-001

Defines the Engineering Engine.

CC-PRD-008 provides the Context and Memory infrastructure used by that engine.

## CC-PRD-002

Defines the Model Gateway.

CC-PRD-008 constructs the information supplied to the Model Gateway without
depending on its provider.

## CC-PRD-003

Defines Tools and Skills.

Tool results and Skill requirements MAY become Context.

## CC-PRD-004

Defines Workflow and Session behavior.

Workflow and Session state MAY contribute to Context.

## CC-PRD-005

Defines developer interaction.

The interaction layer MAY expose Context and Memory inspection.

## CC-PRD-006

Defines Permission, Autonomy & Security.

Memory and Context SHALL remain subordinate to those security boundaries.

## CC-PRD-007

Defines Execution State and Recovery.

Execution state MAY become Context, while Context and Memory remain separate
from execution lifecycle authority.

-------------------------------------------------------------------------------

# 64. Architectural Summary

The resulting architecture SHALL be:

    PROJECT
       │
       ├───────────────┐
       ▼               ▼
    REPOSITORY       MEMORY
       │               │
       └───────┬───────┘
               ▼
           CONTEXT
               │
      ┌────────┼────────┐
      ▼        ▼        ▼
   WORKFLOW   TASK    EXECUTION
      │        │        │
      └────────┼────────┘
               ▼
        CONTEXT BUILDER
               │
               ▼
         ENGINEERING ENGINE
               │
               ▼
          MODEL GATEWAY
               │
               ▼
             MODEL

The central principle is:

    Memory is retained information.

    Context is selected information.

    The Engineering Engine decides when Context is required.

    The Model consumes Context.

    The Model does not own Memory.

-------------------------------------------------------------------------------

# 65. AI Instructions

When implementing CC-PRD-008:

1. Treat Context and Memory as separate concepts.
2. Keep Context operation-specific.
3. Keep Memory explicitly scoped.
4. Preserve memory provenance.
5. Preserve memory status.
6. Preserve project isolation.
7. Do not automatically store every model response.
8. Do not allow model assumptions to become authoritative facts silently.
9. Prefer current verified repository state over stale historical memory.
10. Preserve explicit developer instructions.
11. Detect conflicting memories.
12. Do not silently reconcile conflicting project decisions.
13. Keep Context immutable after construction.
14. Support Context snapshots.
15. Support Context invalidation.
16. Support bounded Context construction.
17. Prioritize mandatory information over optional memory.
18. Keep Task and Execution state separate from Memory lifecycle.
19. Keep Tool results separate from permanent Memory.
20. Never use Memory as unrestricted secret storage.
21. Do not require a specific database.
22. Do not require vector search.
23. Do not require embeddings.
24. Do not couple the architecture to a specific model.
25. Do not couple the architecture to a specific provider.
26. Preserve Workflow/Context separation.
27. Preserve Engineering Engine authority.
28. Preserve Permission and Security boundaries.
29. Preserve developer control.
30. Preserve ClaireCoder's long-term extensibility.
31. Fail safely when required Context is unavailable.
32. Do not fabricate missing project information.
33. Keep the architecture-first philosophy intact.

###############################################################################

END OF CC-PRD-008

###############################################################################