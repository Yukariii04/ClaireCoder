###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Product Requirements Document
#
# Document Number : CC-PRD-007
# Title           : ClaireCoder Execution State & Recovery
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

CC-PRD-007 defines the execution-state and recovery system of ClaireCoder.

ClaireCoder is intended to operate across the complete software-engineering
lifecycle, including planning, implementation, review, testing, documentation,
and continuous improvement.

Because ClaireCoder supports progressively higher levels of engineering
autonomy, it SHALL maintain an explicit representation of what it is currently
doing, what has completed, what failed, and what can safely continue.

The Execution State System SHALL provide the Engineering Engine with a
deterministic operational state independent of the underlying model.

The fundamental pipeline SHALL be:

    ENGINEERING OBJECTIVE
           ↓
        WORKFLOW
           ↓
          TASK
           ↓
       EXECUTION
           ↓
       RESULT
           ↓
    VALIDATION / REVIEW
           ↓
       COMPLETION
           
or, when execution fails:

           ↓
         FAILURE
           ↓
       RECOVERY
           ↓
      RETRY / PAUSE / ABORT

The system SHALL prevent a model response from being treated as proof that an
engineering operation completed successfully.

-------------------------------------------------------------------------------

# 2. Purpose

The purpose of CC-PRD-007 is to establish:

- explicit execution state,
- Task lifecycle,
- execution boundaries,
- failure classification,
- retry behavior,
- recovery behavior,
- cancellation,
- pause/resume,
- completion verification,
- execution history,
- state consistency.

The system SHALL remain independent of:

- model provider,
- model architecture,
- Tool implementation,
- Skill implementation,
- Workflow implementation,
- CLI/TUI implementation.

-------------------------------------------------------------------------------

# 3. Architectural Position

CC-PRD-007 sits between workflow orchestration and Tool execution.

    Engineering Engine
           │
           ▼
        Workflow
           │
           ▼
          Task
           │
           ▼
    Execution State
           │
           ▼
       Permission
           │
           ▼
          Tool
           │
           ▼
        Result
           │
           ▼
       Validation
           │
           ├───────────────┐
           ▼               ▼
       COMPLETE          FAILURE
                           │
                           ▼
                       RECOVERY

The Permission Engine defined by CC-PRD-006 remains the authorization
boundary.

Execution state SHALL NOT grant permission.

-------------------------------------------------------------------------------

# 4. Scope

## 4.1 In Scope

Implement:

- Execution State model.
- Task lifecycle.
- Execution lifecycle.
- State transitions.
- Result classification.
- Failure classification.
- Retry policy.
- Recovery policy.
- Cancellation.
- Pause.
- Resume.
- Completion verification.
- Execution history.
- Recovery boundaries.
- State consistency.
- Structured execution errors.
- Execution status reporting.

-------------------------------------------------------------------------------

## 4.2 Out of Scope

Do NOT implement:

- model inference,
- model provider selection,
- Tool implementation,
- Skill implementation,
- Permission policy,
- authentication,
- credential storage,
- distributed orchestration,
- autonomous policy generation,
- project-specific engineering logic,
- IDE integration.

-------------------------------------------------------------------------------

# 5. Design Principles

ClaireCoder SHALL remain:

- model independent,
- provider independent,
- workflow driven,
- repository aware,
- modular,
- extensible,
- developer controlled.

The Execution State System SHALL additionally be:

- deterministic,
- explicit,
- recoverable,
- observable,
- interruptible,
- state-consistent,
- failure-safe.

The architecture SHALL remain architecture-first rather than implementation-
first, consistent with the ClaireCoder foundation.

-------------------------------------------------------------------------------

# 6. Execution Model

ClaireCoder SHALL distinguish between:

    PLAN
    TASK
    EXECUTION
    RESULT
    VALIDATION
    COMPLETION

A plan is not an execution.

A requested Tool call is not a successful execution.

A Tool response is not automatically a successful Task.

A Task SHALL only become COMPLETE after the required completion conditions
have been satisfied.

