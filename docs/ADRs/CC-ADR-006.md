###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-006
# Title           : Permission, Autonomy & Security Architecture
# Version         : 1.0.0
# Status          : Accepted
#
###############################################################################

# 1. Decision Summary

ClaireCoder SHALL use a centralized Permission Engine as the authoritative
security boundary for all executable capabilities.

The Permission Engine SHALL govern:

- Tools,
- terminal execution,
- filesystem operations,
- Git operations,
- network access,
- MCP capabilities,
- third-party extensions,
- Skills that request executable capabilities,
- autonomous execution.

The fundamental permission states SHALL be:

ALLOW
ASK
DENY

Permissions SHALL support appropriate scopes without making the policy system
unnecessarily complex.

ClaireCoder SHALL distinguish:

- Permission,
- Autonomy,
- Mode,
- Trust,
- Capability.

Autonomy SHALL control how independently ClaireCoder can execute within the
permissions already granted.

Autonomy SHALL NOT silently override security boundaries.

YOLO-style operation MAY be supported as an explicit advanced option.

The user SHALL always be able to understand when ClaireCoder is operating
with elevated autonomy.

-------------------------------------------------------------------------------

# 2. Context

CC-RES-008 established that ClaireCoder will operate with significant
execution capabilities.

These may include:

- filesystem access,
- terminal execution,
- Git,
- network access,
- browser capabilities,
- MCP,
- third-party Skills,
- external Tools.

These capabilities are necessary for a useful coding agent but introduce
security risks.

The architecture therefore requires a centralized system capable of deciding
whether an operation may execute.

The previous ADRs establish that:

- Tools are executable capabilities.
- Skills provide expertise.
- Workflows coordinate engineering.
- Modes influence behavior.
- Commands provide explicit user controls.
- Models may be local or remote.

None of these systems SHALL independently become the security authority.

-------------------------------------------------------------------------------

# 3. Problem

A coding agent can potentially perform destructive or sensitive operations.

Examples include:

- deleting files,
- modifying repository history,
- executing arbitrary commands,
- installing software,
- accessing external services,
- accessing credentials,
- modifying files outside the workspace.

A simple confirmation dialog in the UI is insufficient because execution may
originate from:

- a Command,
- a Skill,
- a Workflow,
- an MCP Tool,
- a subagent,
- an autonomous planning loop.

Therefore the security boundary must exist below these systems.

The architecture SHALL ensure that every executable operation reaches the same
Permission Engine before execution.

-------------------------------------------------------------------------------

# 4. Decision

ClaireCoder SHALL use the following conceptual security architecture:

                         USER / POLICY
                              │
                              ▼
                      PERMISSION ENGINE
                              │
                    ┌─────────┼─────────┐
                    │         │         │
                    ▼         ▼         ▼
                  ALLOW      ASK       DENY
                    │         │
                    │         ▼
                    │     USER DECISION
                    │         │
                    │    ┌────┴────┐
                    │    ▼         ▼
                    │  ALLOW      DENY
                    │
                    └──────┬──────┘
                           ▼
                     TOOL EXECUTION

All executable paths SHALL pass through this boundary.

Conceptually:

Command
   │
Skill
   │
Workflow
   │
Subagent
   │
MCP
   │
Agent
   │
   ▼
Permission Engine
   │
   ▼
Tool / Capability
   │
   ▼
Execution

No higher-level component SHALL directly authorize execution.

-------------------------------------------------------------------------------

# 5. Permission States

The fundamental permission states SHALL be:

ALLOW

The requested operation may execute without user interaction.

ASK

The operation requires explicit user approval.

DENY

The operation must not execute.

The system SHALL avoid introducing unnecessary permission states unless
required by a future architectural decision.

-------------------------------------------------------------------------------

# 6. Permission Evaluation

A permission request SHALL conceptually contain:

- requester,
- Tool,
- operation,
- target,
- workspace,
- requested capability,
- risk information,
- current Mode,
- current autonomy level,
- applicable policy.

