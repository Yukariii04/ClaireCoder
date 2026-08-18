###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-007
# Title           : ClaireCoder CLI & TUI Architecture
# Version         : 2.0.0
# Status          : FINAL
#
###############################################################################

# 1. Decision Summary

This ADR defines the architecture for the ClaireCoder V1 CLI and Terminal User
Interface.

The CLI and TUI SHALL be implemented as presentation and interaction frontends
above the already-approved ClaireCoder V1 application architecture.

The architectural relationship SHALL be:

    CLI / TUI
        ↓
    InteractionController
        ↓
    ClaireCoderV1
        ↓
    Existing V1 Subsystems

The CLI/TUI SHALL NOT become another engineering orchestration layer.

The CLI/TUI SHALL remain replaceable without requiring changes to the approved
Engineering Engine, Workflow, Execution, Verification, Permission, Context,
Tool, Skill, or Model Gateway architecture.

The terminal frontend SHALL remain a terminal-native surface.

The graphical Claire mascot is intentionally NOT part of the terminal rendering
architecture in this revision.

The graphical desktop frontend is defined separately by:

    CC-PRD-012
    CC-ADR-008
    DESKTOP-DESIGN.md


-------------------------------------------------------------------------------

# 2. Context

CC-PRD-011 defines the ClaireCoder V1 CLI and TUI as the terminal-based
developer interaction surface.

The approved ClaireCoder architecture already provides:

    - Engineering Engine
    - Model Gateway
    - Tool system
    - Skill system
    - Permission Engine
    - Context Engine
    - Workflow / Planning
    - Execution State
    - Interaction Layer
    - Verification
    - ClaireCoderV1 integration boundary

The CLI/TUI therefore does not need to own these concerns.

The architectural problem is to expose the approved system through a usable
terminal interface without creating duplicate ownership or bypassing existing
boundaries.

The terminal visual system is governed by:

    TUI-DESIGN.md

and:

    ClaireCoder-TUI-Design-V1.png

The graphical Claire mascot remains a valid Claire ecosystem identity, but
graphical mascot rendering is now a Desktop GUI responsibility rather than a
terminal responsibility.

The Desktop GUI architecture is defined separately through:

    CC-PRD-012
    CC-ADR-008
    DESKTOP-DESIGN.md


-------------------------------------------------------------------------------

# 3. Decision

ClaireCoder SHALL implement the CLI and TUI as thin frontends over the existing
Interaction and Application boundaries.

The TUI SHALL be responsible for:

    - rendering,
    - input focus,
    - keyboard handling,
    - terminal presentation,
    - terminal adaptation,
    - scrollback presentation,
    - UI-level interaction feedback.

The CLI SHALL be responsible for:

    - argument handling,
    - non-interactive input/output,
    - script-friendly invocation,
    - exit codes,
    - structured/log-friendly output.

The Interaction Layer SHALL remain responsible for:

    - command parsing,
    - command routing,
    - interaction modes,
    - interaction semantics.

ClaireCoderV1 SHALL remain responsible for:

    - top-level V1 application lifecycle,
    - coordination of the approved V1 architecture.

No UI component shall become an owner of engineering state.


-------------------------------------------------------------------------------

# 4. Architectural Position

The CLI/TUI SHALL sit above the approved application boundary.

The conceptual architecture is:

    ┌─────────────────────────────────┐
    │          CLI / TUI              │
    │      Presentation / Input       │
    └───────────────┬─────────────────┘
                    ↓
    ┌─────────────────────────────────┐
    │      InteractionController       │
    │   Commands / Interaction Modes   │
    └───────────────┬─────────────────┘
                    ↓
    ┌─────────────────────────────────┐
    │          ClaireCoderV1          │
    │       Application Boundary      │
    └───────────────┬─────────────────┘
                    ↓
    ┌───────────────────────────────────────────────────────────┐
    │                    Existing V1 System                     │
    │                                                           │
    │ Engine │ Workflow │ Execution │ Verification │ Context   │
    │ Tools  │ Skills   │ Gateway   │ Permissions               │
    └───────────────────────────────────────────────────────────┘