-------------------------------------------------------------------------------

# 7. Task

A Task represents one bounded engineering operation.

Conceptual model:

    Task
      │
      ├── taskId
      ├── description
      ├── workflowId
      ├── status
      ├── attempts
      ├── createdAt
      └── updatedAt

The Task model SHALL remain independent of the underlying model.

-------------------------------------------------------------------------------

# 8. Execution

An Execution represents one attempt to perform a Task.

A Task MAY have multiple Executions.

Example:

    Task
      │
      ├── Execution #1 → FAILED
      │
      ├── Execution #2 → FAILED
      │
      └── Execution #3 → SUCCESS

The Task SHALL retain its identity across retries.

Each Execution SHALL have its own execution identity.

-------------------------------------------------------------------------------

# 9. Task States

V1 SHALL implement ONLY:

    PENDING
    READY
    RUNNING
    PAUSED
    SUCCEEDED
    FAILED
    CANCELLED
    BLOCKED

These states SHALL describe Task lifecycle.

No additional Task states SHALL be introduced without architectural review.

-------------------------------------------------------------------------------

# 10. State Definitions

## PENDING

The Task exists but is not yet ready for execution.

-------------------------------------------------------------------------------

## READY

All known prerequisites have been satisfied and execution may begin.

-------------------------------------------------------------------------------

## RUNNING

The Task is actively being executed.

-------------------------------------------------------------------------------

## PAUSED

Execution has intentionally stopped but may resume.

-------------------------------------------------------------------------------

## SUCCEEDED

The Task completed successfully and its completion requirements were satisfied.

-------------------------------------------------------------------------------

## FAILED

The Task could not be completed successfully.

-------------------------------------------------------------------------------

## CANCELLED

Execution was explicitly cancelled.

-------------------------------------------------------------------------------

## BLOCKED

Execution cannot continue because an external dependency, permission,
resource, or prerequisite is preventing progress.

-------------------------------------------------------------------------------

# 11. State Transition Rules

Valid transitions SHALL include:

    PENDING
       ↓
     READY
       ↓
    RUNNING
       ↓
    SUCCEEDED

and:

    RUNNING
       ↓
     FAILED
       ↓
    READY
       ↓
    RUNNING

and:

    RUNNING
       ↓
    PAUSED
       ↓
    RUNNING

and:

    RUNNING
       ↓
   CANCELLED

and:

    READY
       ↓
    BLOCKED

Invalid transitions SHALL be rejected.

-------------------------------------------------------------------------------

# 12. Terminal States

The following SHALL be terminal for a particular Task execution:

    SUCCEEDED
    FAILED
    CANCELLED

A FAILED Task MAY create a new Execution attempt if retry/recovery policy
allows it.

A terminal state SHALL not be mutated into another state retroactively.

-------------------------------------------------------------------------------

# 13. Execution Attempt

Each attempt SHALL have:

    executionId
    taskId
    attemptNumber
    startedAt
    completedAt
    status
    result
    error

Attempt numbers SHALL increase monotonically.

-------------------------------------------------------------------------------

# 14. Execution Result

A Tool result SHALL be classified.

Possible result categories SHALL include:

    SUCCESS
    FAILURE
    CANCELLED
    TIMEOUT
    BLOCKED
    UNKNOWN

The final taxonomy MAY be extended later.

-------------------------------------------------------------------------------

# 15. Completion Verification

ClaireCoder SHALL not assume success solely because:

- a model said it succeeded,
- a Tool returned without throwing,
- a command produced output,
- a file was modified.

Where the Task has explicit completion criteria, those criteria SHALL be
evaluated.

Conceptually:

    Tool Result
        ↓
    Completion Criteria
        ↓
    Verification
        ↓
    SUCCESS / FAILURE

-------------------------------------------------------------------------------

# 16. Verification

Verification MAY include:

- expected file existence,
- expected file content,
- test execution,
- build success,
- command exit status,
- repository state,
- declared Task conditions.

The exact verification mechanism SHALL be provided by the relevant Workflow
or Tool architecture.