The Permission Engine SHALL evaluate the request against the active policy.

Conceptually:

Permission Request
        │
        ▼
Policy Evaluation
        │
        ├── DENY
        │
        ├── ASK
        │
        └── ALLOW

The exact policy implementation SHALL be determined during PRD and
implementation design.

-------------------------------------------------------------------------------

# 7. Permission Scope

ClaireCoder SHALL support scoped authorization.

Potential scopes include:

- one operation,
- one Tool,
- one command pattern,
- one path,
- current task,
- current session,
- current project,
- global configuration.

The final scope hierarchy SHALL remain intentionally small.

The system SHALL avoid requiring users to understand an unnecessarily
complex policy language.

-------------------------------------------------------------------------------

# 8. Allow Once

The user SHOULD be able to approve a single requested operation.

Example:

Terminal requests:

    npm install

User:

    Allow once.

The permission SHALL apply only to the current matching operation.

-------------------------------------------------------------------------------

# 9. Allow for Session

The user MAY approve an operation class for the current Engineering Session.

Example:

    Allow terminal test commands for this session.

The permission SHALL expire when the session policy expires.

-------------------------------------------------------------------------------

# 10. Allow for Project

The user MAY choose to persist a permission for the current project.

Example:

    Allow pytest commands in this project.

Project-level permissions SHALL remain scoped to the intended project.

-------------------------------------------------------------------------------

# 11. Global Permissions

Global permissions MAY be supported for trusted and frequently used
operations.

Global authorization SHOULD be used carefully.

High-risk capabilities SHOULD not become globally authorized without explicit
user intent.

-------------------------------------------------------------------------------

# 12. Permission Precedence

ClaireCoder SHALL use deterministic permission precedence.

The exact implementation SHALL be finalized during implementation design.

The conceptual principle SHALL be:

Explicit restrictive policy
        ↓
Explicit authorization
        ↓
Scoped policy
        ↓
Default policy

A more restrictive explicit rule SHALL not be silently overridden by a
broader authorization.

The final rule-resolution algorithm SHALL be documented before implementation.

-------------------------------------------------------------------------------

# 13. Workspace Boundary

ClaireCoder SHALL establish a workspace boundary.

By default, executable file operations SHOULD remain within the selected
workspace.

Operations outside the workspace SHOULD require additional authorization.

The workspace boundary SHALL apply regardless of which Skill, Mode, model, or
Workflow requested the operation.

-------------------------------------------------------------------------------

# 14. Filesystem Permissions

Filesystem operations SHALL be permission-aware.

Potential categories include:

READ

- read file,
- list directory,
- inspect metadata.

WRITE

- create,
- modify,
- rename,
- move.

DESTRUCTIVE

- delete,
- recursive deletion,
- destructive overwrite.

The Permission Engine MAY use different default policies for these categories.

-------------------------------------------------------------------------------

# 15. Terminal Permissions

Terminal execution SHALL be treated as a high-capability Tool.

The Terminal Tool SHOULD provide sufficient metadata for the Permission
Engine to evaluate:

- executable,
- arguments,
- working directory,
- environment requirements,
- network requirements.

The system SHOULD distinguish between routine development commands and
potentially destructive commands.

-------------------------------------------------------------------------------

# 16. Command Risk

Commands MAY be classified conceptually as:

LOW RISK

Examples:

- tests,
- formatters,
- linters,
- Git status,
- Git diff.

MODERATE RISK

Examples:

- package installation,
- builds,
- generated code,
- dependency updates.

HIGH RISK

Examples:

- destructive file operations,
- destructive Git operations,
- system modification,
- arbitrary scripts.

CRITICAL

Examples:

- credential manipulation,
- unrestricted external system control,
- destructive operations outside the workspace.

The exact classification SHALL remain configurable.

-------------------------------------------------------------------------------

# 17. Git Permissions

Git SHALL have permission-aware operations.

