###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-005
# Title           : Interaction, Modes & Command Architecture
# Version         : 1.0.0
# Status          : Accepted
#
###############################################################################

# 1. Decision Summary

ClaireCoder SHALL use separate but coordinated systems for:

- Interaction,
- Modes,
- Commands,
- Status,
- User approvals,
- Session controls.

The Interaction Layer SHALL provide the user-facing experience without
containing the core engineering logic.

Commands SHALL represent explicit user-invoked operations.

Modes SHALL represent the operational behavior of ClaireCoder during a
session or task.

Modes SHALL NOT become collections of unrelated Commands.

Commands SHALL NOT contain the core implementation of the capabilities they
invoke.

The system SHALL support both interactive agent operation and explicit
command-driven operation.

The interface SHALL remain usable with a single available model and SHALL
not assume the presence of multiple model providers.

The ClaireCoder interface SHALL support a recognizable Claire identity,
including the Claire visual/header treatment, while keeping the UI separate
from the core agent architecture.

-------------------------------------------------------------------------------

# 2. Context

The ClaireCoder research phase established that the agent should provide a
workflow comparable in capability to modern coding agents while retaining
its own architecture and behavior.

ClaireCoder is expected to provide:

- interactive coding,
- planning,
- execution,
- review,
- debugging,
- model selection,
- Skill management,
- Tool management,
- session management,
- permissions,
- configurable autonomy.

The system also requires explicit Commands similar to modern coding-agent
interfaces.

At the same time, ClaireCoder needs Modes because different engineering
situations require different behavior.

For example:

- planning should behave differently from implementation,
- review should behave differently from debugging,
- autonomous execution should behave differently from interactive work.

These concepts must therefore remain distinct.

-------------------------------------------------------------------------------

# 3. Problem

Without clear separation between Modes and Commands, the interface could
become difficult to understand.

For example:

A Mode might be:

    REVIEW

while a Command might be:

    /review

The two are related but are not identical.

A Mode defines how ClaireCoder behaves.

A Command tells ClaireCoder to perform a specific operation.

If Commands become responsible for the actual implementation:

- business logic becomes coupled to the CLI,
- alternate interfaces become difficult,
- automation becomes harder,
- testing becomes harder.

If Modes contain executable implementations:

- behavior becomes tightly coupled,
- workflows become difficult to reuse,
- Mode configuration becomes overly complex.

Therefore the architecture SHALL keep:

Interaction
    ↓
Commands / Modes
    ↓
Engineering Engine
    ↓
Workflow / Context / Model / Tools

-------------------------------------------------------------------------------

# 4. Decision

ClaireCoder SHALL use the following conceptual architecture:

                              CLAIRECODER
                                   │
                         ┌─────────┴─────────┐
                         │                   │
                    INTERACTION          SESSION STATE
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
           Commands     Modes     Approval UI
              │          │
              └────┬─────┘
                   │
                   ▼
            ENGINEERING ENGINE
                   │
       ┌───────────┼───────────┐
       │           │           │
       ▼           ▼           ▼
   Workflow     Context      Model
       │           │         Gateway
       │           │
       └───────────┼───────────┘
                   │
                   ▼
                 Tools

The Interaction Layer SHALL communicate with the Engineering Engine through
defined interfaces.

The Interaction Layer SHALL NOT directly execute privileged operations.

-------------------------------------------------------------------------------

# 5. Interaction Layer

## 5.1 Purpose

The Interaction Layer SHALL provide the user-facing interface to ClaireCoder.

It MAY be implemented initially as a CLI/TUI-style interface.

Future interfaces MAY include:

- graphical interface,
- editor integration,
- IDE integration,
- remote interface.

These interfaces SHALL use the same underlying Engineering Engine.

-------------------------------------------------------------------------------

# 6. Interactive Agent Mode

ClaireCoder SHALL support natural interactive operation.

The user MAY simply provide a request such as:

    "Fix the authentication bug."

The Engineering Engine SHALL determine:

- required context,
- planning depth,
- relevant Skills,
- required Tools,
- model interaction,
- validation.

The user SHALL not need to convert every request into a Command.

-------------------------------------------------------------------------------

# 7. Command System

Commands SHALL provide explicit control over ClaireCoder.