The CLI/TUI SHALL consume public application and interaction interfaces.


-------------------------------------------------------------------------------

# 5. Frontend Separation

The architecture SHALL maintain a clear separation between:

    CLI

        Non-interactive command-line frontend.

    TUI

        Interactive terminal frontend.

Both frontends SHALL share the same approved application and interaction
boundaries.

The architecture SHALL NOT duplicate engineering behavior separately inside
the CLI and TUI.

Shared engineering/application behavior MUST remain below the frontend
boundary.

The conceptual relationship is:

    CLI ───────────┐
                    ├──→ Interaction Layer
    TUI ───────────┘
                         ↓
                    ClaireCoderV1
                         ↓
                    Existing V1 System


-------------------------------------------------------------------------------

# 6. InteractionController Boundary

InteractionController SHALL remain the authoritative interface for user-facing
interaction semantics defined by CC-PRD-005.

Application/interaction commands such as:

    /help
    /status
    /model
    /mode
    /session
    /plan
    /pause
    /resume
    /cancel
    /clear
    /exit

SHALL route through the Interaction Layer.

The TUI SHALL NOT reinterpret these commands into independent engineering
operations.

The CLI SHALL use the same command semantics.

The frontend MAY provide additional presentation-only controls such as:

    /tree
    /review
    /compact

when those operations do not require ownership of engineering state.


-------------------------------------------------------------------------------

# 7. ClaireCoderV1 Boundary

ClaireCoderV1 SHALL remain the top-level application boundary.

The CLI/TUI SHALL request application behavior through its public interface.

The CLI/TUI SHALL NOT:

    - construct a second Engineering Engine,
    - reproduce Workflow orchestration,
    - reproduce Execution lifecycle,
    - reproduce Verification evaluation,
    - reproduce Permission policy,
    - reproduce model-provider logic,
    - mutate private application state.

The CLI/TUI SHALL remain a consumer of ClaireCoderV1.


-------------------------------------------------------------------------------

# 8. State Projection Model

The TUI SHALL display state owned by the underlying ClaireCoder architecture.

The TUI MAY display:

    - session state,
    - Workflow state,
    - Task state,
    - Execution state,
    - Verification state,
    - Permission requests,
    - model information,
    - context usage,
    - repository change information.

The TUI SHALL NOT become the source of truth for those states.

The conceptual model is:

    Authoritative V1 State
        ↓
    Presentation Projection
        ↓
    TUI Rendering

The TUI SHALL NOT maintain independent copies of authoritative engineering
state that can diverge from the application.


-------------------------------------------------------------------------------

# 9. TUI Input State Architecture

The following SHALL be treated as presentation/input states:

    NORMAL
    STREAMING
    CONFIRMATION
    OVERLAY
    INTERRUPTED
    EXITING

These states SHALL belong only to the UI/input layer.

They SHALL NOT be used to replace:

    Workflow state,
    Execution state,
    Verification state,
    Permission policy state.

The UI may change between these presentation states without changing
engineering ownership.


-------------------------------------------------------------------------------

# 10. Command Routing

Command routing SHALL preserve the distinction between application commands
and presentation commands.

The architecture SHALL use:

    User Command
        ↓
    Command Parser / Interaction Layer
        ↓
    Appropriate Public Boundary
        ↓
    Result
        ↓
    Frontend Presentation

The frontend SHALL not directly invoke internal subsystem methods to implement
a command.

If a required public operation does not exist, that operation SHALL be added
to the owning subsystem rather than bypassing the boundary from the frontend.


-------------------------------------------------------------------------------

# 11. Permission Architecture

The TUI SHALL display Permission Engine requests and decisions.

The TUI SHALL NOT make authorization decisions.

The permission interaction SHALL conceptually be:

    Tool Operation Requested
        ↓
    Permission Engine
        ↓
    Permission Result
        ↓
    TUI Confirmation / Status Presentation

The TUI MAY collect user input such as:

    yes
    no
    always for this session
    diff
    cancel

but the resulting authorization semantics SHALL remain owned by the approved
Permission architecture.

The TUI SHALL NOT bypass PermissionEngine to execute a Tool.