Read-oriented operations MAY include:

- status,
- diff,
- log,
- branch inspection.

Modification operations MAY include:

- add,
- commit,
- restore,
- checkout,
- merge,
- rebase.

Potentially destructive operations include:

- reset,
- clean,
- force push,
- branch deletion.

The Permission Engine SHALL be able to distinguish these operations.

-------------------------------------------------------------------------------

# 18. Network Permissions

Network access SHALL be treated independently from local Tool permissions.

Potential network operations include:

- web search,
- web retrieval,
- package downloads,
- API requests,
- remote Git operations,
- browser requests,
- MCP communication.

A Tool requiring network access SHOULD declare that requirement.

-------------------------------------------------------------------------------

# 19. MCP Permissions

MCP capabilities SHALL use the same Permission Engine.

Installing or enabling an MCP server SHALL NOT automatically grant unlimited
execution authority.

MCP permissions MAY be scoped by:

- server,
- Tool,
- operation,
- resource,
- project.

The final MCP-specific policy model SHALL be determined during implementation.

-------------------------------------------------------------------------------

# 20. Skill Permissions

Skills SHALL not automatically receive privileged execution authority.

A Skill MAY:

- recommend a Tool,
- request a Tool,
- provide methodology,
- activate supporting context.

The requested Tool operation SHALL still pass through the Permission Engine.

Third-party Skills SHALL use the same security boundary as built-in Skills.

-------------------------------------------------------------------------------

# 21. Extension Trust

ClaireCoder SHALL distinguish extension trust from extension availability.

Conceptual trust states MAY include:

- Built-in,
- Trusted,
- Community,
- Unverified,
- Blocked.

Trust SHALL not automatically mean unlimited permissions.

A trusted Skill may still be restricted from:

- credential access,
- system modification,
- external network access,
- destructive operations.

-------------------------------------------------------------------------------

# 22. Repository Trust

Repository content SHALL be treated as potentially untrusted input.

Repository files may contain:

- malicious instructions,
- prompt injection,
- unsafe scripts,
- misleading configuration.

Repository instructions SHALL not automatically override:

- system policy,
- user permissions,
- security policy.

-------------------------------------------------------------------------------

# 23. Prompt Injection

ClaireCoder SHALL treat external content as data unless it has an explicitly
authorized instruction role.

Potential injection sources include:

- source code,
- documentation,
- README files,
- issues,
- web pages,
- Tool output,
- MCP responses,
- third-party Skills.

The agent SHALL preserve instruction authority boundaries.

External content SHALL not be able to silently change Permission Engine
policy.

-------------------------------------------------------------------------------

# 24. Secrets

Secrets SHALL receive special treatment.

Potential secrets include:

- API keys,
- access tokens,
- passwords,
- SSH credentials,
- cloud credentials,
- Git credentials,
- MCP credentials.

Secrets SHOULD remain outside normal model context whenever possible.

Tools SHOULD access credentials through secure mechanisms rather than
requiring raw secrets to be supplied to the model.

-------------------------------------------------------------------------------

# 25. Secret Redaction

ClaireCoder SHOULD support redaction of sensitive information from:

- Tool output,
- terminal output,
- logs,
- session records,
- model context.

The system SHOULD avoid storing raw credentials in Engineering Sessions.

-------------------------------------------------------------------------------

# 26. Environment Variables

Environment variables MAY contain secrets.

Terminal execution SHOULD therefore consider:

- inherited environment,
- protected variables,
- secret redaction,
- environment allowlists.

The exact environment policy SHALL be defined during implementation.

-------------------------------------------------------------------------------

# 27. Autonomy

Autonomy SHALL be separate from Permission.

Permission answers:

    "Is this operation allowed?"

Autonomy answers:

    "How much independent execution is ClaireCoder allowed to perform
     within the granted boundaries?"

This distinction SHALL remain fundamental.

-------------------------------------------------------------------------------

# 28. Autonomy Levels