CC-PRD-007 SHALL define the execution lifecycle, not project-specific
verification logic.

-------------------------------------------------------------------------------

# 17. Failure Classification

Failures SHOULD be categorized.

V1 SHALL recognize at least:

    TOOL_FAILURE
    PERMISSION_FAILURE
    VALIDATION_FAILURE
    TIMEOUT
    RESOURCE_FAILURE
    DEPENDENCY_FAILURE
    USER_CANCELLATION
    UNKNOWN_FAILURE

The system SHALL preserve the original failure information where possible.

-------------------------------------------------------------------------------

# 18. Permission Failure

A permission failure SHALL remain distinct from a Tool failure.

Example:

    Tool requested WRITE
          ↓
    Permission Engine
          ↓
        DENY
          ↓
    Permission Failure

The Execution Engine SHALL not retry a denied operation automatically.

Permission handling remains governed by CC-PRD-006.

-------------------------------------------------------------------------------

# 19. Tool Failure

A Tool failure occurs when an authorized Tool operation fails during execution.

Example:

    Shell Tool
        ↓
    npm test
        ↓
    exit code 1
        ↓
    TOOL_FAILURE

The failure MAY be eligible for recovery.

-------------------------------------------------------------------------------

# 20. Validation Failure

A Validation Failure occurs when execution technically completes but the
required result does not satisfy the Task requirements.

Example:

    Build command exits 0
           ↓
    Expected file missing
           ↓
    VALIDATION_FAILURE

This SHALL not automatically be classified as Tool failure.

-------------------------------------------------------------------------------

# 21. Timeout

An execution MAY have a defined timeout.

If the timeout expires:

    RUNNING
       ↓
    TIMEOUT
       ↓
    FAILURE

The system SHALL prevent an expired execution from being incorrectly marked
successful by a late result.

-------------------------------------------------------------------------------

# 22. Retry Policy

Retries SHALL be explicit.

A failure SHALL NOT automatically cause infinite retries.

The retry system SHOULD consider:

- failure type,
- attempt count,
- Task policy,
- Workflow policy,
- permission state,
- developer configuration.

-------------------------------------------------------------------------------

# 23. Retry Limit

Every retryable Task SHALL have a bounded retry policy.

V1 SHOULD provide a finite default.

The exact default count SHALL remain configurable.

Unlimited automatic retry SHALL NOT be the default.

-------------------------------------------------------------------------------

# 24. Retry Safety

The system SHALL distinguish retryable failures from non-retryable failures.

Examples of generally non-retryable conditions:

- explicit permission denial,
- user cancellation,
- invalid Task definition,
- permanently missing prerequisite.

Examples that MAY be retryable:

- transient Tool failure,
- temporary resource failure,
- transient network failure,
- recoverable validation failure.

The final classification MAY depend on Tool metadata.

-------------------------------------------------------------------------------

# 25. Recovery

Recovery SHALL be a controlled process.

Conceptually:

    FAILURE
       ↓
    ANALYZE
       ↓
    RECOVERY DECISION
       │
       ├── RETRY
       ├── PAUSE
       ├── BLOCK
       └── ABORT

The model MAY recommend recovery, but the execution system SHALL enforce
recovery boundaries.

-------------------------------------------------------------------------------

# 26. Recovery SHALL Not Bypass Permission

Recovery SHALL not automatically broaden permissions.

Example:

    WRITE denied
       ↓
    Recovery
       ↓
    Request WRITE again

This SHALL result in normal Permission Engine evaluation.

Recovery SHALL not reinterpret DENY as ALLOW.

-------------------------------------------------------------------------------

# 27. Cancellation

The developer SHALL be able to cancel active execution.

Cancellation SHALL result in:

    RUNNING
       ↓
    CANCELLED

Where Tool cancellation is supported, the Tool SHALL receive a cancellation
signal.

Where immediate cancellation is impossible, the Execution Engine SHALL record
the cancellation request and prevent subsequent state from being incorrectly
reported as successful.