-------------------------------------------------------------------------------

# 12. Tool Execution Boundary

The CLI/TUI SHALL never execute Tools directly.

The architectural chain SHALL remain:

    User
        ↓
    CLI / TUI
        ↓
    Interaction / Application
        ↓
    Engineering System
        ↓
    ToolExecutor
        ↓
    PermissionEngine
        ↓
    Tool

The CLI/TUI MAY display Tool requests and results.

It SHALL NOT contain Tool execution implementations.


-------------------------------------------------------------------------------

# 13. Workflow and Task Presentation

The TUI MAY display:

    - current Workflow,
    - current Task,
    - Task progress,
    - plan progress,
    - completion state,
    - validation state.

The Workflow subsystem remains authoritative.

The TUI SHALL NOT:

    - calculate Task ordering,
    - select the next Task,
    - create recovery plans,
    - change Workflow state directly,
    - recreate Workflow transitions.

The Workflow view SHALL therefore be read-oriented.


-------------------------------------------------------------------------------

# 14. Execution State Presentation

The TUI MAY display:

    - running execution,
    - execution completion,
    - failure,
    - cancellation,
    - retry/recovery information.

ExecutionManager remains the authoritative owner of Execution State.

The TUI SHALL NOT:

    - create execution state independently,
    - maintain attempts independently,
    - decide execution success,
    - implement retry logic,
    - mutate ExecutionManager internals.


-------------------------------------------------------------------------------

# 15. Verification Presentation

The TUI MAY display:

    - Verification progress,
    - Verification results,
    - passed criteria,
    - failed criteria,
    - evidence summaries,
    - blocked state.

VerificationEngine remains authoritative.

The TUI SHALL NOT:

    - evaluate evidence,
    - mark Verification successful,
    - fabricate evidence,
    - mutate Verification state directly.

The display SHALL reflect actual Verification results.


-------------------------------------------------------------------------------

# 16. Terminal Claire Identity Architecture

The terminal SHALL use Claire as a textual/persona identity rather than a
graphical mascot.

The terminal SHALL use:

    - CLAIRECODER wordmark / branding,
    - ClaireCoder visual language,
    - Claire text/persona messages.

A terminal Claire message SHALL conceptually appear as:

    Claire:
        Streaming decode support has been added.
        All tests are passing.
        What would you like to work on next?

The terminal SHALL NOT require:

    - mascot sprite assets,
    - graphical mascot states,
    - terminal image protocols,
    - half-block mascot rendering,
    - Unicode reconstruction of Claire.

The canonical graphical Claire mascot remains a Desktop GUI concern.

The terminal absence of graphical mascot rendering SHALL NOT affect
ClaireCoder functionality.

This does NOT remove the Claire mascot from the broader Claire ecosystem.


-------------------------------------------------------------------------------

# 17. Terminal Startup Architecture

The terminal startup SHALL use the CLAIRECODER wordmark / branding.

The startup SHALL NOT require graphical mascot rendering.

The startup may present:

    CLAIRECODER
    Engineering. Automated.

    > Loading configuration
    > Connecting model gateway
    > Registering tools
    > Preparing workspace
    > Loading skills
    > Starting session

Startup information SHALL originate from the real launcher/application
lifecycle.

The TUI SHALL NOT become a second initialization authority.


-------------------------------------------------------------------------------

# 18. Event / Activity Presentation

The TUI SHALL present agent activity through a rendering layer.

Activity SHALL conceptually flow as:

    Existing Application Event / State
        ↓
    Presentation Event / View Model
        ↓
    TUI Renderer

The presentation representation MAY include:

    ◌ Running
    ✓ Completed
    ⚠ Approval Required
    ✗ Failed

The presentation layer SHALL NOT infer authoritative engineering outcomes from
the rendered glyphs.

Rendering SHALL remain a projection of actual application state.


-------------------------------------------------------------------------------

# 19. Diff Architecture

The TUI SHALL use a presentation-oriented diff renderer.

The underlying repository/session state SHALL remain authoritative.

The renderer SHALL support:

    - small inline diff,
    - collapsed large diff,
    - expandable full diff,
    - session change review.

