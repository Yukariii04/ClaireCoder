###############################################################################

#                           THE CLAIRE PROJECT
#
#                     Product Requirements Document
#
# Document Number : CC-PRD-012
# Title           : ClaireCoder Desktop GUI Interaction Layer
# Version         : 1.0.0
# Status          : FINAL

###############################################################################


# 1. Executive Summary

The ClaireCoder Desktop GUI Interaction Layer provides a graphical desktop
frontend for the approved ClaireCoder V1 application.

The Desktop GUI SHALL be an additional frontend to the same ClaireCoder
application and Interaction boundaries already consumed by the CLI/TUI.

The Desktop GUI SHALL NOT replace:

    - Engineering Engine,
    - Workflow system,
    - Execution system,
    - Verification system,
    - Permission Engine,
    - Model Gateway,
    - Context Engine,
    - Tool system,
    - Skill system,
    - Interaction semantics.

The intended architectural relationship is:

    Desktop GUI
        ↓
    Desktop Interaction Adapter
        ↓
    Local Application / IPC Boundary
        ↓
    ClaireCoderV1
        ↓
    Existing V1 Architecture

The Desktop GUI SHALL provide a rich graphical presentation of the same
engineering behavior exposed by the terminal frontend.

The Desktop GUI SHALL use the canonical Claire graphical identity, including
the supplied Claire artwork and all defined mascot states.

The Desktop GUI SHALL reproduce the locked desktop reference design faithfully
rather than creating an unrelated graphical interpretation.


-------------------------------------------------------------------------------

# 2. Product Goal

The goal of CC-PRD-012 is to provide a polished graphical ClaireCoder
experience for developers who prefer a desktop application while preserving
the exact ClaireCoder application architecture.

The Desktop GUI SHALL provide:

    - branded startup experience,
    - engineering activity streaming,
    - graphical Claire identity,
    - permission interaction,
    - file exploration,
    - change review,
    - workflow/task inspection,
    - command palette,
    - prompt/input,
    - session visibility,
    - responsive manual resizing,
    - direct interaction through mouse and keyboard.

The Desktop GUI SHALL feel like a native ClaireCoder application rather than a
web dashboard placed around the Engineering Engine.

The visual authority SHALL be:

    DESKTOP-DESIGN.md

and the locked desktop reference artwork.


-------------------------------------------------------------------------------

# 3. Problem Statement

ClaireCoder V1 already contains the engineering architecture necessary to:

    - understand objectives,
    - plan work,
    - execute Tasks,
    - apply permissions,
    - verify results,
    - preserve context,
    - maintain sessions,
    - expose model interaction,
    - execute Tools.

The terminal frontend provides a text-native presentation of that system.

However, a desktop surface can provide capabilities that a terminal cannot
reliably reproduce, particularly:

    - exact graphical Claire artwork,
    - animated mascot states,
    - precise visual composition,
    - rich panels,
    - pixel-level layout,
    - graphical permission surfaces,
    - richer interaction through mouse input.

The Desktop GUI therefore provides a second presentation surface without
creating a second engineering system.


-------------------------------------------------------------------------------

# 4. Scope

## 4.1 In Scope

This PRD covers:

    - Desktop GUI application shell.
    - Desktop startup / boot screen.
    - Main Pane.
    - Header/status region.
    - Scrollable action log.
    - Fixed input/prompt bar.
    - Graphical Claire mascot.
    - Mascot state presentation.
    - Permission view.
    - File Tree view.
    - Review Changes view.
    - Task / Workflow view.
    - Command Palette view.
    - Keyboard interaction.
    - Mouse interaction.
    - Panel navigation.
    - View replacement behavior.
    - Session/application status presentation.
    - Streaming agent activity presentation.
    - Desktop ↔ application communication.
    - Local process/service integration.
    - Desktop frontend tests.
    - Desktop integration tests.
    - Desktop accessibility/fallback behavior.
    - Desktop packaging preparation.

## 4.2 Out of Scope