ClaireCoder SHOULD support conceptual autonomy levels.

ASSISTED

The agent requests approval frequently.

BALANCED

Routine operations may proceed automatically while higher-risk operations
require approval.

AUTONOMOUS

The agent may execute most operations within configured boundaries.

YOLO

The user explicitly disables normal approval prompts within the selected
authorization scope.

The final names MAY be changed during PRD.

-------------------------------------------------------------------------------

# 29. Autonomy Boundaries

Increasing autonomy SHALL NOT automatically grant access to:

- credentials,
- files outside the workspace,
- restricted system operations,
- blocked Tools,
- denied extensions.

Autonomy operates within the Permission Engine.

Conceptually:

Permissions
     │
     ▼
Security Boundary
     │
     ▼
Autonomy Level
     │
     ▼
Execution Behavior

-------------------------------------------------------------------------------

# 30. YOLO Mode

ClaireCoder MAY provide a YOLO-style mode.

YOLO SHALL be:

- explicit,
- user-controlled,
- visible,
- reversible.

The interface SHOULD clearly indicate:

- YOLO active,
- workspace,
- model,
- Mode,
- relevant permission scope.

The system SHALL not silently enter YOLO behavior.

-------------------------------------------------------------------------------

# 31. Mode Interaction

Modes MAY provide permission defaults.

Examples:

PLAN

Prefer read-only.

REVIEW

Prefer read-only.

BUILD

Normal development permissions.

DEBUG

Diagnostic execution plus targeted modification.

However, Modes SHALL NOT become the final permission authority.

The Permission Engine remains authoritative.

-------------------------------------------------------------------------------

# 32. Model Independence

Permissions SHALL remain independent of the selected model.

The same permission policy SHALL apply whether ClaireCoder uses:

- a hosted model,
- a local model,
- a router,
- a custom endpoint.

The model SHALL never receive authority merely because it is considered
"trusted."

-------------------------------------------------------------------------------

# 33. Tool Independence

Permissions SHALL be evaluated independently of Tool implementation.

A Tool SHALL declare its requirements.

The Permission Engine SHALL make the authorization decision.

This prevents individual Tools from implementing incompatible security
behavior.

-------------------------------------------------------------------------------

# 34. Subagent Permissions

Subagents SHALL operate within the parent's authorized boundaries unless an
explicit policy grants additional capability.

A subagent SHALL not escalate privileges merely because it is a separate
model or execution process.

The parent Engineering Engine SHALL remain responsible for orchestration.

-------------------------------------------------------------------------------

# 35. Permission Inheritance

Permission inheritance SHALL be explicit.

Potential inheritance hierarchy:

Global Policy
     ↓
Project Policy
     ↓
Session Policy
     ↓
Task Policy
     ↓
Operation Request

A child operation SHALL not silently escalate beyond its parent authorization.

-------------------------------------------------------------------------------

# 36. Approval Request

When a permission state is ASK, the Interaction Layer SHOULD present:

- requested Tool,
- requested operation,
- target,
- workspace,
- reason,
- risk,
- permission scope.

Example:

    Tool: Terminal

    Action: Install project dependency

    Command: npm install package-name

    Workspace: project/

    Risk: Downloads and modifies project dependencies.

    [Allow Once]
    [Allow Session]
    [Deny]

The exact UI SHALL be determined during PRD.

-------------------------------------------------------------------------------

# 37. Approval and Context

Approval requests SHOULD contain sufficient information for the user to
make a decision.

The interface SHALL not expose hidden model reasoning.

The user should understand:

- what will happen,
- where it will happen,
- which capability will be used,
- how long the authorization will last.

-------------------------------------------------------------------------------

# 38. Permission Audit

ClaireCoder SHOULD maintain a permission audit trail.

Events MAY include:

- permission requested,
- permission granted,
- permission denied,
- policy changed,
- autonomy changed,
- YOLO enabled,
- Tool executed.

Sensitive values SHALL not be recorded unnecessarily.

