###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                     Product Requirements Document
#
# Document Number : CC-PRD-011
# Title           : ClaireCoder CLI & TUI System
# Version         : 2.0.0
# Status          : FINAL
#
###############################################################################

# 1. Executive Summary

The ClaireCoder CLI & TUI System provides the terminal-based developer
interaction surface for the approved ClaireCoder V1 application.

The system SHALL provide two complementary terminal interaction surfaces:

    CLI
        Non-interactive, script-friendly, CI-compatible operation.

    TUI
        Interactive, terminal-native developer experience.

The CLI and TUI SHALL operate above the already-approved ClaireCoder V1
application architecture.

The interface SHALL preserve the distinction between:

    USER INTERACTION

        Input, presentation, commands, confirmations, navigation,
        terminal rendering, and terminal-specific interaction behavior.

    ENGINEERING SYSTEM

        Engineering orchestration, workflow, execution, verification,
        permissions, context, tools, skills, sessions, and model interaction.

The CLI/TUI SHALL NOT become another engineering orchestration layer.

The CLI/TUI SHALL remain independent from specific model providers.

The terminal visual and interaction design SHALL remain governed by:

    TUI-DESIGN.md

and the locked ClaireCoder terminal reference design, except where this PRD
explicitly establishes terminal-specific behavior that supersedes an obsolete
mascot-related requirement from the previous revision.

The canonical graphical Claire mascot is NOT a terminal requirement in V2.0.

The desktop graphical interface is defined separately by:

    CC-PRD-012
    CC-ADR-008
    DESKTOP-DESIGN.md

-------------------------------------------------------------------------------

# 2. Product Goal

The goal of CC-PRD-011 is to provide a polished terminal-native engineering
agent experience over the approved ClaireCoder V1 application.

ClaireCoder SHALL feel familiar to developers who use terminal-native coding
agents while retaining its own identity through:

    - ClaireCoder branding and wordmark,
    - Claire text persona,
    - transparent agent activity,
    - explicit permission interaction,
    - workflow-aware presentation,
    - contextual diffs,
    - terminal-first interaction,
    - restrained terminal visual language.

The terminal implementation SHALL NOT attempt to reproduce graphical desktop
mascot rendering.

The terminal Claire identity SHALL be represented through:

    - CLAIRECODER wordmark / branding,
    - terminal visual language,
    - "Claire:" text/persona presentation.

The intended architecture remains:

    Developer
        ↓
    CLI / TUI
        ↓
    Interaction Layer
        ↓
    ClaireCoderV1
        ↓
    Existing V1 Architecture

The addition or revision of the CLI/TUI SHALL NOT require replacing or
duplicating approved V1 subsystems.

-------------------------------------------------------------------------------

# 3. Problem Statement

ClaireCoder V1 contains the engineering architecture required to understand
objectives, plan work, execute Tasks, apply permissions, verify results,
preserve context, and maintain sessions.

However, that architecture is not itself a complete developer-facing terminal
product.

A developer needs a coherent terminal interface through which they can:

    - start ClaireCoder,
    - select or resume a session,
    - submit engineering objectives,
    - observe agent activity,
    - inspect Tool activity,
    - respond to permission requests,
    - inspect changes,
    - inspect Workflow state,
    - pause or resume where supported,
    - cancel active operations,
    - inspect status,
    - review results,
    - continue working.

The CLI/TUI therefore provides the presentation and interaction boundary for
the approved ClaireCoder V1 application.

The terminal SHALL solve this problem using terminal-native rendering rather
than trying to become a graphical desktop environment.

-------------------------------------------------------------------------------

# 4. Scope

## 4.1 In Scope

This PRD covers:

    - Interactive TUI.
    - Non-interactive CLI.
    - CLI invocation behavior.
    - Prompt/input interaction.
    - Command interaction.
    - Keyboard interaction.
    - Streaming agent output.
    - Agent activity rendering.
    - Tool activity rendering.
    - Permission confirmation presentation.
    - Inline diff rendering.
    - Session/status presentation.
    - Claire text/persona presentation.
    - Startup/loading presentation.
    - File tree presentation.
    - Review/change presentation.
    - Workflow/task presentation.
    - Command palette.
    - TUI input states.
    - Terminal-size adaptation.
    - Accessibility and fallback behavior.
    - CI/non-interactive presentation.
    - CLI/TUI integration with the Interaction Layer.
    - CLI/TUI integration with ClaireCoderV1.
    - CLI/TUI testing.
    - CLI/TUI architectural boundary validation.