This PRD SHALL NOT define:

    - a second Engineering Engine,
    - a second Workflow system,
    - a second Execution system,
    - a second Verification system,
    - a second Permission system,
    - a second Model Gateway,
    - direct Tool execution from React components,
    - duplicate command semantics,
    - remote distributed execution infrastructure,
    - a web SaaS product,
    - an IDE replacement,
    - speculative V2 autonomous behavior.

-------------------------------------------------------------------------------

# 5. Core Architectural Principle

The Desktop GUI SHALL be a thin graphical frontend.

The architecture SHALL preserve:

    Desktop GUI
        ↓
    Desktop Interaction Adapter
        ↓
    ClaireCoderV1
        ↓
    Existing V1 System

The Desktop GUI SHALL NOT become the owner of engineering state.

The Desktop GUI MAY:

    - display state,
    - collect user input,
    - present commands,
    - present permission decisions,
    - display Tools,
    - display Workflow,
    - display Execution,
    - display Verification,
    - display session information.

The Desktop GUI SHALL NOT:

    - determine authorization,
    - execute Tools,
    - calculate Workflow transitions,
    - decide execution success,
    - evaluate Verification,
    - own model-provider behavior,
    - mutate private subsystem state.

-------------------------------------------------------------------------------

# 6. Frontend Relationship

The Desktop GUI and terminal frontend SHALL be independent presentation
surfaces over the same application semantics.

Conceptually:

                         ClaireCoderV1
                              │
              ┌───────────────┴────────────────┐
              │                                │
       Terminal Frontend                 Desktop Frontend
              │                                │
          CLI / TUI                     Tauri + React
              │                                │
              └───────────────┬────────────────┘
                              │
                     Shared Application
                     / Interaction Semantics

The Desktop GUI SHALL NOT require changes to Engineering Engine semantics
merely because its presentation capabilities differ from the terminal.


-------------------------------------------------------------------------------

# 7. Technology Direction

The Desktop GUI SHALL use:

    Tauri
        +
    React

unless a later explicit architecture decision supersedes this choice.

The frontend SHALL remain separated from the Python/application backend.

The Desktop GUI SHOULD communicate with the local ClaireCoder application
through a controlled local boundary such as:

    - IPC,
    - WebSocket,
    - local HTTP,
    - or another explicitly approved local transport.

The exact transport SHALL be finalized by:

    CC-ADR-008

The React frontend SHALL NOT directly import or execute Python engineering
subsystems.


-------------------------------------------------------------------------------

# 8. Application Process Model

The preferred runtime model is:

    Desktop GUI Process
        ↓
    Local ClaireCoder Application Process
        ↓
    ClaireCoderV1
        ↓
    Existing V1 Subsystems

The Desktop GUI SHALL automatically start the local ClaireCoder application
process through the approved lifecycle boundary during normal Desktop launch.

The Desktop GUI MAY additionally stop, reconnect to, or monitor the local
application process through the same approved lifecycle boundary.

The GUI SHALL NOT assume that it owns the lifetime of individual engineering
subsystems.

Application restart/reconnection behavior SHALL be defined by the Desktop
architecture and application boundary.


-------------------------------------------------------------------------------

# 9. Reference Window

The Desktop GUI SHALL use the locked desktop design size as its reference
composition.

Default / intrinsic reference size:

    919 × 635 pixels

This is the reference application composition size.

The application SHALL NOT automatically grow the window to fit content.

The user MAY manually resize the window.

The application SHALL support ordinary desktop resizing and snapping so that
developers can place ClaireCoder beside:

    - code editors,
    - terminals,
    - browsers,
    - documentation,
    - other development tools.

The content SHALL adapt inside the available window rather than forcing the
window to grow.


-------------------------------------------------------------------------------

# 10. Window Behavior

The Desktop GUI SHALL:

    - open at the reference size where practical,
    - allow manual resizing,
    - preserve application usability at smaller sizes,
    - avoid automatic content-driven window growth,
    - preserve the major visual hierarchy while resizing,
    - maintain panel behavior inside the same window.