Conceptual examples include:

    /help
    /model
    /mode
    /skills
    /tools
    /status
    /plan
    /review
    /clear
    /resume
    /sessions
    /config

The final Command list SHALL be determined during PRD and implementation
planning.

This ADR establishes the architecture rather than freezing the final command
catalog.

-------------------------------------------------------------------------------

# 8. Command Categories

Commands SHOULD be grouped conceptually.

## 8.1 Agent Commands

Commands controlling agent execution.

Examples:

- plan,
- execute,
- stop,
- continue,
- retry.

-------------------------------------------------------------------------------

## 8.2 Session Commands

Commands controlling Engineering Sessions.

Examples:

- new session,
- resume,
- list sessions,
- pause,
- archive.

-------------------------------------------------------------------------------

## 8.3 Model Commands

Commands controlling model configuration.

Examples:

- show model,
- switch model,
- list models,
- configure provider.

-------------------------------------------------------------------------------

## 8.4 Mode Commands

Commands controlling operational Mode.

Examples:

- show mode,
- switch mode,
- list modes.

-------------------------------------------------------------------------------

## 8.5 Skill Commands

Commands controlling Skills.

Examples:

- list Skills,
- install Skill,
- enable Skill,
- disable Skill,
- inspect Skill,
- install Collection.

-------------------------------------------------------------------------------

## 8.6 Tool Commands

Commands controlling Tool visibility and configuration.

Examples:

- list Tools,
- inspect Tool,
- enable/disable optional Tool,
- inspect Tool permissions.

-------------------------------------------------------------------------------

## 8.7 Configuration Commands

Commands controlling ClaireCoder configuration.

Examples:

- configuration inspection,
- configuration editing,
- reset configuration,
- environment diagnostics.

-------------------------------------------------------------------------------

# 9. Command Parsing

The Command System SHALL distinguish explicit Commands from ordinary user
requests.

Conceptually:

Input
 │
 ├── Command prefix
 │       ↓
 │    Command Parser
 │       ↓
 │    Command Handler
 │
 └── Natural language
         ↓
     Engineering Engine

The parser SHALL not need to understand the complete engineering semantics of
a natural-language request.

-------------------------------------------------------------------------------

# 10. Command Execution

Commands SHALL invoke capabilities through existing ClaireCoder systems.

For example:

    /review

SHALL NOT implement review logic itself.

Instead:

Command
   ↓
Engineering Engine
   ↓
Review Workflow
   ↓
Context / Skills / Tools
   ↓
Model

This keeps the Command layer lightweight.

-------------------------------------------------------------------------------

# 11. Command Arguments

Commands SHOULD support structured arguments.

For example:

    /model <model>

    /mode <mode>

    /skills <action>

    /resume <session>

The final argument grammar SHALL be determined during implementation.

Invalid arguments SHOULD produce clear user-facing errors.

-------------------------------------------------------------------------------

# 12. Command Discoverability

ClaireCoder SHALL make Commands discoverable.

The interface SHOULD support:

- help,
- command suggestions,
- command completion where practical,
- descriptions,
- argument hints.

The user SHALL not need to memorize every Command.

-------------------------------------------------------------------------------

# 13. Modes

## 13.1 Definition

A Mode SHALL represent a behavioral configuration for ClaireCoder.

A Mode MAY influence:

- planning behavior,
- interaction style,
- Tool defaults,
- Skill activation,
- approval behavior,
- validation expectations,
- autonomy.

A Mode SHALL not directly implement the underlying capabilities.

-------------------------------------------------------------------------------

# 14. Initial Mode Architecture

ClaireCoder SHALL support the concept of specialized Modes.

Candidate V1 Modes include:

BUILD

Used for normal implementation work.

PLAN

Used primarily for analysis and planning.

REVIEW

Used for inspecting existing work and identifying issues.

DEBUG

Used for diagnosing and resolving failures.

RESEARCH

Used for gathering and evaluating technical information.

These are architectural candidates.

The final Mode roster SHALL be confirmed during PRD.

-------------------------------------------------------------------------------

# 15. Mode Behavior

A Mode SHALL be represented as configuration and behavior rules rather than
as an independent agent implementation.

Conceptually:

Mode
 │
 ├── Planning policy
 ├── Tool policy
 ├── Skill policy
 ├── Permission defaults
 ├── Validation policy
 └── Interaction behavior

The Engineering Engine SHALL interpret these policies.

-------------------------------------------------------------------------------

# 16. Mode Switching

Users SHOULD be able to switch Modes during a Session.

For example:

BUILD
   ↓
DEBUG
   ↓
REVIEW
   ↓
BUILD

Switching Modes SHALL not automatically destroy:

- plan,
- session state,
- Memory,
- repository context.

The Engineering Engine SHALL re-evaluate the active Workflow where necessary.

-------------------------------------------------------------------------------

# 17. Mode and Workflow

Modes SHALL remain separate from Workflows.

Mode:

    "How should ClaireCoder operate?"

Workflow:

    "What engineering process is being performed?"

For example:

DEBUG Mode
    ↓
Debugging Workflow

BUILD Mode
    ↓
Implementation Workflow

REVIEW Mode
    ↓
Review Workflow

A Mode MAY influence a Workflow without becoming the Workflow itself.

-------------------------------------------------------------------------------

# 18. Mode and Model

Modes SHALL not require a specific model.

A Mode MAY define model preferences or capability requirements.

For example:

RESEARCH Mode
    ↓
Preference: strong reasoning / web capability

However, the Model Gateway SHALL determine whether the selected model can
satisfy the requirements.

A user with only one model SHALL still be able to use the Mode whenever that
model provides sufficient capabilities.

-------------------------------------------------------------------------------

# 19. Mode and Skills

Modes MAY activate or recommend Skills.

For example:

BUILD
    ↓
Frontend Skill

REVIEW
    ↓
Code Quality Skill

RESEARCH
    ↓
Research Skill

Skills remain independently manageable.

The user SHALL be able to disable or replace Skills where appropriate.

-------------------------------------------------------------------------------

# 20. Mode and Permissions

Modes MAY define permission defaults.

For example:

PLAN

Prefer read-only operations.

BUILD

Allow normal development operations.

REVIEW

Prefer read-only operations.

DEBUG

Allow diagnostic execution and targeted modification.

These are defaults only.

The Permission Engine remains authoritative.

-------------------------------------------------------------------------------

# 21. Autonomy

Autonomy SHALL remain a separate concept from Mode.

A Mode may recommend an autonomy level.

However:

Mode
    ≠
Autonomy

Autonomy determines how independently ClaireCoder can execute actions.

Modes determine the operational behavior of the agent.

The final autonomy architecture SHALL be defined in CC-ADR-006.

-------------------------------------------------------------------------------

# 22. Status Interface

ClaireCoder SHOULD provide persistent execution status.

The interface SHOULD expose relevant information such as:

- active Mode,
- active Model,
- current Session,
- current Workflow,
- current Task,
- Tool execution,
- Skill activity,
- approval state,
- planning state.

The status display SHALL remain compact and readable.

-------------------------------------------------------------------------------

# 23. Claire Identity

ClaireCoder SHALL have its own visual identity within the Claire ecosystem.

The header/status area SHOULD include Claire's visual representation or
approved Claire image treatment.

The intended interaction pattern is similar in spirit to how other coding
agents display a recognizable identity in their interface.

However, ClaireCoder SHALL not depend on the image for functionality.

The visual layer SHALL remain separate from the Engineering Engine.

-------------------------------------------------------------------------------

# 24. Header Architecture

The header MAY display:

    Claire image / identity
    ClaireCoder
    active model
    active Mode
    session status

The exact visual design SHALL be defined during PRD and UI implementation.

The architecture SHALL only require that the identity layer be replaceable
without affecting the core agent.

-------------------------------------------------------------------------------

# 25. Approval Interface

When the Permission Engine returns ASK, the Interaction Layer SHALL present
the approval request.

The approval UI SHOULD communicate:

- requested action,
- Tool,
- target,
- risk,
- requested permission scope.

The Interaction Layer SHALL pass the user's decision back to the Permission
Engine.

It SHALL not independently authorize execution.

-------------------------------------------------------------------------------

# 26. Interruptions

The user SHALL be able to interrupt active execution.

The Interaction Layer SHOULD provide:

- stop,
- cancel,
- pause where supported.

An interruption SHALL update the Engineering Session appropriately.

The agent SHALL not assume that an interrupted Tool completed successfully.

-------------------------------------------------------------------------------

# 27. Streaming Interface

The Interaction Layer SHOULD support streamed output.

The interface MAY display:

- model response,
- Tool activity,
- planning activity,
- validation,
- errors,
- status updates.

The interface SHALL avoid exposing internal chain-of-thought.

It MAY display concise progress information instead.

-------------------------------------------------------------------------------

# 28. Progress Representation

ClaireCoder SHOULD expose meaningful progress.

For example:

    Planning
      ↓
    Inspecting repository
      ↓
    Editing
      ↓
    Running tests
      ↓
    Validating
      ↓
    Complete

Progress SHALL represent actual system state rather than fabricated
percentages.

-------------------------------------------------------------------------------

# 29. User Input During Execution

The user MAY provide additional instructions while execution is active.

The Engineering Engine SHALL determine whether the new input:

- modifies the current task,
- pauses the current task,
- creates a new task,
- requires clarification.

The Interaction Layer SHALL not make this determination independently.

-------------------------------------------------------------------------------

# 30. Help System

ClaireCoder SHALL provide a help mechanism.

Help SHOULD expose:

- Commands,
- Modes,
- Skills,
- Tools,
- configuration,
- model information,
- active permissions where useful.

Help MAY be context-sensitive.

-------------------------------------------------------------------------------

# 31. Error Presentation

Errors SHALL be presented at the appropriate abstraction level.

The interface SHOULD distinguish:

- user input error,
- Command error,
- model error,
- Tool error,
- permission denial,
- Workflow failure,
- configuration error.

Raw stack traces SHOULD not be the default user-facing error format.

Detailed diagnostics MAY be available when requested.

-------------------------------------------------------------------------------

# 32. Interaction State

The Interaction Layer MAY maintain UI state such as:

- current input,
- display state,
- selected panel,
- expanded Tool information,
- approval dialog state.

This state SHALL remain separate from Engineering Session state.

UI state SHOULD not become authoritative engineering state.

-------------------------------------------------------------------------------

# 33. Non-Interactive Operation

ClaireCoder SHALL support non-interactive execution as part of the V1 interface.

Potential uses include:

- scripts,
- CI,
- automation,
- scheduled tasks,
- development pipelines.

The same Engineering Engine SHALL be used.

The interface SHALL therefore not be the source of core engineering logic.

-------------------------------------------------------------------------------

# 34. CLI/TUI Boundary

The V1 interface SHALL provide both an interactive TUI and a non-interactive CLI architecture.

Conceptually:

CLI/TUI
   ↓
Interaction API
   ↓
Engineering Engine

The Engineering Engine SHALL not directly depend on terminal rendering.

This keeps future GUI or IDE integrations possible.

-------------------------------------------------------------------------------

# 35. Decision Rationale

This architecture was selected because it provides:

- explicit Commands,
- natural-language interaction,
- configurable Modes,
- clear status,
- approval interaction,
- interruption,
- model switching,
- Skill management,
- Session management.

More importantly, it prevents the interface from becoming the actual agent.

Commands become entry points.

Modes become behavioral configuration.

The Engineering Engine remains responsible for engineering execution.

-------------------------------------------------------------------------------

# 36. Alternatives Considered

## Alternative A — Everything Is a Command

Decision:

REJECTED.

Reason:

Natural-language interaction is a core coding-agent behavior and should not
require command syntax for ordinary engineering work.

-------------------------------------------------------------------------------

## Alternative B — Everything Is a Mode

Decision:

REJECTED.

Reason:

Modes are persistent behavioral configurations, while Commands represent
explicit user actions.

-------------------------------------------------------------------------------

## Alternative C — Commands Directly Execute Tools

Decision:

REJECTED.

Reason:

This would bypass the Engineering Engine and make alternate interfaces
difficult.

-------------------------------------------------------------------------------

## Alternative D — UI Owns Session State

Decision:

REJECTED.

Reason:

Engineering state must survive interface changes, interruption, and future
non-interactive operation.

-------------------------------------------------------------------------------

## Alternative E — Separate Agent Per Mode