## 4.2 Out of Scope

This PRD SHALL NOT define:

    - a replacement Engineering Engine,
    - a replacement Workflow system,
    - a replacement Execution system,
    - a replacement Verification system,
    - a replacement Permission Engine,
    - a replacement Model Gateway,
    - direct Tool execution,
    - provider-specific model architecture,
    - distributed persistence,
    - a graphical desktop application,
    - a web dashboard,
    - an IDE replacement,
    - speculative V2 autonomous behavior,
    - a remote extension marketplace,
    - desktop graphical mascot rendering,
    - desktop animation systems.

Desktop GUI requirements are owned by:

    CC-PRD-012

-------------------------------------------------------------------------------

# 5. Core Distinction

ClaireCoder SHALL preserve the distinction between:

    CLI / TUI

        Terminal presentation and interaction surfaces.

and:

    ClaireCoder V1

        Application boundary coordinating the approved engineering system.

The CLI/TUI MAY:

    - display state,
    - accept input,
    - present commands,
    - present permissions,
    - display changes,
    - display Workflow progress,
    - render Tool activity,
    - render Verification results,
    - present Claire as a text/persona identity.

The CLI/TUI SHALL NOT:

    - decide authorization,
    - execute Tools,
    - own Workflow state,
    - own Execution State,
    - own Verification state,
    - own model/provider logic,
    - replace the Engineering Engine,
    - mutate internal subsystem state directly.

-------------------------------------------------------------------------------

# 6. Design Philosophy

ClaireCoder CLI/TUI SHALL follow these principles.

## 6.1 Terminal-First

The interface SHALL remain native to the terminal.

It SHALL NOT become an IDE clone.

It SHALL NOT require graphical terminal image support for baseline operation.

## 6.2 Conversation-First

The primary interactive experience SHALL use a continuous scrollback-oriented
conversation.

Agent activity SHALL appear in context rather than requiring a permanent
dashboard.

## 6.3 Transparent Agent Activity

The developer SHOULD be able to see:

    - Tool activity,
    - file reads,
    - edits,
    - tests,
    - Verification,
    - failures,
    - approvals,
    - completion.

## 6.4 Explicit Permissions

Privileged operations SHALL be presented through clear confirmation UI.

Permission decisions SHALL remain owned by the Permission Engine.

## 6.5 Contextual Diffs

Small changes SHOULD appear inline.

Large changes SHOULD collapse to summaries and remain expandable.

## 6.6 Workflow-Aware, Not Workflow-Owning

The CLI/TUI MAY display:

    - current Workflow,
    - current Task,
    - progress,
    - completion state.

The CLI/TUI SHALL NOT become the authority for any of those states.

## 6.7 Minimal Chrome

Persistent information SHALL remain useful but SHALL NOT dominate the
transcript.

## 6.8 Optional Advanced Views

Advanced views SHALL be opt-in.

Examples:

    - file tree,
    - Workflow/task view,
    - review/change view,
    - command palette.

## 6.9 Claire Is Persona, Not Logic

Claire remains presentation-only.

In the terminal surface, Claire SHALL be represented primarily through:

    Claire:
        <message>

and the surrounding ClaireCoder terminal visual language.

The terminal SHALL NOT require graphical Claire artwork.

## 6.10 Terminal Adaptation

The system SHALL adapt to terminal size and capability.

The default experience SHOULD remain visually faithful to the locked terminal
reference.

When terminal capabilities are limited, presentation SHALL degrade while
preserving semantic content.

-------------------------------------------------------------------------------

# 7. Architectural Position

The intended presentation path is:

    CLI / TUI
        ↓
    InteractionController
        ↓
    ClaireCoderV1
        ↓
    Existing V1 Subsystems

The CLI/TUI SHALL use public application and interaction boundaries.

The CLI/TUI SHALL NOT access:

    - private session dictionaries,
    - private Workflow dictionaries,
    - private Execution dictionaries,
    - private Verification dictionaries,
    - provider SDKs,
    - Tool private execution methods,
    - Permission policy internals.

The CLI/TUI SHALL remain replaceable without redesigning the approved V1
engineering architecture.

-------------------------------------------------------------------------------

# 8. Ownership Boundaries

## 8.1 CLI

The CLI owns:

    - command-line argument handling,
    - non-interactive input,
    - standard output formatting,
    - standard error formatting,
    - exit codes,
    - scripting-oriented invocation.

## 8.2 TUI