No normal user interaction SHALL open secondary content in a separate window.

Desktop panels SHALL remain inside the main application window.


-------------------------------------------------------------------------------

# 11. Visual Fidelity

The Desktop GUI SHALL reproduce the locked desktop reference design with a
high degree of visual fidelity.

The target SHALL be:

    1:1 visual recreation at the reference geometry.

The implementation SHALL preserve, where technically supported:

    - exact colors,
    - spacing,
    - relative dimensions,
    - typography,
    - borders,
    - line heights,
    - visual hierarchy,
    - mascot placement,
    - prompt placement,
    - panel geometry.

The Desktop GUI SHALL NOT treat the reference as inspiration only.

The locked design SHALL be considered the visual source of truth.

Framework defaults SHALL NOT redefine the product appearance.


-------------------------------------------------------------------------------

# 12. Desktop Design Authority

The Desktop GUI SHALL use:

    DESKTOP-DESIGN.md

as the authoritative UX and interaction specification.

The document SHALL define:

    - reference dimensions,
    - layout,
    - screens/views,
    - mascot states,
    - panel navigation,
    - keyboard behavior,
    - mouse behavior,
    - Esc semantics,
    - confirmation semantics,
    - resizing behavior,
    - visual tokens.

Implementation SHALL follow the design document rather than reconstructing
visual decisions independently in individual React components.


-------------------------------------------------------------------------------

# 13. Boot Screen

The Desktop GUI SHALL provide a branded boot screen.

The boot screen SHALL include the canonical Claire graphical artwork.

The boot composition SHALL visually follow the locked reference design.

The boot process MAY display:

    - ClaireCoder branding,
    - tagline,
    - configuration loading,
    - model gateway readiness,
    - Tool registration,
    - workspace preparation,
    - Skill loading,
    - session startup,
    - progress.

The boot screen SHALL represent actual application startup state where such
state is available.

It SHALL NOT become a second application initialization authority.


-------------------------------------------------------------------------------

# 14. Main Pane

The Main Pane SHALL be the primary Desktop GUI view.

The Main Pane SHALL contain:

    - fixed Header,
    - session/repository/model/mode status,
    - scrollable Action Log,
    - Claire graphical presentation,
    - prompt/input bar,
    - shortcut/navigation controls.

The Main Pane SHALL remain within the fixed application window.

The Main Pane SHALL NOT expand the window based on action-log length.


-------------------------------------------------------------------------------

# 15. Header

The Header SHALL remain fixed while the Action Log scrolls.

The Header SHALL display, where available:

    - working directory,
    - selected model,
    - current mode,
    - session identifier,
    - current Task,
    - Task progress,
    - context usage.

The Header SHALL follow the locked desktop visual hierarchy.


-------------------------------------------------------------------------------

# 16. Action Log

The Action Log SHALL be internally scrollable.

The Action Log MAY display:

    - file reads,
    - edits,
    - Tool requests,
    - Tool results,
    - test execution,
    - Verification,
    - permissions,
    - failures,
    - completion,
    - Claire text messages.

New activity SHALL stream into the Action Log.

The Action Log SHALL NOT cause the application window to grow.

The Action Log SHALL consume authoritative application events/state.

The GUI SHALL NOT infer engineering outcomes from visual appearance alone.


-------------------------------------------------------------------------------

# 17. Prompt / Input Bar

The prompt SHALL remain fixed at the bottom of the Main Pane.

The prompt SHALL use the locked glass/translucent visual treatment.

The visual implementation SHOULD provide:

    - translucent or simulated translucent background,
    - subtle border,
    - cyan accent,
    - appropriate corner treatment,
    - visible keyboard focus,
    - cursor,
    - placeholder/help text where appropriate.

The prompt SHALL remain visually integrated with the locked reference design.

The prompt SHALL accept natural-language engineering objectives through the
approved Interaction boundary.


-------------------------------------------------------------------------------

# 18. Claire Graphical Identity

The Desktop GUI SHALL use the canonical Claire graphical artwork.

