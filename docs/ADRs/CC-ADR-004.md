###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-004
# Title           : Workflow, Context & Engineering Session Architecture
# Version         : 1.0.0
# Status          : Accepted
#
###############################################################################

# 1. Decision Summary

ClaireCoder SHALL use separate but coordinated systems for:

- Workflow & Planning,
- Context,
- Memory,
- Engineering Sessions.

The Workflow & Planning system SHALL determine how an engineering objective
is decomposed, planned, executed, validated, and replanned.

The Context Engine SHALL determine what information is relevant to the
current model operation.

Engineering Sessions SHALL persist the state of an ongoing engineering task.

Memory SHALL represent durable information that may remain useful beyond the
current session.

These systems SHALL NOT be merged into one generic "agent state" component.

Planning SHALL be adaptive rather than forcing every task through the same
planning depth.

Context SHALL be progressively assembled rather than sending the entire
repository and session history to every model call.

Engineering Sessions SHALL remain resumable after context compaction,
interruption, or process restart.

-------------------------------------------------------------------------------

# 2. Context

CC-RES-004 established the need for adaptive planning and structured
engineering execution.

CC-RES-006 established the distinction between:

Context
    Information required by the model right now.

Memory
    Durable information worth preserving for future work.

Engineering Session
    Persistent state of the current engineering task.

Repository Intelligence
    Information describing the repository and helping retrieve relevant
    project context.

The system must support both small-context local models and large-context
hosted models.

Therefore ClaireCoder cannot depend on sending the complete repository,
conversation, Tool history, and Skill library to every model request.

The architecture must instead determine what information is needed at each
stage of engineering execution.

-------------------------------------------------------------------------------

# 3. Problem

A coding agent performs a long sequence of operations.

For example:

User Request
    ↓
Repository Inspection
    ↓
Planning
    ↓
Implementation
    ↓
Testing
    ↓
Failure
    ↓
Debugging
    ↓
Replanning
    ↓
Validation
    ↓
Completion

During this process, information accumulates.

If all information remains in active context:

- context windows become exhausted,
- model latency increases,
- irrelevant information accumulates,
- small-context models become unusable.

If information is discarded without structure:

- plans are lost,
- previous decisions are forgotten,
- validation results disappear,
- interrupted sessions become difficult to resume.

Therefore ClaireCoder requires explicit separation between active context and
persistent engineering state.

-------------------------------------------------------------------------------

# 4. Decision

ClaireCoder SHALL use the following conceptual architecture:

                         ENGINEERING ENGINE
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
        WORKFLOW &         CONTEXT ENGINE      SESSION
         PLANNING                │              STATE
              │                 │                 │
              │        ┌────────┼────────┐       │
              │        │        │        │       │
              │        ▼        ▼        ▼       │
              │   Repository  Skills   Tools     │
              │    Context   Context   Results   │
              │        │        │        │       │
              │        └────────┼────────┘       │
              │                 │                 │
              │                 ▼                 │
              │           Active Context          │
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                                ▼
                         Model Gateway
                                │
                                ▼
                              Model

Memory SHALL remain a separate persistent information source.

The Context Engine MAY retrieve relevant Memory when required.

-------------------------------------------------------------------------------

# 5. Workflow Architecture

## 5.1 Workflow Definition

A Workflow SHALL represent an engineering process.

Examples include:

- implementation,
- debugging,
- review,
- research,
- testing,
- refactoring.

A Workflow MAY contain:

- objectives,
- stages,
- task dependencies,
- completion criteria,
- validation requirements,
- recovery behavior.

A Workflow SHALL not be equivalent to a Mode.

A Mode controls operational behavior.

A Workflow defines an engineering process.

-------------------------------------------------------------------------------

# 6. Planning Architecture

## 6.1 Adaptive Planning

ClaireCoder SHALL use adaptive planning.

The system SHALL NOT force every request through maximum planning.

Planning depth SHOULD depend on factors such as:

- task complexity,
- repository size,
- number of affected components,
- ambiguity,
- risk,
- dependency count,
- requested Mode,
- available model capabilities.

Simple requests MAY execute directly.

Complex requests SHOULD receive deeper planning.

-------------------------------------------------------------------------------

## 6.2 Planning Levels

The architecture SHALL support conceptual planning levels.

LEVEL 0 — Direct

Used for simple, well-defined operations.

Example:

- rename a variable,
- update a value,
- make a small documentation change.