The TUI owns:

    - rendering,
    - keyboard handling,
    - input focus,
    - terminal presentation,
    - terminal-specific visual adaptation,
    - scrollback presentation,
    - UI-level interaction feedback.

## 8.3 Interaction Layer

The Interaction Layer owns:

    - interaction commands,
    - command parsing,
    - command routing,
    - interaction modes,
    - user-facing command semantics.

## 8.4 ClaireCoderV1

ClaireCoderV1 owns the approved top-level application lifecycle.

The CLI/TUI SHALL consume that boundary rather than replacing it.

-------------------------------------------------------------------------------

# 9. CLI Architecture

The CLI SHALL provide a non-interactive frontend to ClaireCoder.

The conceptual relationship is:

    Command Line
        ↓
    CLI
        ↓
    Interaction Layer
        ↓
    ClaireCoder V1
        ↓
    Existing V1 System

The CLI SHOULD support:

    - interactive launch,
    - objective supplied on invocation,
    - session selection,
    - session resumption,
    - model selection,
    - mode selection,
    - status inspection,
    - non-interactive execution,
    - CI-friendly execution.

The exact argument parser and packaging mechanism SHALL remain implementation
decisions until launcher/configuration design is finalized.

-------------------------------------------------------------------------------

# 10. Interactive Launch

The V1 product SHALL provide a launcher-compatible interactive entry point.

The intended user experience is conceptually:

    clairecoder

The system SHOULD also support:

    python -m clairecoder

where practical.

The final launcher/bootstrap behavior SHALL be defined during the later
provider/configuration/launcher stage.

-------------------------------------------------------------------------------

# 11. CLI Invocation

The CLI SHOULD support direct objective submission.

Example:

    clairecoder "Fix the failing tests in this repository."

The CLI MAY support:

    - explicit project selection,
    - session selection,
    - model selection,
    - mode selection,
    - configuration selection.

The exact option syntax SHALL be determined during implementation while
preserving the underlying Interaction contract.

-------------------------------------------------------------------------------

# 12. Non-Interactive / CI Mode

The CLI SHALL support a non-interactive mode suitable for:

    - scripts,
    - CI,
    - automated environments,
    - redirected input/output.

Non-interactive mode SHALL:

    - avoid interactive confirmation surfaces,
    - avoid graphical mascot rendering,
    - avoid interactive overlays,
    - use structured/log-friendly output,
    - provide meaningful exit codes,
    - preserve all underlying authorization boundaries.

The CLI SHALL NOT silently bypass the Permission Engine merely because the
terminal is non-interactive.

Unresolved confirmation behavior SHALL remain aligned with the approved
Permission architecture.

-------------------------------------------------------------------------------

# 13. Command System

The intended V1 command surface SHALL remain divided into two categories.

## 13.1 Application / Interaction Commands

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

These commands SHALL route through the existing Interaction Layer.

## 13.2 UI / Presentation Commands

    /tree
    /review
    /compact

These commands MAY operate directly within the TUI presentation layer when
they do not require engineering-state ownership.

The command surface MAY be implemented incrementally.

Documented command names and ownership SHALL remain part of the V1 interaction
contract.

-------------------------------------------------------------------------------

# 14. Keyboard Interaction

The TUI SHALL support:

    Ctrl+C
        Interrupt the active engineering operation through the approved
        Interaction / Execution boundary.

    Ctrl+T
        Open the File Tree view.

    Ctrl+R
        Open the session Change Review view.

    Ctrl+P
        Open the Workflow / Task view.

    ?
        Open the Command Palette / Help view.

    Enter
        Submit prompt in normal input.
        Activate the selected item when the active UI surface owns focus.

    Esc
        Perform UI-level close/cancel behavior according to the active
        interaction surface.

Esc and Ctrl+C SHALL NOT be treated as equivalent operations.

    Esc
        UI-level behavior.

    Ctrl+C
        Engineering-operation interruption.

-------------------------------------------------------------------------------

# 15. TUI Input States

The TUI SHALL support these input/presentation states:

    NORMAL

        The prompt accepts normal user input.

    STREAMING

        Agent output is streaming.

    CONFIRMATION

        Permission confirmation owns keyboard focus.

    OVERLAY

        A terminal secondary view owns keyboard focus.

    INTERRUPTED

        The active operation has been interrupted and control returns to the
        interaction surface.

    EXITING

        The TUI is shutting down cleanly.

These states SHALL remain UI/input states only.

They SHALL NOT become another:

    Workflow state machine,
    Execution state machine,
    Verification state machine,
    Permission state machine.