The diff renderer SHALL NOT become a second repository-state authority.

The review view SHALL consume actual change information.


-------------------------------------------------------------------------------

# 20. Terminal Secondary-Surface Architecture

The following terminal surfaces SHALL remain presentation-level views:

    File Tree
    Review / Changes
    Workflow / Task
    Command Palette

Their implementation SHALL remain within the terminal presentation boundary.

When active, the selected surface SHALL own terminal keyboard focus.

The surface lifecycle is:

    Normal TUI
        ↓
    Open secondary surface
        ↓
    Surface owns focus
        ↓
    User Interaction
        ↓
    Return to Normal TUI

The terminal implementation SHALL preserve the approved TUI composition and
shall not introduce engineering-state ownership into these surfaces.


-------------------------------------------------------------------------------

# 21. Terminal Input and Interruption Architecture

The following semantics SHALL remain distinct:

    Esc

        UI-level closure/cancellation.

    Ctrl+C

        Engineering-operation interruption.

Esc SHALL NOT automatically cancel an Engineering operation.

Ctrl+C SHALL route through the approved interaction/execution boundary.

The frontend SHALL not directly modify ExecutionManager state.


-------------------------------------------------------------------------------

# 22. Terminal Esc Semantics

Esc behavior SHALL be determined by the active terminal interaction surface.

For File Tree:

    Esc
        Return to the main TUI.

For Task / Workflow View:

    Esc
        Return to the main TUI.

For Command Palette:

    Esc
        Close the palette and return to the main TUI.

For Permission:

    Esc
        Cancel the pending permission interaction.

For Review:

    Esc
        Return/back out of the active review interaction according to the
        current review state.

The distinction between:

    closing a navigational surface

and:

    cancelling a pending interaction

SHALL be preserved.

Esc SHALL remain UI-level behavior.

It SHALL NOT be interpreted as engineering-operation interruption.


-------------------------------------------------------------------------------

# 23. CLI Architecture

The CLI SHALL use the same application boundary as the TUI.

The conceptual flow is:

    CLI Arguments / Input
        ↓
    CLI Frontend
        ↓
    InteractionController
        ↓
    ClaireCoderV1
        ↓
    Existing V1 System

Non-interactive mode SHALL remain presentation-oriented.

The CLI SHALL provide:

    structured/log-friendly output
    meaningful exit status
    deterministic formatting where practical

The CLI SHALL preserve all existing authorization boundaries.

The absence of an interactive terminal SHALL NOT automatically authorize
privileged operations.


-------------------------------------------------------------------------------

# 24. CLI / TUI Shared Behavior

The CLI and TUI SHALL share:

    - command semantics,
    - session semantics,
    - mode semantics,
    - application lifecycle semantics,
    - permission semantics,
    - engineering result semantics.

They MAY differ in:

    - presentation,
    - rendering,
    - input mechanics,
    - output formatting.

The architecture SHALL avoid duplicated business logic.


-------------------------------------------------------------------------------

# 25. Terminal Adaptation

The TUI SHALL provide adaptive presentation:

    Full TUI
        Large terminal.

    Compact TUI
        Medium terminal or user preference.

    Minimal TUI
        Small terminal or reduced presentation.

    CI / Non-interactive
        No interactive terminal.

Adaptation SHALL occur in the presentation layer.

It SHALL NOT modify the underlying application behavior.

Terminal graphical mascot support SHALL NOT be a prerequisite for any of these
modes.


-------------------------------------------------------------------------------

# 26. Accessibility and Fallback Architecture

The renderer SHALL provide textual/semantic fallbacks for environments without:

    - color,
    - Unicode glyph support.

Critical state SHALL remain understandable without visual decoration.

This ensures:

    Success
    Failure
    Warning
    Permission Required

remain semantically visible in minimal environments.


-------------------------------------------------------------------------------

# 27. Terminal Framework Decision

This ADR SHALL NOT require a specific TUI framework as an architectural
requirement.

Framework selection SHALL be an implementation decision subject to:

    - compatibility with TUI-DESIGN.md,
    - testability,
    - terminal portability,
    - streaming responsiveness,
    - maintainability,
    - fallback support,
    - minimal architectural coupling.