-------------------------------------------------------------------------------

# 39. Security Events

Security-relevant events SHOULD be distinguishable from ordinary Tool output.

Potential events include:

- blocked operation,
- unauthorized path,
- suspicious extension,
- credential access,
- policy conflict,
- denied network operation,
- permission escalation attempt.

These events SHOULD be visible in diagnostics.

-------------------------------------------------------------------------------

# 40. Sandboxing

ClaireCoder SHOULD support sandboxing where practical.

Potential sandbox boundaries include:

- filesystem,
- process,
- network,
- environment,
- workspace.

Sandboxing SHALL remain an additional protection layer.

It SHALL not replace the Permission Engine.

-------------------------------------------------------------------------------

# 41. Worktrees

ClaireCoder MAY support Git worktrees for safer autonomous development.

A Workflow MAY operate in a dedicated worktree.

Potential benefits include:

- isolation,
- safer experimentation,
- easier review,
- easier rollback,
- parallel development.

Worktree orchestration SHALL remain optional for V1.

-------------------------------------------------------------------------------

# 42. Recovery

When an operation is interrupted or fails, ClaireCoder SHOULD record:

- operation state,
- Tool state,
- affected files where known,
- task state,
- validation state.

The Engineering Engine SHALL determine whether to:

- retry,
- rollback,
- replan,
- request user intervention.

The Permission Engine SHALL not assume that an interrupted operation was
completed.

-------------------------------------------------------------------------------

# 43. Permission Failure

Permission denial SHALL be treated as a normal execution outcome.

A denied operation SHOULD return structured information to the Engineering
Engine.

The Engineering Engine MAY:

- continue without the operation,
- ask the user for another approach,
- request permission again if circumstances changed,
- replan.

It SHALL not repeatedly request the same denied operation without meaningful
change.

-------------------------------------------------------------------------------

# 44. Decision Rationale

This architecture was selected because ClaireCoder requires both autonomy and
safety.

A coding agent that asks for permission for every harmless operation becomes
slow and frustrating.

A coding agent that performs unrestricted operations without user control
becomes unsafe.

The centralized Permission Engine provides the boundary.

The autonomy system determines how aggressively ClaireCoder operates inside
that boundary.

This allows experienced users to operate with greater autonomy while
preserving explicit security controls.

-------------------------------------------------------------------------------

# 45. Alternatives Considered

## Alternative A — UI-Only Permissions

Decision:

REJECTED.

Reason:

Commands, Skills, MCP, subagents, and autonomous workflows could potentially
bypass UI-level authorization.

-------------------------------------------------------------------------------

## Alternative B — Tool-Owned Permissions

Decision:

REJECTED.

Reason:

Each Tool would implement different security behavior and extensions could
create inconsistent permission boundaries.

-------------------------------------------------------------------------------

## Alternative C — Always Ask

Decision:

REJECTED.

Reason:

This would make routine engineering work unnecessarily slow.

-------------------------------------------------------------------------------

## Alternative D — Always Autonomous

Decision:

REJECTED.

Reason:

Users need control over destructive and sensitive operations.

-------------------------------------------------------------------------------

## Alternative E — Autonomy Automatically Grants Permissions

Decision:

REJECTED.

Reason:

Autonomy and authorization are different concepts.

-------------------------------------------------------------------------------

# 46. Consequences

## Positive Consequences

- Centralized security.
- Explicit authorization.
- Configurable autonomy.
- Workspace protection.
- Skill security.
- MCP security.
- Model independence.
- Tool independence.
- Better transparency.
- Safer autonomous execution.
- Extensible permission policy.

## Negative Consequences

- Permission evaluation adds architectural complexity.
- Policy scopes require careful design.
- Approval UX must remain understandable.
- Risk classification can never perfectly predict every command.
- Advanced sandboxing may require platform-specific implementation.

These costs are accepted because execution security is fundamental to
ClaireCoder.

-------------------------------------------------------------------------------

# 47. V1 Boundary