-------------------------------------------------------------------------------

# 16. Main TUI Layout

The default interactive view SHALL remain the locked ClaireCoder terminal
composition.

The primary composition SHALL include:

    - ClaireCoder identity/header,
    - repository/session/model/mode information,
    - current Task/progress information,
    - context usage where available,
    - agent activity,
    - Tool activity,
    - Verification results,
    - inline diffs,
    - Claire text/persona messages,
    - prompt,
    - keyboard/help hints.

The prompt SHALL remain visually anchored at the bottom during normal
streaming output.

The current terminal visual hierarchy SHALL be preserved.

The terminal SHALL NOT allocate a dedicated graphical mascot region.

-------------------------------------------------------------------------------

# 17. Persistent Status

The TUI SHOULD expose:

    - working directory,
    - selected model,
    - current mode,
    - session identity,
    - current Task / Task progress,
    - context usage.

Provider-dependent information such as estimated cost MAY be displayed when
available.

Cost information SHALL NOT be required for local or otherwise non-metered
providers.

-------------------------------------------------------------------------------

# 18. Agent Activity Blocks

Agent activity SHALL use compact semantic states.

The TUI SHOULD support states such as:

    ◌ Running
    ✓ Completed
    ⚠ Approval Required
    ✗ Failed

Examples:

    > ✓ Reading src/decoder.py
    > ● Editing src/router.py
    > ◌ Running pytest tests/decoder/
    > ✓ Verification passed
    > ✗ 3 tests failed

Activity blocks SHOULD be expandable and collapsible.

Long output SHOULD collapse to concise summaries.

The TUI SHALL NOT determine engineering success from visual status alone.

The displayed state SHALL originate from the approved application architecture.

-------------------------------------------------------------------------------

# 19. Inline Diff Rendering

Small diffs SHOULD appear inline where changes occur.

Large diffs SHOULD collapse automatically.

Example:

    src/decoder.py   +18 -4

The developer SHALL be able to expand the summary and inspect the full diff.

The TUI SHALL display change information obtained from the approved underlying
application/repository state.

It SHALL NOT fabricate a separate change-tracking authority.

-------------------------------------------------------------------------------

# 20. Permission / Confirmation UI

Privileged operations SHALL use a dedicated confirmation surface.

The intended interaction SHALL support:

    [y] yes
    [n] no
    [a] yes, always this session
    [d] diff
    Esc cancel

The TUI SHALL display the Permission Engine's request/decision context.

The TUI SHALL NOT:

    - make ALLOW / ASK / DENY decisions,
    - modify authorization policy,
    - bypass the Permission Engine,
    - execute the requested Tool itself.

-------------------------------------------------------------------------------

# 21. Claire Terminal Identity

The terminal SHALL NOT render the canonical graphical Claire mascot.

The terminal identity SHALL instead use:

    - CLAIRECODER wordmark / branding,
    - ClaireCoder color language,
    - Claire text/persona messages.

Claire messages SHALL use a consistent presentation such as:

    Claire:
        Streaming decode support has been added.
        All tests are passing.
        What would you like to work on next?

The exact text styling SHALL follow TUI-DESIGN.md.

The terminal SHALL NOT require:

    - mascot sprite files,
    - graphical mascot states,
    - terminal image protocols,
    - half-block mascot rendering,
    - Unicode character reconstruction of Claire.

This terminal decision does NOT remove the canonical Claire mascot from the
Claire ecosystem.

The graphical mascot remains a desktop-interface concern defined by
CC-PRD-012.

-------------------------------------------------------------------------------

# 22. Terminal Startup / Loading Screen

The terminal SHALL provide a short branded startup sequence.

The startup SHALL use the CLAIRECODER wordmark rather than graphical Claire
artwork.

The startup MAY represent:

    CLAIRECODER

    Engineering. Automated.

    > Loading configuration
    > Connecting model gateway
    > Registering tools
    > Preparing workspace
    > Loading skills
    > Starting session

Status indicators MAY be shown as appropriate.

The startup SHOULD be:

    - brief,
    - visually consistent with the locked terminal design,
    - skippable where practical.

The startup SHALL NOT become a second application initialization authority.

-------------------------------------------------------------------------------

# 23. Optional File Tree

Ctrl+T SHALL open the File Tree view.

The file tree MAY display:

    - repository hierarchy,
    - modified files,
    - newly created files,
    - unchanged files.

Suggested markers:

    M
        Modified during session.

    +
        Newly created.

    plain
        Untouched.