-------------------------------------------------------------------------------

# 28. Pause

Execution MAY be paused when supported.

Pause SHALL result in:

    RUNNING
       ↓
    PAUSED

A paused Task SHALL retain sufficient state to resume without creating a
duplicate Task identity.

-------------------------------------------------------------------------------

# 29. Resume

A paused Task MAY resume:

    PAUSED
       ↓
    RUNNING

The system SHALL verify that the execution context remains valid before
resuming.

If the context is no longer valid, the Task MAY become BLOCKED or require a
new Execution attempt.

-------------------------------------------------------------------------------

# 30. Blocked State

A Task SHALL enter BLOCKED when execution cannot safely continue.

Examples:

- missing dependency,
- unavailable Tool,
- unresolved external condition,
- unavailable permission,
- required developer decision.

BLOCKED SHALL not mean FAILED.

The distinction SHALL remain explicit.

-------------------------------------------------------------------------------

# 31. Developer Intervention

The system SHALL support developer intervention when required.

Examples:

    Permission required
    ↓
    BLOCKED
    ↓
    Developer decision
    ↓
    READY

or:

    Failure
    ↓
    Recovery decision
    ↓
    Developer chooses retry
    ↓
    READY

-------------------------------------------------------------------------------

# 32. Execution History

The system SHOULD preserve execution history for the current engineering
Session.

History SHOULD allow ClaireCoder to distinguish:

- what was attempted,
- what succeeded,
- what failed,
- what was cancelled,
- what was retried.

The history SHALL not expose secrets unnecessarily.

-------------------------------------------------------------------------------

# 33. State Consistency

Only the Execution State System SHALL mutate execution state.

Models, Tools, and Skills SHALL report events or results.

They SHALL NOT directly mutate Task lifecycle state.

-------------------------------------------------------------------------------

# 34. Event Model

The system SHOULD represent important execution transitions as events.

Examples:

    TASK_CREATED
    TASK_READY
    EXECUTION_STARTED
    EXECUTION_COMPLETED
    EXECUTION_FAILED
    TASK_PAUSED
    TASK_RESUMED
    TASK_CANCELLED
    TASK_BLOCKED
    TASK_SUCCEEDED

The event model SHALL remain extensible.

-------------------------------------------------------------------------------

# 35. Idempotency

Execution state operations SHOULD be safe against duplicate notifications.

For example, receiving the same completion event twice SHALL not create two
successful completions.

The system SHALL use execution identity to distinguish attempts.

-------------------------------------------------------------------------------

# 36. Late Results

A result arriving after cancellation, timeout, or terminal failure SHALL not
automatically change the Task back to RUNNING or SUCCEEDED.

The result SHALL be associated with its original Execution.

-------------------------------------------------------------------------------

# 37. Concurrent Execution

V1 SHALL avoid uncontrolled concurrent mutation of the same Task.

A Task SHALL have at most one active Execution unless a future architecture
explicitly introduces parallel execution.

Parallel Tasks MAY execute independently when the Workflow permits it.

-------------------------------------------------------------------------------

# 38. Dependency Handling

A Task MAY depend on another Task.

Example:

    TASK A
      ↓
    TASK B
      ↓
    TASK C

Task B SHALL not become READY until required dependencies have reached the
required state.

Dependency graphs SHALL remain acyclic in V1 unless explicitly supported by
future architecture.

-------------------------------------------------------------------------------

# 39. Workflow Integration

Workflows SHALL create and coordinate Tasks.

The Execution State System SHALL track Task execution.

The Workflow SHALL determine engineering sequencing.

The Execution State System SHALL determine lifecycle validity.

Neither component SHALL replace the other.

This preserves the project's separation between workflows and the Engineering
Engine.

-------------------------------------------------------------------------------

# 40. Skill Integration

Skills MAY recommend:

- Task creation,
- Task decomposition,
- verification,
- recovery.

Skills SHALL not directly mutate execution state.

-------------------------------------------------------------------------------

# 41. Tool Integration

Tools SHALL report:

- execution start,
- result,
- failure,
- cancellation where supported.

Tools SHALL not determine whether a Task is ultimately complete.

The Execution Engine SHALL make the final lifecycle determination.

-------------------------------------------------------------------------------

# 42. Model Integration

The model MAY:

- propose Tasks,
- propose recovery,
- interpret Tool results,
- propose next actions.

The model SHALL NOT:

- mark a Task successful without verification,
- bypass state transitions,
- revive terminal executions,
- bypass cancellation,
- bypass permission.

-------------------------------------------------------------------------------

# 43. Permission Integration

The execution pipeline SHALL be:

    Task
      ↓
    Permission Check
      ↓
    ALLOW
      ↓
    Tool Execution
      ↓
    Result
      ↓
    Verification
      ↓
    State Transition

If Permission returns DENY:

    Task
      ↓
    Permission Check
      ↓
    DENY
      ↓
    BLOCKED / DENIED RESULT

The Permission Engine remains authoritative.

-------------------------------------------------------------------------------

# 44. Error Model

V1 SHOULD provide structured errors such as:

    ExecutionError
    InvalidStateTransitionError
    TaskNotFoundError
    ExecutionNotFoundError
    ExecutionTimeoutError
    ExecutionCancelledError
    DependencyBlockedError
    RecoveryError
    VerificationError

The final implementation MAY refine the taxonomy.

-------------------------------------------------------------------------------

# 45. Observability

The system SHOULD expose current execution state to the interaction layer.

The developer SHOULD be able to see:

    Task
    Status
    Current Execution
    Attempt
    Current Operation
    Error
    Recovery State

Sensitive Tool output SHALL remain protected.

-------------------------------------------------------------------------------

# 46. Autonomy Integration

Autonomy level SHALL influence how much recovery can occur without
intervention.

Conceptually:

    SUPERVISED
        ↓
    Failure
        ↓
    ASK DEVELOPER

while:

    ASSISTED
        ↓
    Recoverable Failure
        ↓
    Apply permitted recovery

and:

    AUTONOMOUS
        ↓
    Recoverable Failure
        ↓
    Apply authorized recovery policy

However, autonomy SHALL not override permission restrictions or explicit
developer constraints.

This follows the foundational requirement that ClaireCoder preserve developer
control while enabling progressively higher autonomy.

-------------------------------------------------------------------------------

# 47. Recovery Boundaries

Autonomous recovery SHALL be bounded by:

- Task scope,
- Workflow scope,
- Permission scope,
- retry limit,
- resource scope,
- autonomy level,
- developer policy.

ClaireCoder SHALL not transform a failed Task into unrestricted exploratory
execution.

-------------------------------------------------------------------------------

# 48. Completion

A Task SHALL reach SUCCEEDED only when:

1. execution completed,
2. no blocking error remains,
3. required verification succeeded,
4. the resulting state satisfies Task completion criteria.

The model's statement:

    "Done."

SHALL NOT itself satisfy completion.

-------------------------------------------------------------------------------

# 49. Failure

A Task SHALL reach FAILED when:

- execution cannot complete,
- recovery is exhausted,
- verification fails without an allowed recovery path,
- an unrecoverable error occurs.

The failure SHALL preserve the reason where available.

-------------------------------------------------------------------------------

# 50. Cancellation

A cancelled Task SHALL remain distinguishable from failure.

The system SHALL record:

- cancellation time,
- cancellation source,
- execution identity.

-------------------------------------------------------------------------------

# 51. Persistence

V1 SHALL define the execution-state model independently of persistence.

The system MAY initially maintain state in memory.

Persistence architecture SHALL be introduced separately if required.

This avoids prematurely coupling ClaireCoder to a particular storage system and
preserves the architecture-first principle.

-------------------------------------------------------------------------------

# 52. Acceptance Criteria

CC-PRD-007 SHALL be considered complete when:

### AC-001 — Task Model

Tasks can be represented independently of models.

### AC-002 — Execution Model

Each Task can have distinct Execution attempts.

### AC-003 — Explicit States