Decision:

REJECTED.

Reason:

This would duplicate the Engineering Engine and make behavior unnecessarily
fragmented.

-------------------------------------------------------------------------------

# 37. Consequences

## Positive Consequences

- Clear interaction architecture.
- Natural-language and command interaction.
- Explicit Modes.
- Reusable Workflows.
- Future interface support.
- Centralized engineering state.
- Better user visibility.
- Clear approval handling.
- Easier testing.

## Negative Consequences

- Command and Mode boundaries must remain clear.
- Interaction APIs must be maintained.
- Mode configuration can become complex if uncontrolled.
- Progress reporting requires accurate state events.
- Multiple interfaces eventually require consistent interaction behavior.

These costs are accepted because user interaction is a major part of
ClaireCoder's product identity.

-------------------------------------------------------------------------------

# 38. V1 Boundary

The following SHALL be part of the V1 architecture:

Interaction:

- interactive agent operation,
- non-interactive CLI operation,
- command parser,
- command execution layer,
- help,
- status,
- progress,
- approval interaction,
- interruption,
- streaming.

Modes:

- Mode abstraction,
- Mode switching,
- Mode configuration,
- Mode/Workflow integration.

Commands:

- agent commands,
- session commands,
- model commands,
- mode commands,
- Skill commands,
- Tool commands,
- configuration commands.

The following MAY remain optional:

- full graphical interface,
- IDE integrations,
- advanced command completion,
- remote UI,
- multi-user interaction.

-------------------------------------------------------------------------------

# 39. Implementation Guidance

The implementation SHOULD initially favor:

- a small command registry,
- explicit Mode definitions,
- structured command arguments,
- event-driven status updates,
- a clean Interaction API,
- terminal-independent Engineering Engine logic.

The implementation SHALL avoid:

- putting engineering logic inside Commands,
- creating separate agents for every Mode,
- coupling the Engineering Engine to terminal rendering,
- making every operation require a Command,
- creating a large command language for V1.

-------------------------------------------------------------------------------

# 40. Decision Status

STATUS

ACCEPTED

This ADR establishes the Interaction, Modes, and Command architecture for
ClaireCoder V1.

Later ADRs MAY refine:

- permission behavior,
- autonomy,
- Tool interaction,
- Skill interaction,
- UI implementation.

Any fundamental change to the Mode/Command/Interaction boundaries SHALL
explicitly supersede this ADR.

-------------------------------------------------------------------------------

# 41. Relationship With Other ADRs

CC-ADR-001

ClaireCoder Core Architecture

Defines the overall system boundaries.

CC-ADR-002

Model Gateway & Provider Architecture

Defines model execution.

CC-ADR-003

Tool & Skill Extension Architecture

Defines Tools and Skills.

CC-ADR-004

Workflow, Context & Engineering Session Architecture

Defines engineering execution and persistent state.

CC-ADR-005

Interaction, Modes & Command Architecture

Defines the user-facing control architecture.

CC-ADR-006

Permission, Autonomy & Security Architecture

Defines execution security, autonomy, and approval policy.

-------------------------------------------------------------------------------

# 42. AI Instructions

When implementing or documenting ClaireCoder after this ADR:

1. Keep Commands separate from Modes.
2. Keep Modes separate from Workflows.
3. Keep the Interaction Layer separate from the Engineering Engine.
4. Preserve natural-language interaction.
5. Preserve explicit Commands.
6. Keep command logic lightweight.
7. Keep engineering logic inside the Engineering Engine.
8. Keep UI state separate from Engineering Session state.
9. Preserve Mode switching.
10. Preserve session continuity during Mode switching.
11. Keep autonomy separate from Mode.
12. Keep Permissions authoritative.
13. Provide meaningful execution status.
14. Provide interruption support.
15. Avoid exposing internal chain-of-thought.
16. Preserve the Claire visual identity in the interface layer.
17. Keep the visual identity independent from core functionality.
18. Preserve future GUI and IDE compatibility.
19. Keep non-interactive execution possible.
20. Do not over-engineer the command system.
21. Treat this ADR as the authoritative Interaction, Modes, and Command
    architecture unless explicitly superseded.

###############################################################################

END OF CC-ADR-005

###############################################################################