The file tree SHALL remain a presentation surface.

-------------------------------------------------------------------------------

# 24. Review / Changes View

Ctrl+R SHALL open the session change review.

The review view SHOULD display:

    - files changed,
    - insertion/deletion summary,
    - newly created files,
    - selectable files,
    - full diff inspection.

The review view MAY later support commit interaction, but commit functionality
is secondary to the baseline terminal interface.

The review view SHALL remain presentation-oriented.

-------------------------------------------------------------------------------

# 25. Task / Workflow View

Ctrl+P SHALL open the Workflow / Task view.

The view MAY show:

    - Workflow stages,
    - current Task,
    - Task progress,
    - objective summary,
    - completion state,
    - validation state.

The view SHALL be read-oriented.

The TUI SHALL display Workflow state from the Workflow subsystem.

The TUI SHALL NOT maintain a duplicate Workflow state machine.

-------------------------------------------------------------------------------

# 26. Command Palette

? SHALL open the command palette/help view.

The command palette SHALL distinguish:

    APPLICATION / INTERACTION

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

    UI / PRESENTATION

        /tree
        /review
        /compact

Application commands SHALL route through the Interaction Layer.

Presentation commands SHALL remain TUI concerns.

-------------------------------------------------------------------------------

# 27. TUI Surface and Esc Semantics

The terminal SHALL preserve clear UI-level behavior for secondary surfaces.

File Tree:

    Esc
        Close the active File Tree presentation and return to the main TUI.

Task / Workflow View:

    Esc
        Close the active Task view and return to the main TUI.

Command Palette:

    Esc
        Close the palette and return to the main TUI.

Permission:

    Esc
        Cancel the pending permission interaction.

Review:

    Esc
        Return/back out of the active review interaction according to the
        current review state.

The terminal SHALL distinguish:

    informational/navigation closure
        from
    pending interaction cancellation.

Esc SHALL remain a UI-level action and SHALL NOT be treated as engineering
operation interruption.

-------------------------------------------------------------------------------

# 28. Modes of Operation

## 28.1 Full TUI

The default terminal experience SHALL include:

    - CLAIRECODER identity,
    - transcript,
    - activity rendering,
    - advanced views,
    - permission confirmations,
    - status information,
    - Claire text persona.

The Full TUI SHALL NOT require graphical mascot rendering.

## 28.2 Compact TUI

The interface SHALL:

    - reduce verbose activity output,
    - reduce optional visual chrome,
    - preserve core interaction,
    - preserve Claire text/persona identity.

## 28.3 Minimal TUI

The interface SHALL:

    - remove optional panes,
    - retain transcript,
    - retain prompt,
    - retain commands,
    - retain permission interaction,
    - retain Claire text persona where appropriate.

## 28.4 Non-Interactive / CI

The interface SHALL:

    - disable interactive overlays,
    - disable interactive confirmation UI,
    - produce structured/log-friendly output,
    - preserve engineering authorization boundaries.

-------------------------------------------------------------------------------

# 29. Visual Language

The implementation SHALL follow the locked terminal visual reference.

The primary visual language SHALL be:

    Cyan / Teal
        ClaireCoder primary interface and activity.

    Pink / Magenta
        Claire identity and secondary accent.

    Green
        Added content and successful operations.

    Red
        Removed content and failures.

    Yellow
        Warnings and pending confirmation.

    Dim Grey
        Secondary/collapsed content.

The visual language SHALL remain:

    - dark-terminal-first,
    - restrained,
    - sparse,
    - readable.

Semantic meaning SHALL NOT depend solely on color.

-------------------------------------------------------------------------------

# 30. Terminal Adaptation

The TUI SHALL adapt according to terminal capability and size.

The intended hierarchy is:

    Large terminal
        ↓
    Full TUI

    Medium terminal
        ↓
    Compact TUI

    Small terminal
        ↓
    Minimal TUI

    Non-interactive environment
        ↓
    CI mode

The interface SHALL degrade gracefully.

Baseline functionality SHALL NOT require terminal-specific graphics protocols.

-------------------------------------------------------------------------------

# 31. Accessibility and Fallback

The interface SHALL provide meaningful fallback behavior when:

    - color is unavailable,
    - Unicode glyphs are unavailable,
    - terminal dimensions are limited.

Critical state SHALL remain understandable through text and semantic
presentation.

The terminal SHALL NOT rely exclusively on:

    - color,
    - emoji,
    - terminal graphics,
    - mascot imagery