The Desktop GUI SHALL NOT reconstruct Claire using:

    - Unicode,
    - terminal glyphs,
    - text placeholders,
    - generic avatars.

The graphical Claire artwork SHALL preserve:

    - original appearance,
    - proportions,
    - pixel-art style,
    - intended visual placement,
    - applicable transparency,
    - state-specific artwork.


-------------------------------------------------------------------------------

# 19. Mascot States

The Desktop GUI SHALL support the following nine mascot states:

    IDLE
    THINKING
    WORKING
    CONFIRM
    SUCCESS
    WARNING
    ERROR
    PAUSED
    COMPLETED

Mascot state SHALL be derived from authoritative application state.

Mascot state SHALL remain presentation-only.

The mascot SHALL NOT:

    - own Workflow,
    - own Execution,
    - make Permission decisions,
    - own Verification,
    - own Context,
    - control Tool execution,
    - become the source of truth for application state.

Each supported state SHALL use the canonical visual representation defined by
the desktop reference.


-------------------------------------------------------------------------------

# 20. View Model

The Desktop GUI SHALL use a view-based navigation model.

The primary application window SHALL have one active primary view at a time.

The available views SHALL include:

    Main Pane
    Permission View
    File Tree View
    Review Changes View
    Task / Workflow View
    Command Palette View

The active view SHALL own the main viewport.

The application SHALL NOT keep the Main Pane active and scrollable beneath a
secondary view.


-------------------------------------------------------------------------------

# 21. View Replacement Behavior

Opening a secondary panel SHALL replace the current Main Pane view inside the
same 919×635 application window.

The behavior SHALL be:

    Main Pane
        ↓
    File Tree View

or:

    Main Pane
        ↓
    Review Changes View

or:

    Main Pane
        ↓
    Task / Workflow View

or:

    Main Pane
        ↓
    Command Palette View

or:

    Main Pane
        ↓
    Permission View

The application SHALL NOT:

    - open another application window,
    - enlarge the application window,
    - leave the Main Pane scrollable behind the selected view.

Only the active view owns the primary viewport.


-------------------------------------------------------------------------------

# 22. File Tree View

The File Tree SHALL be opened through:

    Ctrl+T

and through the corresponding clickable bottom-bar control.

The File Tree SHALL replace the Main Pane view.

The File Tree MAY provide:

    - repository hierarchy,
    - modified files,
    - newly created files,
    - unchanged files,
    - file selection,
    - internal scrolling.

The File Tree SHALL remain a presentation view.

It SHALL NOT become a repository-state authority.


-------------------------------------------------------------------------------

# 23. Review Changes View

The Review Changes view SHALL be opened through:

    Ctrl+R

and through the corresponding clickable bottom-bar control.

The Review view SHALL replace the Main Pane view.

The Review view SHOULD provide:

    - files changed,
    - additions,
    - deletions,
    - new files,
    - file selection,
    - diff inspection.

The Review view MAY support commit interaction where the underlying application
boundary provides it.

The Review view SHALL NOT independently decide repository state.


-------------------------------------------------------------------------------

# 24. Task / Workflow View

The Task / Workflow view SHALL be opened through:

    Ctrl+P

and through the corresponding clickable bottom-bar control.

The Task view SHALL replace the Main Pane view.

The Task view MAY provide:

    - current Workflow,
    - current Task,
    - Task progress,
    - objective summary,
    - completion state,
    - validation state.

The view SHALL be read-oriented unless an explicit application operation is
being routed through the approved Interaction boundary.


-------------------------------------------------------------------------------

# 25. Command Palette View

The Command Palette SHALL be opened through:

    ?

and through its corresponding user-visible control.

The Command Palette SHALL replace the Main Pane view.

The Command Palette SHALL provide:

    - command categories,
    - command search/filter,
    - keyboard navigation,
    - mouse selection,
    - Enter activation.

Application commands SHALL continue to route through the shared Interaction
semantics.

Presentation-only controls MAY be handled directly by the Desktop presentation
layer.


-------------------------------------------------------------------------------