The selected framework SHALL remain an implementation detail behind the TUI
presentation boundary.


-------------------------------------------------------------------------------

# 28. Provider Independence

The CLI/TUI SHALL NOT import provider-specific SDKs into its core public
contracts.

Model identity SHALL be represented through approved application/model
interfaces.

The frontend MAY display:

    model name
    provider label
    endpoint information where appropriate

but SHALL NOT depend on provider-specific runtime types.


-------------------------------------------------------------------------------

# 29. Testing Architecture

CLI/TUI tests SHALL operate at multiple levels.

## Unit

Test:

    - rendering,
    - input,
    - focus,
    - secondary surfaces,
    - command parsing integration,
    - keyboard shortcuts,
    - Claire text/persona rendering,
    - terminal adaptation.

## Integration

Test:

    - launch,
    - objective submission,
    - streaming,
    - permission,
    - Tool activity,
    - Verification presentation,
    - Workflow presentation,
    - completion,
    - interruption,
    - session commands.

## Boundary Tests

Verify that the CLI/TUI cannot:

    - execute Tools directly,
    - bypass PermissionEngine,
    - mutate Workflow directly,
    - mutate ExecutionManager directly,
    - mutate VerificationEngine directly,
    - import provider SDKs into core contracts.

The complete approved ClaireCoder V1 regression suite SHALL remain green.


-------------------------------------------------------------------------------

# 30. Rejected Architectural Alternatives

## 30.1 TUI as Orchestrator

REJECTED.

The TUI SHALL not coordinate engineering state because this would duplicate
Engineering Engine and Workflow responsibilities.

## 30.2 Separate CLI and TUI Business Logic

REJECTED.

Both frontends SHALL use the same Interaction/Application boundaries.

## 30.3 Direct Tool Calls From TUI

REJECTED.

This would bypass approved execution and permission boundaries.

## 30.4 TUI-Owned Workflow State

REJECTED.

WorkflowManager remains authoritative.

## 30.5 Provider-Coupled Frontend

REJECTED.

The Model Gateway remains provider-independent.

## 30.6 Graphical Mascot Required by Terminal

REJECTED.

The terminal SHALL remain fully functional without terminal image protocols or
graphical mascot rendering.

## 30.7 Permanent Dashboard UI

REJECTED.

The locked terminal design is terminal-first and conversation-first rather than
a permanent multi-pane dashboard.


-------------------------------------------------------------------------------

# 31. Consequences

## Positive

This decision provides:

    - replaceable frontends,
    - consistent CLI/TUI behavior,
    - preservation of V1 architecture,
    - easier testing,
    - terminal adaptability,
    - provider independence,
    - clean separation between terminal and desktop identity,
    - future frontend replacement without core redesign.

The removal of graphical mascot requirements from the terminal eliminates a
terminal-capability dependency while preserving the graphical mascot for the
Desktop frontend.

## Negative

The terminal cannot provide the same graphical mascot experience as the
Desktop frontend.

Some presentation behavior must therefore differ between the two surfaces.

This is intentional.

The presentation difference does not change shared application semantics.

## Neutral

The exact terminal rendering framework remains an implementation decision.


-------------------------------------------------------------------------------

# 32. Implementation Order

The current implementation SHALL proceed from the existing approved baseline.

Historical phases already completed SHALL NOT be reimplemented.

Implementation sequence and order are governed authoritatively by:

    CLI-TUI-DESKTOP-ROADMAP.md

The remaining implementation proceeds according to the current staged roadmap,
whose active sequence is:

    Stage 5
        Terminal Experience Finalization
            ↓
    Stage 6
        CLI Completion
            ↓
    Stage 7
        Multi-Provider Configuration / Credential / Bootstrap
            ↓
    Stage 8
        Desktop Application Foundation
            ↓
    Stage 9
        Desktop Main Experience
            ↓
    Stage 10
        Desktop Secondary Views
            ↓
    Stage 11
        Desktop Interaction Integration
            ↓
    Stage 12
        Desktop UX Completion
            ↓
    Stage 13
        Desktop Security / Credential Integration
            ↓
    Stage 14
        Packaging / Distribution
            ↓
    Stage 15
        Full End-to-End Validation
            ↓
    Stage 16
        Final V1 Audit