for critical information.

-------------------------------------------------------------------------------

# 32. CLI and TUI Relationship

The CLI and TUI SHALL share the same approved application and Interaction
boundaries.

Conceptually:

    CLI
       │
       ├──────────────┐
       │              │
       ▼              ▼
    Interaction Layer
       ▲              ▲
       │              │
       └──────────────┘
              TUI
               ↓
         ClaireCoder V1
               ↓
         Existing V1 System

The CLI SHALL NOT duplicate TUI business logic.

The TUI SHALL NOT duplicate CLI business logic.

Shared behavior SHOULD remain in the existing Interaction/Application
boundaries.

-------------------------------------------------------------------------------

# 33. Testing Strategy

## 33.1 CLI Tests

The CLI test suite SHALL cover:

    - startup,
    - argument handling,
    - command routing,
    - session selection,
    - session resumption,
    - model selection,
    - mode selection,
    - non-interactive output,
    - exit codes,
    - CI behavior.

## 33.2 TUI Tests

The TUI test suite SHALL cover:

    - rendering,
    - prompt handling,
    - input focus,
    - input states,
    - activity rendering,
    - diff rendering,
    - permission presentation,
    - Claire text/persona rendering,
    - file tree,
    - review view,
    - Workflow view,
    - command palette,
    - keyboard shortcuts,
    - terminal adaptation,
    - terminal fallback modes.

Tests SHALL NOT require graphical mascot assets or terminal image protocols.

## 33.3 Integration Tests

The system SHALL validate at minimum:

    Launch
        ↓
    Developer input
        ↓
    Engineering Objective
        ↓
    Visible agent activity
        ↓
    Permission request where required
        ↓
    Tool/Task execution
        ↓
    Verification
        ↓
    Completion

The tests SHALL verify that the CLI/TUI does not bypass the approved
architecture.

-------------------------------------------------------------------------------

# 34. Acceptance Criteria

CC-PRD-011 SHALL be considered successfully implemented when:

## AC-001 — Interactive Startup

A developer can start ClaireCoder through the supported interactive terminal
interface.

## AC-002 — Prompt Input

A developer can submit a natural-language engineering objective.

## AC-003 — Streaming

Agent activity is displayed progressively in the transcript.

## AC-004 — Permission Presentation

Permission requests are presented clearly and routed through the existing
Permission Engine boundary.

## AC-005 — Tool Visibility

Tool activity and Tool results are visible in the interface.

## AC-006 — Diff Visibility

Changes can be inspected inline or through the review surface.

## AC-007 — Claire Terminal Identity

The terminal presents the Claire persona and ClaireCoder wordmark without
requiring graphical mascot rendering.

## AC-008 — Workflow Visibility

Current Workflow/Task information is inspectable without a second Workflow
state machine.

## AC-009 — Session Commands

Session commands are available through the Interaction Layer.

## AC-010 — Application Commands

The documented application command surface is available.

## AC-011 — UI Commands

UI commands such as `/tree`, `/review`, and `/compact` operate without
mutating engineering state directly.

## AC-012 — Interruption

Ctrl+C interrupts an active engineering operation through the approved
boundary.

## AC-013 — UI Cancellation

Esc performs UI-level close/cancel behavior without being treated as
engineering-operation cancellation.

## AC-014 — Terminal Adaptation

The TUI adapts appropriately to terminal capability and size.

## AC-015 — Non-Interactive Operation

The CLI can operate without an interactive terminal.

## AC-016 — Architecture Isolation

The CLI/TUI performs:

    no direct Tool execution,
    no Permission bypass,
    no direct Workflow mutation,
    no direct Execution mutation,
    no direct Verification mutation,
    no provider-specific core coupling.

## AC-017 — Regression Safety

The CLI/TUI implementation passes its dedicated tests and preserves the
existing approved ClaireCoder V1 regression suite.

-------------------------------------------------------------------------------

# 35. Non-Functional Requirements

## NFR-001 — Responsiveness

The TUI SHOULD remain responsive while agent activity streams.

## NFR-002 — Long Sessions

Long transcripts SHALL not create unbounded rendering overhead.

## NFR-003 — Output Control

Large Tool outputs and diffs SHOULD collapse automatically.

## NFR-004 — Terminal Compatibility

The system SHALL support Full / Compact / Minimal / CI presentation modes.

## NFR-005 — CI Determinism

Non-interactive output SHOULD remain deterministic and suitable for logs.

## NFR-006 — Accessibility