# 26. Permission View

A permission request SHALL replace the Main Pane view with the Permission
View.

The Permission View SHALL clearly communicate:

    - requested operation,
    - Tool/action information,
    - applicable risk context,
    - available decisions,
    - Claire contextual message where defined.

The UI MAY collect:

    [y] yes
    [n] no
    [a] yes, always this session
    [d] diff
    Esc cancel

The final authorization semantics SHALL remain owned by the Permission Engine.


-------------------------------------------------------------------------------

# 27. Keyboard Navigation

The Desktop GUI SHALL support:

    Ctrl+T
        Open File Tree View.

    Ctrl+R
        Open Review Changes View.

    Ctrl+P
        Open Task / Workflow View.

    ?
        Open Command Palette.

    Enter
        Submit prompt or activate the currently selected control.

    Esc
        Perform active-view-specific close/cancel behavior.

    Ctrl+C
        Engineering-operation interruption through the approved application
        boundary where applicable.


-------------------------------------------------------------------------------

# 28. Mouse Navigation

The Desktop GUI SHALL support mouse activation for visible navigation and
primary interaction controls.

Clicking a bottom-bar navigation control SHALL perform the same operation as
its documented keyboard shortcut.

For example:

    Click "File Tree"
        = Ctrl+T

    Click "Review"
        = Ctrl+R

    Click "Task"
        = Ctrl+P

    Click "Help / Palette"
        = ?

Mouse interaction SHALL NOT bypass the same application/interaction boundaries
used by keyboard commands.


-------------------------------------------------------------------------------

# 29. Esc Semantics

Esc behavior SHALL depend on the active view.

## File Tree

    Esc
        Close the File Tree view.
        Return to Main Pane.
        No engineering side effect.

## Task / Workflow View

    Esc
        Close the Task view.
        Return to Main Pane.
        No engineering side effect.

## Command Palette

    Esc
        Close the Command Palette.
        Return to Main Pane.
        No engineering side effect.

## Permission View

    Esc
        Cancel the pending permission interaction.

This is an intentional cancellation of the pending interaction.

## Review Changes

    Esc
        Back out of the active Review interaction according to its current
        state.

If a review interaction is holding a pending decision, Esc SHALL discard/cancel
that pending interaction according to the defined review contract.

Esc SHALL NOT be treated universally as "close window."

Esc SHALL NOT silently cancel an engineering operation.

-------------------------------------------------------------------------------

# 30. Explicit Confirmation / Completion

Explicit user actions SHALL complete the corresponding interaction where
supported.

Permission:

    [y] yes
    [n] no
    [a] yes, always this session
    [d] diff

A resolved permission decision SHALL return the user to the appropriate main
application state and update the Action Log.

Review:

    Enter
        View selected diff.

    c
        Commit where supported by the underlying application boundary.

    q
        Return/back.

Explicit completion SHALL return to the Main Pane or appropriate resulting view
and preserve the resulting application state in the Action Log.


-------------------------------------------------------------------------------

# 31. Scroll Ownership

Only the active view SHALL own its internal scrolling.

Examples:

    Main Pane
        Action Log scrolls.

    File Tree
        File hierarchy may scroll.

    Review Changes
        Review content may scroll.

    Task View
        Task content may scroll when required.

    Command Palette
        Command results may scroll when required.

    Permission View
        The permission surface SHALL remain a focused interaction surface
        rather than becoming the Main Pane transcript.

The application window SHALL never grow because a view contains additional
content.


-------------------------------------------------------------------------------

# 32. Streaming Integration

The Desktop GUI SHALL support progressive presentation of application events.

The conceptual path is:

    ClaireCoderV1 Event / State
        ↓
    Desktop Presentation Adapter
        ↓
    React View Model
        ↓
    UI Update

Streaming SHALL update:

    - Action Log,
    - status,
    - Permission View,
    - Claire state,
    - Task progress,
    - Verification state.

The GUI SHALL NOT manufacture application events as substitutes for actual
Engineering Engine state.


-------------------------------------------------------------------------------