PENDING, READY, RUNNING, PAUSED, SUCCEEDED, FAILED, CANCELLED, and BLOCKED
are represented.

### AC-004 — Valid Transitions

Invalid state transitions are rejected.

### AC-005 — Completion Verification

A Task cannot become SUCCEEDED solely because a model claims success.

### AC-006 — Failure Classification

Major failure categories can be distinguished.

### AC-007 — Retry

Retryable failures can be retried within a bounded policy.

### AC-008 — No Infinite Retry

Unlimited automatic retries are prevented by default.

### AC-009 — Recovery

Recoverable failures can enter a controlled recovery flow.

### AC-010 — Permission Boundary

Recovery cannot bypass Permission Engine decisions.

### AC-011 — Cancellation

Active execution can be cancelled.

### AC-012 — Pause

Supported executions can be paused.

### AC-013 — Resume

Paused executions can resume safely.

### AC-014 — Blocked

Blocked Tasks remain distinct from failed Tasks.

### AC-015 — Execution History

Execution attempts can be distinguished and tracked.

### AC-016 — Late Results

Late results cannot incorrectly revive terminal executions.

### AC-017 — Idempotency

Duplicate execution events do not corrupt state.

### AC-018 — Workflow Integration

Workflows can coordinate Tasks without directly mutating execution state.

### AC-019 — Tool Integration

Tools can report execution results without becoming lifecycle authorities.

### AC-020 — Model Independence

The execution state system does not depend on a specific model.

### AC-021 — Provider Independence

The execution state system does not depend on a specific provider.

### AC-022 — Autonomy

Recovery behavior can respect the configured autonomy level.

### AC-023 — Developer Control

Developer intervention remains possible during execution.

### AC-024 — Failure Safety

Unknown or inconsistent state does not result in false success.

-------------------------------------------------------------------------------

# 53. Non-Functional Requirements

## NFR-001 — Determinism

Equivalent state transitions SHALL produce equivalent results.

## NFR-002 — Consistency

A Task SHALL never simultaneously occupy incompatible states.

## NFR-003 — Traceability

Every Execution SHALL be associated with its Task.

## NFR-004 — Recoverability

Recoverable failures SHALL preserve enough state to support retry.

## NFR-005 — Isolation

Execution state SHALL remain independent of model implementation.

## NFR-006 — Extensibility

Future execution strategies SHALL be addable without replacing the Task
model.

## NFR-007 — Safety

The system SHALL favor explicit failure over false completion.

-------------------------------------------------------------------------------

# 54. Deliverables

Implementation SHALL produce:

1. Task model.
2. Execution model.
3. Task state machine.
4. Execution state machine.
5. State transition validator.
6. Execution result model.
7. Failure classification.
8. Retry policy.
9. Recovery policy.
10. Cancellation mechanism.
11. Pause/resume mechanism.
12. Dependency handling.
13. Completion verification boundary.
14. Execution history.
15. Execution events.
16. Structured execution errors.
17. Permission integration.
18. Workflow integration.
19. Tool integration.
20. Autonomy integration.
21. State consistency tests.
22. Recovery tests.

-------------------------------------------------------------------------------

# 55. Verification Strategy

## Unit Tests

Test:

- Task creation,
- Execution creation,
- valid transitions,
- invalid transitions,
- terminal states,
- cancellation,
- pause/resume.

## Failure Tests

Test:

- Tool failure,
- Permission failure,
- validation failure,
- timeout,
- dependency failure,
- cancellation.

## Recovery Tests

Test:

    FAILURE
       ↓
    RETRY

and:

    FAILURE
       ↓
    BLOCK

and:

    FAILURE
       ↓
    ABORT

Verify retry limits.

## Completion Tests

Verify that:

- model claims cannot create success,
- Tool completion does not automatically create success,
- verification determines completion.

## Concurrency Tests

Verify:

- duplicate completion,
- late results,
- duplicate events,
- simultaneous cancellation.

## Permission Tests

Verify:

- denied operations cannot execute,
- recovery cannot bypass permission,
- escalation returns to Permission Engine.

## Autonomy Tests

Verify that:

- supervised mode requests intervention,
- assisted mode applies permitted recovery,
- autonomous mode remains bounded by authorization.

-------------------------------------------------------------------------------

# 56. Forbidden

Do NOT:

- allow models to mutate Task state directly,
- allow Tools to mark Tasks successful without lifecycle verification,
- allow Skills to bypass the state machine,
- allow infinite retries,
- allow recovery to bypass permissions,
- allow late results to revive terminal executions,
- treat BLOCKED as FAILED,
- treat CANCELLED as FAILED,
- treat model output as proof of completion,
- introduce distributed orchestration,
- introduce persistent storage requirements,
- couple execution state to one model provider,
- couple execution state to one Tool implementation,
- implement project-specific engineering logic.

-------------------------------------------------------------------------------

# 57. Relationship With Previous PRDs

## CC-PRD-001

Defines the Engineering Engine.

CC-PRD-007 provides the execution lifecycle used by that engine.

## CC-PRD-002

Defines model/provider interaction.

CC-PRD-007 remains independent of the model gateway.

## CC-PRD-003

Defines Tools and Skills.

CC-PRD-007 tracks their execution without owning their implementation.

## CC-PRD-004

Defines Workflow and Session behavior.

CC-PRD-007 executes Tasks within those workflows.

## CC-PRD-005

Defines developer interaction.

CC-PRD-007 exposes execution state and intervention requirements to it.

## CC-PRD-006

Defines Permission, Autonomy & Security.

CC-PRD-007 SHALL consume its authorization decisions and SHALL never bypass
them.

-------------------------------------------------------------------------------

# 58. Architectural Summary

The resulting ClaireCoder execution architecture SHALL be:

    USER
      │
      ▼
    ENGINEERING OBJECTIVE
      │
      ▼
    ENGINEERING ENGINE
      │
      ▼
    WORKFLOW
      │
      ▼
    TASK
      │
      ▼
    EXECUTION STATE
      │
      ▼
    PERMISSION ENGINE
      │
      ├──── DENY ─────→ BLOCKED
      │
      ▼
    TOOL
      │
      ▼
    RESULT
      │
      ▼
    VERIFICATION
      │
      ├──── SUCCESS ──→ SUCCEEDED
      │
      └──── FAILURE ──→ RECOVERY
                              │
                     ┌────────┼────────┐
                     ▼        ▼        ▼
                   RETRY    PAUSE     ABORT

This creates a controlled execution lifecycle without coupling ClaireCoder's
engineering behavior to any particular model or provider.

-------------------------------------------------------------------------------

# 59. AI Instructions

When implementing CC-PRD-007:

1. Treat Execution State as an authoritative lifecycle boundary.
2. Keep Task identity separate from Execution identity.
3. Implement explicit state transitions.
4. Reject invalid transitions.
5. Never treat model output as proof of completion.
6. Require completion verification.
7. Keep FAILED, CANCELLED, and BLOCKED distinct.
8. Keep Permission Failure distinct from Tool Failure.
9. Bound retries.
10. Never implement infinite automatic retries.
11. Keep recovery within the existing permission scope.
12. Never allow recovery to grant itself permission.
13. Preserve developer cancellation.
14. Preserve pause/resume semantics.
15. Protect against late results.
16. Protect against duplicate events.
17. Keep execution state independent of models.
18. Keep execution state independent of providers.
19. Keep execution state independent of Tool implementations.
20. Preserve Workflow/Task separation.
21. Preserve Skill/Tool separation.
22. Preserve developer control.
23. Support progressively higher autonomy without removing security boundaries.
24. Fail safely when execution state becomes uncertain.
25. Do not introduce persistent storage unless explicitly required.
26. Do not introduce distributed execution infrastructure.
27. Keep the implementation modular and architecture-first.
28. Preserve ClaireCoder's long-term provider and model independence.

###############################################################################

END OF CC-PRD-007

###############################################################################