Critical semantic information SHALL remain understandable without color,
Unicode-specific glyphs, or graphical mascot rendering.

## NFR-007 — Maintainability

Presentation components SHALL remain separated from engineering logic.

## NFR-008 — Testability

CLI/TUI components SHOULD be testable without requiring real model
credentials.

-------------------------------------------------------------------------------

# 36. Deliverables

Implementation of CC-PRD-011 SHALL ultimately produce:

    1. CLI entry point.
    2. Interactive TUI.
    3. Non-interactive CLI mode.
    4. Prompt/input handling.
    5. Command system integration.
    6. Streaming presentation.
    7. Agent activity renderer.
    8. Tool activity renderer.
    9. Permission confirmation surface.
    10. Inline diff renderer.
    11. Claire text/persona identity layer.
    12. CLAIRECODER startup/loading screen.
    13. File tree view.
    14. Review/change view.
    15. Workflow/task view.
    16. Command palette.
    17. Keyboard interaction.
    18. Terminal-size adaptation.
    19. Accessibility/fallback behavior.
    20. Dedicated CLI/TUI tests.
    21. Integration tests.
    22. Updated terminal user documentation.

Graphical desktop requirements are NOT deliverables of CC-PRD-011.

-------------------------------------------------------------------------------

# 37. Implementation Constraints

The implementation SHALL NOT:

    - create another Engineering Engine,
    - create another Workflow state machine,
    - create another Execution state machine,
    - create another Verification system,
    - create another Permission policy system,
    - directly execute Tools,
    - bypass ToolExecutor,
    - make Permission decisions in the UI,
    - mutate private subsystem state,
    - import provider-specific SDKs into core CLI/TUI contracts,
    - replace ClaireCoderV1,
    - require real external model credentials for unit tests,
    - introduce speculative distributed infrastructure,
    - require terminal image protocols,
    - reintroduce graphical mascot rendering into the terminal.

The CLI/TUI SHALL consume approved public interfaces.

-------------------------------------------------------------------------------

# 38. Relationship With Other PRDs

## CC-PRD-001

Provides the Engineering Engine boundary consumed by the CLI/TUI.

## CC-PRD-002

Provides Model Gateway abstraction.

The CLI/TUI SHALL display model information through public application contracts
and SHALL NOT depend on provider-specific implementation.

## CC-PRD-003

Provides Tool and Skill capabilities.

The TUI SHALL display their activity without executing them directly.

## CC-PRD-004

Provides Workflow and Planning.

The TUI SHALL display Workflow state without owning it.

## CC-PRD-005

Provides Interaction, Modes, and Commands.

The CLI/TUI SHALL consume the Interaction Layer defined there.

## CC-PRD-006

Provides Permission and Autonomy architecture.

The TUI SHALL present permission interaction without becoming the authority.

## CC-PRD-007

Provides Execution State and Recovery.

The TUI SHALL display execution state and interruption behavior without owning
the Execution subsystem.

## CC-PRD-008

Provides Context and Memory boundaries.

The TUI MAY display appropriate context information but SHALL NOT mutate
EngineeringContext.

## CC-PRD-009

Provides Verification.

The TUI SHALL display Verification results without becoming the evaluator.

## CC-PRD-010

Provides final V1 integration.

The CLI/TUI SHALL operate over the approved ClaireCoder V1 application
boundary.

## CC-PRD-012

Defines the separate graphical Desktop GUI Interaction Layer.

CC-PRD-011 SHALL NOT absorb Desktop GUI requirements.

-------------------------------------------------------------------------------

# 39. Current Implementation Baseline

CC-PRD-011 SHALL be implemented against the current approved ClaireCoder V1
baseline.

Historical implementation order SHALL NOT be treated as a requirement to
rebuild already-completed stages.

Remaining implementation shall proceed from the current approved state and
shall preserve the documented architecture.

-------------------------------------------------------------------------------

# 40. Verification Strategy

## Unit Tests

Test:

    - rendering components,
    - prompt state,
    - input states,
    - command dispatch,
    - keyboard handling,
    - activity rendering,
    - diff rendering,
    - Claire text/persona rendering,
    - terminal adaptation.

## Interaction Tests

Test:

    - application commands,
    - UI commands,
    - mode interaction,
    - session interaction,
    - pause/resume/cancel interaction,
    - permission interaction.

## Integration Tests

Test:

    - startup,
    - objective submission,
    - streaming,
    - permission,
    - Tool visibility,
    - Verification visibility,
    - Workflow visibility,
    - completion,
    - failure display,
    - interruption,
    - session operations.