# 33. Application Commands

The Desktop GUI SHALL support the shared documented application command
surface, including:

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

These commands SHALL use the shared Interaction/Application semantics.

Desktop-specific presentation commands MAY exist where they do not mutate
engineering state directly.


-------------------------------------------------------------------------------

# 34. Session Behavior

The Desktop GUI SHALL support the approved application/session operations.

These MAY include:

    - starting a session,
    - viewing session identity,
    - resuming a session,
    - continuing an existing operation,
    - session status,
    - closing a session.

The GUI SHALL NOT create a second persistence authority.


-------------------------------------------------------------------------------

# 35. Error and Disconnect Behavior

The Desktop GUI SHALL handle local application communication failure
gracefully.

The GUI SHOULD distinguish:

    application unavailable
    transport disconnected
    request failed
    operation failed
    permission pending
    application restarting

The GUI SHALL NOT silently convert transport failure into engineering success
or failure.

Where possible, it SHALL offer controlled reconnection or restart behavior.


-------------------------------------------------------------------------------

# 36. Resizing Behavior

The Desktop GUI SHALL support manual window resizing.

Resizing SHALL:

    - preserve the application window,
    - reflow the active view,
    - preserve major visual relationships,
    - preserve fixed header/prompt behavior where practical,
    - avoid forced window growth.

The reference geometry remains:

    919 × 635

Other dimensions are adaptive presentations of the same design.


-------------------------------------------------------------------------------

# 37. Accessibility

The Desktop GUI SHALL provide meaningful keyboard navigation.

Critical state SHALL not depend solely on:

    - color,
    - mascot animation,
    - visual position.

Controls SHALL have meaningful labels.

Permission decisions SHALL remain understandable without relying exclusively
on graphical styling.


-------------------------------------------------------------------------------

# 38. Security / Trust Boundary

The Desktop GUI SHALL be treated as a local frontend.

It SHALL NOT:

    - expose private subsystem state unnecessarily,
    - execute arbitrary Tool commands directly,
    - bypass permission checks,
    - bypass application authorization,
    - embed provider credentials into React source,
    - persist secrets in plain UI state.

Credential/configuration handling SHALL be defined by the application/configuration
architecture rather than arbitrary React storage.


-------------------------------------------------------------------------------

# 39. Testing Strategy

## Unit Tests

Test:

    - components,
    - views,
    - navigation,
    - input behavior,
    - keyboard shortcuts,
    - mouse interaction,
    - view replacement,
    - Esc semantics,
    - mascot state mapping,
    - Action Log updates,
    - responsive layout.

## Integration Tests

Test:

    - startup,
    - connection to the local application,
    - objective submission,
    - streaming,
    - permission,
    - Tool activity,
    - Verification,
    - Workflow visibility,
    - completion,
    - interruption,
    - session operations,
    - reconnect behavior.

## Boundary Tests

Verify that the Desktop GUI cannot:

    - directly execute Tools,
    - bypass PermissionEngine,
    - mutate Workflow directly,
    - mutate ExecutionManager directly,
    - mutate VerificationEngine directly,
    - own provider-specific logic.

-------------------------------------------------------------------------------

# 40. Acceptance Criteria

CC-PRD-012 SHALL be considered successfully implemented when:

## AC-001 — Desktop Startup

A developer can launch the Desktop GUI through the supported application
entry point.

## AC-002 — Reference Window

The application opens using the locked 919 × 635 reference composition where
practical.

## AC-003 — Manual Resize

The user can resize the application window without application-driven growth.

## AC-004 — Main Pane

The Main Pane displays:

    header,
    action log,
    Claire,
    prompt,
    navigation controls.

## AC-005 — Scroll Ownership

The Action Log scrolls internally without changing the window size.

## AC-006 — Claire Identity

The canonical graphical Claire is displayed using the approved artwork and
state mappings.

## AC-007 — File Tree

Ctrl+T or the visible navigation control switches to the File Tree view.

## AC-008 — Review