LEVEL 1 — Lightweight

Used when limited repository inspection is required.

LEVEL 2 — Structured

Used when multiple files or components are involved.

LEVEL 3 — Deep

Used for complex architectural or multi-stage changes.

The final naming and exact thresholds SHALL be determined during
implementation planning.

-------------------------------------------------------------------------------

## 6.3 Planning Output

A plan SHOULD contain:

- objective,
- assumptions,
- affected areas,
- tasks,
- dependencies,
- validation strategy,
- risks,
- completion criteria.

The plan SHALL be persistable inside the Engineering Session.

-------------------------------------------------------------------------------

# 7. Task Model

ClaireCoder SHALL represent engineering work as tasks.

A task MAY contain:

- identifier,
- description,
- status,
- dependencies,
- affected files,
- required Skills,
- required Tools,
- validation requirements,
- result,
- failure information.

Conceptual task states:

PENDING
    ↓
READY
    ↓
IN_PROGRESS
    ↓
VALIDATING
    ↓
COMPLETED

Failure MAY transition a task into:

FAILED
    ↓
REPLAN / RETRY / BLOCKED

The exact state machine SHALL be finalized during implementation design.

-------------------------------------------------------------------------------

# 8. Task Dependencies

Complex Workflows SHALL support task dependencies.

Example:

Task A
    ↓
Task B
    ↓
Task C

or:

        ┌── Task B ──┐
Task A ─┤            ├─ Task D
        └── Task C ──┘

The Planner SHALL be able to determine when a task becomes executable.

Independent tasks MAY be executed concurrently where the Tool and Permission
systems allow it.

-------------------------------------------------------------------------------

# 9. Validation Loop

ClaireCoder SHALL treat validation as part of engineering execution.

The conceptual loop SHALL be:

PLAN
  ↓
IMPLEMENT
  ↓
VALIDATE
  ↓
  ├── PASS → COMPLETE
  │
  └── FAIL
       ↓
    DIAGNOSE
       ↓
     REPLAN
       ↓
    IMPLEMENT
       ↓
    VALIDATE

The agent SHALL not assume that successful file modification means the
engineering task is complete.

-------------------------------------------------------------------------------

# 10. Replanning

The Planner SHALL be able to replan when:

- implementation assumptions are invalid,
- tests fail,
- dependencies differ from expectations,
- repository state changes,
- required capabilities are unavailable,
- new constraints are discovered.

Replanning SHALL update the Engineering Session.

The previous plan SHOULD remain recoverable as historical information where
useful.

-------------------------------------------------------------------------------

# 11. Context Architecture

## 11.1 Context Definition

Context SHALL represent information actively supplied to the model for a
specific operation.

Potential context sources include:

- user request,
- current task,
- current plan,
- relevant files,
- repository structure,
- project instructions,
- active Skills,
- recent Tool results,
- validation state,
- relevant session information,
- relevant Memory.

-------------------------------------------------------------------------------

# 12. Context Layers

ClaireCoder SHALL use a conceptual context hierarchy.

Layer 0 — Immediate Objective

- current user request,
- current action.

Layer 1 — Active Task

- current task,
- current plan section,
- completion criteria.

Layer 2 — Instructions

- project instructions,
- relevant Mode instructions,
- active Skill instructions.

Layer 3 — Repository Context

- repository map,
- relevant files,
- symbols,
- dependencies,
- Git state.

Layer 4 — Execution Context

- Tool results,
- terminal output,
- test failures,
- validation results.

Layer 5 — Session Context

- previous decisions,
- completed tasks,
- unresolved issues.

Layer 6 — Memory

- durable project knowledge,
- relevant long-term decisions.

The Context Engine SHALL select from these layers according to relevance and
available context capacity.

-------------------------------------------------------------------------------

# 13. Context Selection

The Context Engine SHALL prioritize relevance.

A conceptual priority order is:

1. Current objective.
2. Current task.
3. Relevant instructions.
4. Relevant code.
5. Current plan.
6. Current validation state.
7. Recent Tool results.
8. Repository structure.
9. Relevant session history.
10. Optional historical information.

Recency alone SHALL not determine context priority.

-------------------------------------------------------------------------------

# 14. Repository Intelligence

The Context Engine SHALL use Repository Intelligence to locate relevant
repository information.

Repository Intelligence MAY provide:

- directory structure,
- files,
- symbols,
- functions,
- classes,
- imports,
- dependencies,
- relationships,
- project instructions.