The following SHALL be part of the V1 architecture:

Permission:

- centralized Permission Engine,
- ALLOW / ASK / DENY,
- workspace boundaries,
- Tool permissions,
- terminal permissions,
- filesystem permissions,
- Git permissions,
- network permissions,
- Skill permissions,
- MCP permissions,
- approval scopes,
- permission persistence.

Autonomy:

- Assisted,
- Balanced,
- Autonomous,
- explicit advanced YOLO capability where implemented.

Security:

- extension trust concept,
- prompt-injection boundary,
- secret protection,
- environment protection,
- permission audit,
- interruption handling.

The following MAY remain optional:

- advanced sandboxing,
- automatic command risk analysis,
- advanced worktree orchestration,
- enterprise policy management,
- remote policy servers,
- advanced security analytics.

ClaireCoder SHALL not require these systems to operate as a useful V1 coding
agent.

-------------------------------------------------------------------------------

# 48. Implementation Guidance

The implementation SHOULD initially favor:

- one centralized Permission Engine,
- simple policy objects,
- explicit permission requests,
- structured approval events,
- workspace-aware filesystem checks,
- command-aware terminal checks,
- clear autonomy configuration.

The implementation SHALL avoid:

- permission logic scattered throughout Tools,
- hidden authorization,
- automatic privilege escalation,
- mandatory sandboxing,
- mandatory YOLO behavior,
- complex enterprise policy systems,
- storing secrets in model context.

-------------------------------------------------------------------------------

# 49. Decision Status

STATUS

ACCEPTED

This ADR establishes the Permission, Autonomy, and Security architecture for
ClaireCoder V1.

It completes the planned six-document ADR architecture phase.

Future changes to these security boundaries SHALL require an explicit
architectural decision or superseding ADR.

-------------------------------------------------------------------------------

# 50. Relationship With Other ADRs

CC-ADR-001

ClaireCoder Core Architecture

Defines the overall architecture.

CC-ADR-002

Model Gateway & Provider Architecture

Defines model execution and provider independence.

CC-ADR-003

Tool & Skill Extension Architecture

Defines Tools, Skills, and extension mechanisms.

CC-ADR-004

Workflow, Context & Engineering Session Architecture

Defines engineering execution and persistent state.

CC-ADR-005

Interaction, Modes & Command Architecture

Defines user-facing interaction and operational Modes.

CC-ADR-006

Permission, Autonomy & Security Architecture

Defines execution authorization, autonomy, and security boundaries.

-------------------------------------------------------------------------------

# 51. AI Instructions

When implementing or documenting ClaireCoder after this ADR:

1. Treat the Permission Engine as the authoritative execution boundary.
2. Apply permissions to every executable Tool.
3. Apply permissions to Skills that request executable capabilities.
4. Apply permissions to MCP.
5. Apply permissions to terminal execution.
6. Apply permissions to filesystem operations.
7. Apply permissions to Git operations.
8. Apply permissions to network operations.
9. Preserve ALLOW / ASK / DENY.
10. Preserve scoped authorization.
11. Preserve workspace boundaries.
12. Keep autonomy separate from authorization.
13. Preserve Assisted, Balanced, and Autonomous concepts.
14. Keep YOLO explicit and visible if implemented.
15. Never silently escalate privileges.
16. Keep permissions independent of the selected model.
17. Keep permissions independent of individual Tool implementations.
18. Treat third-party extensions as potentially untrusted.
19. Protect credentials from unnecessary model exposure.
20. Treat repository and external content as potentially untrusted.
21. Preserve prompt-injection boundaries.
22. Preserve permission audit information without storing secrets.
23. Preserve interruption and recovery behavior.
24. Do not make advanced sandboxing mandatory for V1.
25. Do not over-engineer the permission system.
26. Treat this ADR as the authoritative Permission, Autonomy, and Security
    architecture unless explicitly superseded.

###############################################################################

END OF CC-ADR-006

###############################################################################