Ctrl+R or the visible navigation control switches to the Review Changes view.

## AC-009 — Task View

Ctrl+P or the visible navigation control switches to the Task / Workflow view.

## AC-010 — Command Palette

? or the visible navigation control switches to the Command Palette view.

## AC-011 — Permission

Permission requests replace the Main Pane with the Permission View.

## AC-012 — View Replacement

Only one primary view owns the viewport at a time.

Secondary views do not appear as independent windows.

## AC-013 — Esc Semantics

Esc closes non-pending navigational views and cancels pending interaction views
according to the documented semantics.

## AC-014 — Confirmation

Explicit confirmation actions resolve their intended interaction and return
to the appropriate application state.

## AC-015 — Engine Integration

Desktop interaction uses the same approved application and engineering
semantics as the terminal frontend.

## AC-016 — Architecture Isolation

The Desktop GUI does not:

    direct-execute Tools,
    bypass Permission,
    own Workflow,
    own Execution,
    own Verification,
    replace ClaireCoderV1.

## AC-017 — Visual Fidelity

At the locked reference geometry, the Desktop GUI reproduces the approved
desktop design with high visual fidelity.

## AC-018 — Regression Safety

Desktop integration does not break the approved ClaireCoder V1 regression
suite.


-------------------------------------------------------------------------------

# 41. Non-Functional Requirements

## NFR-001 — Responsiveness

The Desktop GUI SHOULD remain responsive during streaming agent activity.

## NFR-002 — Stable Window

The application SHALL NOT grow automatically as content increases.

## NFR-003 — Maintainability

Desktop presentation components SHALL remain separated from application logic.

## NFR-004 — Testability

Desktop UI components SHALL be testable without requiring real provider
credentials.

## NFR-005 — Resilience

The Desktop GUI SHALL handle temporary application/transport disconnection
without corrupting session state.

## NFR-006 — Accessibility

Critical interaction semantics SHALL remain understandable without relying only
on color or mascot animation.


-------------------------------------------------------------------------------

# 42. Deliverables

Implementation of CC-PRD-012 SHALL ultimately produce:

    1. Desktop application shell.
    2. Local application communication boundary.
    3. Boot screen.
    4. Main Pane.
    5. Header/status.
    6. Scrollable Action Log.
    7. Prompt/input bar.
    8. Canonical Claire graphical identity.
    9. Nine mascot states.
    10. File Tree View.
    11. Review Changes View.
    12. Task / Workflow View.
    13. Command Palette View.
    14. Permission View.
    15. Keyboard interaction.
    16. Mouse interaction.
    17. View replacement/navigation.
    18. Streaming integration.
    19. Session integration.
    20. Error/reconnection behavior.
    21. Desktop tests.
    22. Integration tests.
    23. Packaging preparation.
    24. Updated desktop user documentation.


-------------------------------------------------------------------------------

# 43. Implementation Constraints

The implementation SHALL NOT:

    - create another Engineering Engine,
    - create another Workflow state machine,
    - create another Execution state machine,
    - create another Verification system,
    - create another Permission system,
    - duplicate command semantics,
    - directly execute Tools from React components,
    - bypass ToolExecutor,
    - bypass PermissionEngine,
    - mutate private application state,
    - embed provider-specific SDK logic in the Desktop frontend,
    - create a second persistence authority,
    - create a second session authority,
    - force automatic window growth,
    - replace the locked desktop design with a new visual interpretation,
    - turn panels into independent windows,
    - leave the Main Pane active underneath secondary views.


-------------------------------------------------------------------------------

# 44. Relationship With Other PRDs

## CC-PRD-001

Provides the Engineering Engine consumed by the Desktop GUI.

## CC-PRD-002

Provides Model Gateway abstraction consumed by the application layer.

## CC-PRD-003

Provides Tool and Skill capabilities.

The Desktop GUI SHALL display Tool and Skill activity without executing them
directly.

## CC-PRD-004

Provides Workflow and Planning.

The Desktop GUI SHALL display Workflow state without owning it.

## CC-PRD-005