Repository Intelligence SHALL help retrieval.

It SHALL not replace the actual source files required for implementation.

-------------------------------------------------------------------------------

# 15. File Retrieval

When a task requires detailed source code, the Context Engine SHOULD retrieve
the relevant file or section rather than relying only on a repository map.

The system SHOULD avoid loading unrelated files.

-------------------------------------------------------------------------------

# 16. Tool Result Context

Tool results SHALL have a defined lifecycle.

Small relevant results MAY remain in active context.

Large results SHOULD be:

- truncated,
- summarized,
- persisted,
- or retrievable by reference.

The Context Engine SHALL preserve important errors and validation information.

-------------------------------------------------------------------------------

# 17. Skill Context

Skills SHALL be loaded progressively.

The Context Engine SHOULD initially use Skill metadata.

Full Skill instructions SHALL be loaded when:

- explicitly activated,
- required by a Workflow,
- required by a Mode,
- or determined relevant by the Skill system.

Supporting references SHOULD only be loaded when required.

-------------------------------------------------------------------------------

# 18. Context Compression

ClaireCoder SHALL support context compression.

Compression SHOULD preserve:

- current objective,
- current plan,
- important decisions,
- current task state,
- validation state,
- unresolved issues,
- relevant repository changes.

Redundant conversation and Tool output MAY be summarized or discarded.

Compression SHALL NOT automatically discard persistent Engineering Session
state.

-------------------------------------------------------------------------------

# 19. Context Budget

The Context Engine SHALL account for model context capacity.

Conceptually:

Model Capacity
      ↓
Reserve Output Space
      ↓
Determine Input Budget
      ↓
Rank Context
      ↓
Load Highest-Value Context
      ↓
Compress / Retrieve as Necessary

The exact token budgeting implementation SHALL be determined later.

-------------------------------------------------------------------------------

# 20. Small-Context Models

ClaireCoder SHALL remain usable with small-context models.

The Context Engine SHOULD compensate through:

- repository mapping,
- targeted file retrieval,
- Tool-result summarization,
- progressive Skill loading,
- context compression,
- session persistence.

A small context window SHALL not automatically make a model unsupported.

-------------------------------------------------------------------------------

# 21. Large-Context Models

Large-context models MAY receive more:

- repository context,
- conversation history,
- Tool results,
- planning information.

However, ClaireCoder SHALL still prefer relevant information over sending
everything.

Large context SHALL be treated as additional capacity, not as a requirement.

-------------------------------------------------------------------------------

# 22. Memory Architecture

Memory SHALL remain separate from active Context and Engineering Session
state.

Memory MAY contain:

- durable project decisions,
- stable architecture information,
- recurring project conventions,
- user-defined engineering preferences,
- important long-term constraints.

Memory SHOULD only enter active Context when relevant.

-------------------------------------------------------------------------------

# 23. Memory Versus Session

The distinction SHALL be:

Memory:

"Information that remains useful beyond this engineering session."

Session:

"State required to continue this engineering session."

Example:

Architecture decision:

    Memory

Current implementation plan:

    Session

Current failing test:

    Session

Stable repository convention:

    Potential Memory

Temporary terminal output:

    Context / Session history

-------------------------------------------------------------------------------

# 24. Engineering Session

An Engineering Session SHALL represent an ongoing engineering objective.

A Session SHOULD contain:

- session identifier,
- title,
- objective,
- Mode,
- Model Profile,
- Workflow,
- plan,
- task state,
- completed tasks,
- pending tasks,
- important decisions,
- validation state,
- unresolved issues,
- changed files,
- relevant repository state,
- timestamps,
- session status.

-------------------------------------------------------------------------------

# 25. Session Lifecycle

The conceptual lifecycle SHALL be:

CREATE
  ↓
UNDERSTAND
  ↓
PLAN
  ↓
EXECUTE
  ↓
VALIDATE
  ↓
  ├── CONTINUE
  │      ↓
  │    EXECUTE
  │
  └── COMPLETE
         ↓
       ARCHIVE

An interrupted session MAY enter:

PAUSED
  ↓
RESUME
  ↓
CONTINUE

-------------------------------------------------------------------------------

# 26. Session Persistence

The Session SHALL persist enough information to resume work.

Persistence SHOULD include:

- plan,
- task states,
- important decisions,
- validation state,
- unresolved issues,
- relevant Tool results,
- changed files,
- current Mode,
- Model Profile.