The relationship between authorities SHALL be:

    CC-ADR-007
        = CLI/TUI architecture authority

    CLI-TUI-DESKTOP-ROADMAP.md
        = implementation sequence authority

    CC-PRD-012 / CC-ADR-008
        = Desktop architecture authority

Desktop GUI implementation and architecture remain explicitly outside this
ADR's architectural scope and SHALL be governed by:

    CC-PRD-012
    CC-ADR-008


-------------------------------------------------------------------------------

# 33. Relationship With Other Architecture Decisions

## CC-ADR-001

Defines core subsystem boundaries and Engineering Engine responsibilities.

CC-ADR-007 SHALL preserve those boundaries.

## CC-ADR-003

Defines Tool and Skill extension boundaries.

The CLI/TUI SHALL remain outside Tool execution and Skill execution.

## CC-ADR-004

Defines Workflow and Context responsibilities.

The TUI SHALL display but not own them.

## CC-ADR-005

Defines Interaction, Modes, and Commands.

CC-ADR-007 extends the terminal presentation boundary over that interaction
contract.

## CC-ADR-006

Defines Permission and autonomy architecture.

The TUI SHALL present permission interaction without becoming the authority.

## CC-PRD-012 / CC-ADR-008

Define the separate Desktop GUI Interaction Layer and its local application
boundary.

The Desktop architecture SHALL consume the same approved application and
interaction semantics without changing terminal architecture.


-------------------------------------------------------------------------------

# 34. AI Instructions

When implementing CC-ADR-007:

    1. Treat CC-PRD-011 as the authoritative terminal product requirement.
    2. Treat TUI-DESIGN.md as the authoritative terminal UX requirement.
    3. Treat ClaireCoder-TUI-Design-V1.png as the canonical terminal visual
       reference.
    4. Keep CLI/TUI as presentation/input layers.
    5. Use InteractionController as the interaction boundary.
    6. Use ClaireCoderV1 as the application boundary.
    7. Do not create another Engineering Engine.
    8. Do not create another Workflow state machine.
    9. Do not create another Execution state machine.
    10. Do not create another Verification system.
    11. Do not create another Permission system.
    12. Keep Tool execution behind ToolExecutor.
    13. Keep authorization behind PermissionEngine.
    14. Keep provider independence behind ModelGateway.
    15. Treat WorkflowManager as Workflow authority.
    16. Treat ExecutionManager as Execution authority.
    17. Treat VerificationEngine as Verification authority.
    18. Keep Claire presentation-only.
    19. In terminal mode, use Claire text/persona rather than graphical mascot
        rendering.
    20. Preserve the complete documented command surface.
    21. Preserve Esc versus Ctrl+C semantics.
    22. Preserve Full/Compact/Minimal/CI modes.
    23. Keep the TUI responsive and testable.
    24. Prefer public interfaces over private state access.
    25. Do not introduce V2 architecture.
    26. Do not let terminal framework limitations redefine the product
        architecture.
    27. Preserve the locked terminal visual hierarchy.
    28. Use fakes/mocks where external providers are unnecessary for tests.
    29. Preserve the existing V1 regression suite.
    30. Correct project-owned warnings at their source.
    31. Do not introduce terminal graphical mascot dependencies.
    32. Treat CC-PRD-012 and CC-ADR-008 as the authority for Desktop GUI
        requirements.
    33. Treat this ADR as the authoritative architecture decision for the
        ClaireCoder CLI/TUI implementation unless explicitly superseded.


-------------------------------------------------------------------------------

# 35. Decision Status

This ADR is currently:

    DRAFT

It SHALL become final only after:

    CC-PRD-011 V2.0
        +
    CC-ADR-007 V2.0
        ↓
    Independent review
        ↓
    Documentation approval

Only after approval SHALL the next implementation authorization be issued.


###############################################################################

END OF CC-ADR-007

###############################################################################