## Regression Tests

The complete approved ClaireCoder V1 test suite SHALL continue to pass.

Project-owned warnings SHALL be corrected rather than broadly suppressed.

-------------------------------------------------------------------------------

# 41. Out-of-Scope Implementation Decisions

This PRD SHALL NOT prematurely decide:

    - exact TUI framework,
    - exact terminal rendering library,
    - exact CLI parser library,
    - exact widget implementation,
    - exact configuration-file format,
    - exact packaging implementation.

Terminal graphical mascot protocols are explicitly unnecessary for the baseline
terminal product.

Desktop rendering technology and desktop IPC transport are defined separately
by:

    CC-PRD-012
    CC-ADR-008

-------------------------------------------------------------------------------

# 42. Success Definition

ClaireCoder V1 satisfies CC-PRD-011 when a developer can:

    launch ClaireCoder
        ↓
    enter an engineering objective
        ↓
    observe ClaireCoder activity
        ↓
    respond to required permission prompts
        ↓
    inspect changes and Workflow progress
        ↓
    observe execution and Verification results
        ↓
    complete or interrupt the operation
        ↓
    continue using the same application/session interface

while all existing V1 architectural boundaries remain intact.

The terminal experience SHALL feel like a coherent terminal-native engineering
agent rather than a collection of disconnected subsystem interfaces.

-------------------------------------------------------------------------------

# 43. AI Instructions

When implementing CC-PRD-011:

    1. Treat TUI-DESIGN.md as the authoritative terminal UX reference.
    2. Treat ClaireCoder-TUI-Design-V1.png as the canonical terminal visual
       reference.
    3. Keep CLI and TUI as presentation/input layers.
    4. Use InteractionController as the interaction boundary.
    5. Use ClaireCoderV1 as the application boundary.
    6. Do not create another Engineering Engine.
    7. Do not create another Workflow state machine.
    8. Do not create another Execution State machine.
    9. Do not create another Verification engine.
    10. Do not create another Permission system.
    11. Keep Tools behind ToolExecutor.
    12. Keep authorization behind PermissionEngine.
    13. Keep provider abstraction behind ModelGateway.
    14. Keep Skills declarative.
    15. Keep Context immutable.
    16. Keep Workflow state owned by WorkflowManager.
    17. Keep Execution state owned by ExecutionManager.
    18. Keep Verification owned by VerificationEngine.
    19. Treat Claire as presentation-only.
    20. In terminal mode, represent Claire through text/persona and ClaireCoder
        branding, not graphical mascot rendering.
    21. Preserve the complete documented command surface.
    22. Implement commands incrementally without changing their ownership.
    23. Preserve `/pause`, `/resume`, and `/cancel`.
    24. Keep Esc as UI-level behavior and Ctrl+C as engineering interruption.
    25. Preserve Full/Compact/Minimal/CI terminal modes.
    26. Keep semantic meaning independent of color.
    27. Use mocks/fakes for UI tests where real providers are unnecessary.
    28. Preserve the existing V1 regression suite.
    29. Correct project-owned warnings at their source.
    30. Do not introduce V2 architecture into the terminal frontend.
    31. Do not silently change the locked terminal visual hierarchy.
    32. Do not introduce terminal graphical mascot dependencies.
    33. Treat CC-PRD-012 as the authority for Desktop GUI requirements.
    34. Treat this PRD as the authoritative product requirement for the
        ClaireCoder CLI & TUI System unless explicitly superseded.

-------------------------------------------------------------------------------

# 44. V1 Design Lock

CC-PRD-011 defines the implementation contract for the ClaireCoder V1 CLI/TUI.

The visual and interaction reference is:

    TUI-DESIGN.md

and:

    ClaireCoder-TUI-Design-V1.png

The CLI/TUI SHALL preserve:

    - terminal-first interaction,
    - conversation-first layout,
    - transparent agent activity,
    - explicit permission interaction,
    - contextual diffs,
    - Claire text/persona identity,
    - optional advanced views,
    - responsive terminal adaptation,
    - approved architecture boundaries.

The terminal mascot removal is an intentional product decision in this
revision, not a visual redesign of the approved terminal composition.

The graphical Claire mascot belongs to the Desktop frontend defined by
CC-PRD-012.

The product requirements, command ownership, architectural ownership, and
terminal visual/interaction intent SHALL remain stable unless this PRD is
explicitly superseded.

###############################################################################

END OF CC-PRD-011
###############################################################################