The system SHALL not need to replay the complete conversation to resume.

-------------------------------------------------------------------------------

# 27. Session Resumption

When a user resumes a Session, ClaireCoder SHOULD:

1. Load Session metadata.
2. Inspect current repository state.
3. Detect relevant changes since the previous execution.
4. Restore the current plan.
5. Restore pending tasks.
6. Restore important decisions.
7. Rebuild only the required active Context.
8. Continue execution.

The entire historical context SHALL not automatically be reloaded.

-------------------------------------------------------------------------------

# 28. Repository State Validation

A resumed Session SHALL verify that repository state has not materially
changed.

Potential changes include:

- modified files,
- branch changes,
- deleted files,
- generated files,
- dependency changes.

If significant differences are detected, ClaireCoder SHOULD inform the
Engineering Engine before continuing blindly.

-------------------------------------------------------------------------------

# 29. Git State

The Engineering Session SHOULD record relevant Git state.

Potential information includes:

- branch,
- commit,
- modified files,
- staged files,
- untracked files.

The exact Git snapshot mechanism SHALL be determined during implementation.

-------------------------------------------------------------------------------

# 30. Subagent Context

Subagents SHALL receive task-specific Context.

A subagent SHOULD receive:

- task objective,
- relevant files,
- relevant Skills,
- required Tools,
- required constraints,
- required validation criteria.

A subagent SHALL NOT automatically inherit the entire parent conversation.

-------------------------------------------------------------------------------

# 31. Subagent Results

A subagent SHOULD return a compact structured result containing:

- outcome,
- changes,
- findings,
- validation,
- unresolved issues.

The parent Engineering Engine SHALL decide what information enters the
active Context.

This prevents every subagent's complete execution history from accumulating
inside the primary model context.

-------------------------------------------------------------------------------

# 32. Workflow and Mode Interaction

Modes SHALL influence Workflow behavior.

For example:

PLAN Mode
    ↓
Planning-focused Workflow

BUILD Mode
    ↓
Implementation-focused Workflow

REVIEW Mode
    ↓
Inspection-focused Workflow

DEBUG Mode
    ↓
Diagnostic Workflow

The Mode does not become the Workflow.

The Workflow remains responsible for the engineering process.

-------------------------------------------------------------------------------

# 33. Model Interaction

The Workflow and Context systems SHALL interact with the Model Gateway through
capability requirements.

For example:

Workflow requirement:

    "Requires vision."

Context Engine:

    "Relevant image available."

Model Gateway:

    "Selected model supports vision."

Execution:

    Continue.

If the selected model does not support the required capability, the system
MAY:

- select another model,
- modify the Workflow,
- ask the user,
- fail clearly.

-------------------------------------------------------------------------------

# 34. Error Handling

The Workflow system SHALL distinguish:

- Tool failure,
- model failure,
- validation failure,
- planning failure,
- context failure,
- permission failure,
- repository-state conflict.

The Engineering Engine SHALL determine whether the correct response is:

- retry,
- replan,
- switch model,
- request permission,
- request user input,
- terminate.

-------------------------------------------------------------------------------

# 35. Decision Rationale

This architecture was selected because it provides a clean separation between
three different forms of state:

Active Context
    What the model needs now.

Engineering Session
    What the engineering process needs to continue.

Memory
    What should remain useful beyond the current session.

It also allows adaptive planning and context management without making large
context windows mandatory.

This architecture supports:

- small local models,
- large hosted models,
- short tasks,
- long-running tasks,
- interrupted work,
- resumable sessions,
- complex multi-step engineering,
- bounded subagents.

-------------------------------------------------------------------------------

# 36. Alternatives Considered

## Alternative A — Store Everything in Conversation History

Decision:

REJECTED.

Reason:

Conversation history grows indefinitely and does not provide structured
engineering state.

-------------------------------------------------------------------------------

## Alternative B — One Unified Context/Memory Database

Decision:

REJECTED.

Reason:

Active context, session state, and durable memory have different lifecycles
and retention requirements.

-------------------------------------------------------------------------------

## Alternative C — Always Use Maximum Planning

Decision:

REJECTED.

Reason:

Simple tasks would become slower and more expensive than necessary.

-------------------------------------------------------------------------------

## Alternative D — Never Persist Plans

Decision:

REJECTED.

Reason:

Context compression and process interruption would make long-running tasks
difficult to resume.

-------------------------------------------------------------------------------