Provides Interaction, Modes, and Commands.

The Desktop GUI SHALL consume those interaction semantics.

## CC-PRD-006

Provides Permission and Autonomy architecture.

The Desktop GUI SHALL present permission interaction without becoming the
authority.

## CC-PRD-007

Provides Execution State and Recovery.

The Desktop GUI SHALL display Execution state without owning it.

## CC-PRD-008

Provides Context and Memory boundaries.

The Desktop GUI MAY display context information but SHALL NOT mutate the
Context Engine.

## CC-PRD-009

Provides Verification.

The Desktop GUI SHALL display Verification results without becoming the
evaluator.

## CC-PRD-010

Provides final V1 integration.

The Desktop GUI SHALL operate over the approved ClaireCoderV1 boundary.

## CC-PRD-011

Defines the terminal/CLI frontend.

The Desktop GUI SHALL share application and interaction semantics while
remaining a distinct visual frontend.


-------------------------------------------------------------------------------

# 45. AI Instructions

When implementing CC-PRD-012:

    1. Treat DESKTOP-DESIGN.md as the authoritative desktop visual and
       interaction specification.
    2. Treat the locked desktop reference artwork as the canonical visual
       reference.
    3. Treat CC-ADR-008 as the authoritative desktop architecture decision.
    4. Keep the Desktop GUI as a frontend only.
    5. Use the approved application/interaction boundary.
    6. Do not create another Engineering Engine.
    7. Do not create another Workflow state machine.
    8. Do not create another Execution State machine.
    9. Do not create another Verification system.
    10. Do not create another Permission system.
    11. Keep Tools behind ToolExecutor.
    12. Keep authorization behind PermissionEngine.
    13. Keep Workflow state owned by WorkflowManager.
    14. Keep Execution state owned by ExecutionManager.
    15. Keep Verification state owned by VerificationEngine.
    16. Keep provider independence behind ModelGateway.
    17. Keep React components presentation-oriented.
    18. Do not put engineering orchestration inside React components.
    19. Preserve the 919 × 635 reference geometry.
    20. Do not allow content to force application window growth.
    21. Preserve exact visual composition.
    22. Use canonical Claire artwork.
    23. Preserve all nine mascot states.
    24. Keep Main Pane, Permission, File Tree, Review, Task, and Palette as
        distinct active views.
    25. Only one primary view shall own the viewport at a time.
    26. Do not implement secondary views as independent application windows.
    27. Preserve exact Esc semantics.
    28. Preserve explicit confirmation semantics.
    29. Support both keyboard and mouse navigation.
    30. Keep session semantics below the frontend.
    31. Handle transport failure explicitly.
    32. Never store provider secrets in React source.
    33. Use mocks/fakes for UI tests where real providers are unnecessary.
    34. Preserve the existing V1 regression suite.
    35. Do not introduce speculative V2 engineering architecture.
    36. Treat CC-PRD-011 as the authoritative terminal frontend requirement.
    37. Treat this PRD as the authoritative Desktop GUI product requirement
        unless explicitly superseded.


-------------------------------------------------------------------------------

# 46. Design Lock

CC-PRD-012 defines the product requirements for the ClaireCoder Desktop GUI.

The authoritative visual/interaction reference SHALL be:

    DESKTOP-DESIGN.md

The reference desktop composition SHALL use:

    919 × 635 pixels

as its default/reference size.

The Desktop GUI SHALL preserve:

    - exact visual hierarchy,
    - exact mascot placement,
    - graphical Claire identity,
    - nine mascot states,
    - fixed Header,
    - scrollable Action Log,
    - fixed Prompt,
    - fixed application window behavior,
    - view replacement navigation,
    - keyboard navigation,
    - mouse navigation,
    - panel-specific Esc semantics,
    - explicit confirmation behavior,
    - approved ClaireCoder architecture boundaries.

The product requirements, architectural ownership, and visual/interaction intent
SHALL remain stable unless this PRD is explicitly superseded.


###############################################################################

END OF CC-PRD-012
###############################################################################