## Alternative E — Always Send the Entire Repository

Decision:

REJECTED.

Reason:

This wastes context and prevents efficient operation with smaller models.

-------------------------------------------------------------------------------

# 37. Consequences

## Positive Consequences

- Adaptive planning.
- Efficient context usage.
- Small-context model support.
- Large-context model support.
- Resumable engineering sessions.
- Persistent plans.
- Clear state separation.
- Better subagent isolation.
- Better recovery.
- Reduced context growth.

## Negative Consequences

- Multiple state systems must be maintained.
- Context selection requires relevance logic.
- Session persistence requires structured state.
- Compression can lose information if implemented incorrectly.
- Repository changes must be detected during session resumption.

These costs are accepted because reliable long-running engineering requires
explicit state management.

-------------------------------------------------------------------------------

# 38. V1 Boundary

The following SHALL be part of the V1 architecture:

Workflow:

- adaptive planning,
- task model,
- task dependencies,
- validation loop,
- replanning,
- Workflow state.

Context:

- layered context,
- repository retrieval,
- Skill context,
- Tool-result context,
- context budgeting,
- compression,
- model-capacity awareness.

Engineering Session:

- session persistence,
- plan persistence,
- task state,
- validation state,
- resumption,
- interruption recovery.

Memory:

- basic durable engineering memory concept,
- relevant-memory retrieval.

The following MAY remain optional:

- advanced semantic memory,
- vector databases,
- sophisticated automatic memory formation,
- cross-project memory,
- advanced long-term knowledge graphs.

ClaireCoder SHALL not require a vector database or complex memory system for
V1.

-------------------------------------------------------------------------------

# 39. Implementation Guidance

The implementation SHOULD initially favor:

- explicit state objects,
- deterministic Workflow transitions,
- simple persistent session files or database storage,
- structured plans,
- bounded Context assembly,
- explicit compression events,
- repository-aware retrieval.

The implementation SHALL avoid:

- storing every Tool result permanently,
- automatically loading every Memory item,
- automatically loading the entire repository,
- forcing maximum planning,
- requiring a vector database,
- creating a distributed session service for V1.

-------------------------------------------------------------------------------

# 40. Decision Status

STATUS

ACCEPTED

This ADR establishes the Workflow, Context, and Engineering Session
architecture for ClaireCoder V1.

Later ADRs MAY refine:

- interaction behavior,
- commands,
- Modes,
- permissions,
- model integration,
- extension behavior.

Any fundamental change to Workflow, Context, Memory, or Session boundaries
SHALL explicitly supersede this ADR.

-------------------------------------------------------------------------------

# 41. Relationship With Other ADRs

CC-ADR-001

ClaireCoder Core Architecture

Defines the overall system boundaries.

CC-ADR-002

Model Gateway & Provider Architecture

Defines model execution and capability negotiation.

CC-ADR-003

Tool & Skill Extension Architecture

Defines executable Tools and reusable Skills.

CC-ADR-004

Workflow, Context & Engineering Session Architecture

Defines engineering execution, context, and persistent session state.

CC-ADR-005

Interaction, Modes & Command Architecture

Defines the user-facing control system.

CC-ADR-006

Permission, Autonomy & Security Architecture

Defines execution security and autonomy.

-------------------------------------------------------------------------------

# 42. AI Instructions

When implementing or documenting ClaireCoder after this ADR:

1. Keep Workflow separate from Mode.
2. Keep Context separate from Session.
3. Keep Memory separate from both Context and Session.
4. Use adaptive planning.
5. Preserve direct execution for simple tasks.
6. Support deeper planning for complex tasks.
7. Persist plans independently from conversation history.
8. Preserve validation state.
9. Preserve resumable Engineering Sessions.
10. Rebuild active Context when resuming instead of replaying everything.
11. Use Repository Intelligence for targeted retrieval.
12. Prefer relevant context over indiscriminate context.
13. Use progressive Skill loading.
14. Summarize or persist large Tool results.
15. Keep subagent Context bounded.
16. Support small-context models.
17. Support large-context models without depending on them.
18. Do not make vector databases mandatory for V1.
19. Do not over-engineer Memory.
20. Preserve deterministic Workflow state.
21. Preserve ClaireCoder's simplicity.
22. Treat this ADR as the authoritative Workflow, Context, and Engineering
    Session architecture unless explicitly superseded.

###############################################################################

END OF CC-ADR-004

###############################################################################