###############################################################################

# CLAIRECODER DESKTOP GUI — DESIGN SPECIFICATION

# File        : DESKTOP-DESIGN.md
# Version     : 1.0.0
# Status      : FINAL
# Related     : CC-PRD-012
#              CC-ADR-008

###############################################################################


# 1. Purpose

DESKTOP-DESIGN.md is the authoritative visual and interaction specification
for the ClaireCoder Desktop GUI.

It defines:

    - window geometry,
    - visual composition,
    - layout,
    - typography,
    - spacing,
    - colors,
    - Claire presentation,
    - mascot states,
    - view navigation,
    - keyboard behavior,
    - mouse behavior,
    - scrolling,
    - prompt behavior,
    - permission interaction,
    - review interaction,
    - panel replacement behavior,
    - startup behavior,
    - resizing behavior.

CC-PRD-012 defines WHAT the Desktop GUI must provide.

CC-ADR-008 defines HOW the Desktop GUI is architecturally connected.

This document defines WHAT THE USER SEES AND HOW THE USER INTERACTS WITH IT.


-------------------------------------------------------------------------------

# 2. Visual Authority

The Desktop GUI SHALL reproduce the locked ClaireCoder desktop references.

The reference artwork is the visual source of truth.

The Desktop implementation SHALL NOT:

    - reinterpret the composition,
    - simplify the mascot into a generic avatar,
    - redesign the header,
    - redesign the prompt,
    - replace the panel compositions,
    - introduce unrelated dashboard styling,
    - alter the established color language.

The target is:

    faithful 1:1 recreation at the reference geometry.

Where platform rendering differences make literal pixel identity impossible,
the implementation SHALL preserve the reference's:

    - geometry,
    - proportions,
    - spacing,
    - typography hierarchy,
    - color relationships,
    - borders,
    - mascot scale,
    - visual rhythm.


-------------------------------------------------------------------------------

# 3. Reference Window

The canonical desktop reference size is:

    919 × 635 px

This is the intrinsic/reference composition size.

The application SHOULD initially open at:

    width  = 919 px
    height = 635 px

The application SHALL NOT automatically enlarge the window because content
requires additional space.

The user MAY manually:

    - resize,
    - maximize,
    - snap,
    - place beside another application,
    - use split-screen layouts.

The internal composition SHALL adapt to the available viewport.


-------------------------------------------------------------------------------

# 4. Window Rules

The application SHALL use one primary desktop window.

Secondary views SHALL NOT open separate application windows.

The following MUST remain inside the same window:

    Main Pane
    Permission View
    File Tree View
    Review View
    Task View
    Command Palette View

The window size is controlled by the user/platform.

The application content is controlled by the active view.

Content SHALL NEVER force automatic window growth.


-------------------------------------------------------------------------------

# 5. Main Desktop Composition

The Main Pane consists of five major visual regions:

    1. Header
    2. Status information
    3. Action Log
    4. Claire visual region
    5. Prompt + navigation footer

Conceptually:

    ┌──────────────────────────────────────────────────────────────┐
    │ HEADER / IDENTITY / STATUS                                  │
    ├──────────────────────────────────────────────────────────────┤
    │                                                              │
    │ ACTION LOG                              CLAIRE               │
    │                                                              │
    │ activity                                                    │
    │ activity + diff                                             │
    │ activity                                                    │
    │ verification                                               │
    │ Claire message                                              │
    │                                                              │
    ├──────────────────────────────────────────────────────────────┤
    │ PROMPT / INPUT                                              │
    │ SHORTCUTS / NAVIGATION                                      │
    └──────────────────────────────────────────────────────────────┘

This diagram describes functional regions only.

The exact spacing and proportions SHALL follow the locked visual reference.


-------------------------------------------------------------------------------

# 6. Header

The Header SHALL remain fixed.

The Header SHALL NOT scroll with the Action Log.

The Header SHALL contain, where available:

    ClaireCoder identity
    working directory
    selected model
    current mode
    session identity
    current Task
    Task progress
    context usage

The information SHALL be compact and horizontally composed.

The Header SHALL NOT become a collection of independent cards.

The Header SHALL preserve the visual hierarchy of the reference design.


-------------------------------------------------------------------------------

# 7. Action Log

The Action Log is the primary scrollable content region.

It SHALL display progressive engineering activity.

Examples:

    Reading src/decoder.py
    Editing src/decoder.py
    Running pytest
    Verification passed
    Permission required
    Task completed

The Action Log SHALL:

    - scroll vertically,
    - preserve history,
    - support streaming updates,
    - preserve activity ordering,
    - avoid unbounded window growth.

The application window SHALL remain fixed while Action Log content grows.


-------------------------------------------------------------------------------

# 8. Action Log Visual Language

The Action Log SHALL preserve the established ClaireCoder activity hierarchy.

Examples:

    > ✓ Reading src/decoder.py
    > ● Editing src/router.py
    > ◌ Running pytest tests/decoder/
    > ⚠ Approval Required
    > ✗ 3 tests failed
    > ✓ Verification passed

The leading activity marker SHALL remain visually consistent.

Activity blocks SHALL use whitespace and hierarchy rather than unnecessary
nested boxes.

Long output MAY collapse to concise summaries.

Expanded activity SHOULD reveal additional information without changing the
overall page composition.


-------------------------------------------------------------------------------

# 9. Diff Presentation

Diffs SHALL appear as contextual content associated with the relevant
activity.

Small diffs MAY appear inline.

Large diffs SHOULD collapse to a summary.

Example:

    src/decoder.py                 +18 -4

Expanded form SHALL provide readable:

    additions
    removals
    line references
    surrounding context

The diff itself MAY use a contained code region.

The entire activity entry SHALL NOT be wrapped in a redundant card merely
because a diff exists.


-------------------------------------------------------------------------------

# 10. Claire Visual Region

The Desktop GUI SHALL display the canonical Claire artwork.

Claire SHALL be visually integrated into the Main Pane.

The artwork SHALL:

    - preserve proportions,
    - preserve visual details,
    - preserve pixel-art style,
    - preserve transparency where applicable,
    - use the canonical state artwork.

Claire SHALL NOT become an independent floating window.

Claire SHALL NOT be surrounded by a generic UI card unless the locked reference
specifically shows one.

The Claire region SHALL occupy the same general visual role and scale as the
reference composition.


-------------------------------------------------------------------------------

# 11. Mascot States

The Desktop GUI SHALL support exactly these nine mascot states:

    IDLE
    THINKING
    WORKING
    CONFIRM
    SUCCESS
    WARNING
    ERROR
    PAUSED
    COMPLETED

State transitions SHALL be derived from application state.

The mascot SHALL remain presentation-only.

The mascot SHALL never become an authoritative application state owner.


-------------------------------------------------------------------------------

# 12. Mascot State Meaning

The visual mapping SHOULD follow:

    IDLE
        Waiting for user interaction.

    THINKING
        Application/model processing.

    WORKING
        Active engineering work.

    CONFIRM
        A confirmation/permission interaction requires attention.

    SUCCESS
        A successful operation/result.

    WARNING
        Attention required without terminal failure.

    ERROR
        An error condition is visible.

    PAUSED
        Engineering operation paused.

    COMPLETED
        Current engineering objective/session operation completed.

The exact trigger for each state SHALL come from the authoritative application
state mapping, not from arbitrary React-side inference.


-------------------------------------------------------------------------------

# 13. Claire Message

Claire messages SHALL be visually distinct from ordinary Action Log activity.

Conceptual presentation:

    Claire:
        Streaming decode support has been added.
        All tests are passing.
        What would you like to work on next?

The Claire message MAY visually integrate with the mascot artwork.

Claire text SHALL use the established Claire identity styling.

The message SHALL remain part of the active view, not a separate pop-up.


-------------------------------------------------------------------------------

# 14. Prompt / Input Bar

The Prompt SHALL remain fixed at the bottom of the Main Pane.

The Prompt SHALL NOT scroll with the Action Log.

The Prompt SHALL use the locked glass/translucent visual treatment.

The visual treatment SHOULD include:

    translucent/simulated translucent background
    soft cyan-accented border
    compact corner treatment
    active cursor
    clear keyboard focus
    readable placeholder or prompt marker

The Prompt SHALL remain visually subordinate to the main conversation while
remaining clearly interactive.


-------------------------------------------------------------------------------

# 15. Prompt Behavior

Normal state:

    User may type an engineering objective.

Enter:

    submits the objective through the Interaction Layer.

Streaming state:

    Prompt remains visually anchored but may be disabled/suspended according
    to the approved interaction behavior.

Permission state:

    Prompt is replaced by the Permission View.

Secondary view:

    Prompt belongs to the Main Pane and SHALL NOT remain active underneath
    the secondary view.


-------------------------------------------------------------------------------

# 16. Bottom Navigation

The bottom navigation/footer SHALL display the primary discoverable actions.

Examples:

    Ctrl+T  File Tree
    Ctrl+R  Review
    Ctrl+P  Task
    ?       Commands

Clickable controls SHALL perform exactly the same operation as their keyboard
equivalent.

Keyboard and mouse interaction SHALL remain behaviorally equivalent.


-------------------------------------------------------------------------------

# 17. View Architecture

The Desktop GUI SHALL use a single active primary view.

The available views are:

    MainPane
    PermissionView
    FileTreeView
    ReviewView
    TaskView
    CommandPaletteView

Only one view SHALL own the primary viewport at a time.

The architecture SHALL NOT be:

    MainPane
        + floating overlay
        + main content still active underneath

Instead:

    MainPane
        ↓
    Active View

For example:

    MainPane
        ↓ Ctrl+R
    ReviewView

The Main Pane is no longer the active viewport while ReviewView is active.


-------------------------------------------------------------------------------

# 18. View Replacement Rule

Opening a secondary interface SHALL replace the Main Pane view inside the same
919×635 application window.

Examples:

    Main Pane
        ↓ Ctrl+T
    File Tree View

    Main Pane
        ↓ Ctrl+R
    Review View

    Main Pane
        ↓ Ctrl+P
    Task View

    Main Pane
        ↓ ?
    Command Palette

    Main Pane
        ↓ Permission Request
    Permission View

The active view owns:

    content,
    focus,
    scrolling,
    keyboard behavior,
    mouse interaction.


-------------------------------------------------------------------------------

# 19. Main Pane Background Behavior

When a secondary view is active:

    Main Pane scrolling STOPS.

The Main Pane SHALL NOT remain interactive underneath the selected view.

The Main Pane SHALL NOT continue streaming visible content into the background
of a replacement view.

The application SHALL return to the Main Pane after the active interaction is
closed/resolved.


-------------------------------------------------------------------------------

# 20. File Tree View

File Tree SHALL be accessible through:

    Ctrl+T

and:

    Click → File Tree

The File Tree SHALL replace the Main Pane.

It MAY support:

    - tree expansion/collapse,
    - selection,
    - internal scrolling,
    - modified-file indicators,
    - newly-created indicators.

The File Tree SHALL remain presentation-only.

It SHALL NOT become a second repository/change authority.


-------------------------------------------------------------------------------

# 21. Review View

Review SHALL be accessible through:

    Ctrl+R

and:

    Click → Review

The Review View SHALL replace the Main Pane.

The view MAY contain:

    Changes this session

    src/decoder.py       +18 -4
    src/router.py         +6 -0
    tests/test_decoder.py +22 -0

    3 files changed
    46 insertions
    4 deletions

The user SHALL be able to select files and inspect diffs.

The view MAY expose commit functionality where the application boundary
supports it.


-------------------------------------------------------------------------------

# 22. Task View

Task View SHALL be accessible through:

    Ctrl+P

and:

    Click → Task

The Task View SHALL replace the Main Pane.

Conceptual structure:

    Current Workflow

    1  Understand objective        ✓
    2  Plan changes                ✓
    3  Implement changes           ●
    4  Verify                      ○
    5  Complete                    ○

    Task Progress
    ███████████░░░░░░░░ 48%

    Objective:
    Add streaming decode support
    with interrupt capability.

The information SHALL come from Workflow/application state.


-------------------------------------------------------------------------------

# 23. Command Palette View

Command Palette SHALL be accessible through:

    ?

and:

    Click → Commands / Help

The Command Palette SHALL replace the Main Pane.

The palette SHOULD contain:

    search/filter
    categories
    command list
    keyboard navigation
    mouse selection

The palette SHALL distinguish:

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


-------------------------------------------------------------------------------

# 24. Permission View

Permission View SHALL replace the Main Pane when authorization input is
required.

Conceptual structure:

    Permission Required

    ClaireCoder wants to run:

        $ rm src/decoder_v1_deprecated.py

        [y] yes
        [n] no

        [a] yes, always this session
        [d] diff

    Claire:
        This will permanently delete the file.
        Are you sure?

    Esc to cancel

The visual design SHALL follow the locked desktop reference.


-------------------------------------------------------------------------------

# 25. Permission Focus

When Permission View is active:

    keyboard focus belongs exclusively to Permission View.

The Main Pane SHALL not accept prompt input.

The Action Log SHALL not own keyboard focus.

The user SHALL resolve or cancel the pending permission interaction before
normal Main Pane interaction resumes.


-------------------------------------------------------------------------------

# 26. Explicit Permission Actions

Supported actions:

    y
        yes

    n
        no

    a
        yes, always this session

    d
        inspect relevant diff where supported

    Esc
        cancel pending permission interaction

The UI SHALL only collect the decision.

Permission authority remains in the application/Permission Engine boundary.


-------------------------------------------------------------------------------

# 27. Review Explicit Actions

Review actions may include:

    Enter
        View selected diff.

    c
        Commit, where supported.

    q
        Return/back.

Esc:

    Back out of the current review interaction.

Where a pending review action exists, Esc SHALL discard/cancel according to the
active review state.


-------------------------------------------------------------------------------

# 28. Esc Semantics Matrix

The following behavior is LOCKED:

    Main Pane

        Esc
            No global engineering cancellation.
            Remains in Main Pane unless another transient UI interaction owns
            Esc.

    File Tree

        Esc
            Return to Main Pane.
            No engineering side effect.

    Task View

        Esc
            Return to Main Pane.
            No engineering side effect.

    Command Palette

        Esc
            Return to Main Pane.
            No engineering side effect.

    Permission View

        Esc
            Cancel pending permission interaction.

    Review View

        Esc
            Return/back according to current review state.
            Pending review interaction is discarded/cancelled where applicable.

Esc SHALL NOT be implemented as:

    "close whatever component is nearest"

The active view determines Esc semantics.


-------------------------------------------------------------------------------

# 29. Keyboard Shortcuts

Locked shortcuts:

    Ctrl+T
        File Tree

    Ctrl+R
        Review Changes

    Ctrl+P
        Task / Workflow

    ?
        Command Palette

    Enter
        Submit / activate

    Esc
        View-specific close/cancel

    Ctrl+C
        Engineering-operation interruption


-------------------------------------------------------------------------------

# 30. Mouse Interaction

Every visible primary shortcut control SHALL be mouse clickable.

Examples:

    click File Tree
        = Ctrl+T

    click Review
        = Ctrl+R

    click Task
        = Ctrl+P

    click Commands
        = ?

Mouse interactions SHALL route through the same application/interaction
semantics as keyboard-triggered commands.


-------------------------------------------------------------------------------

# 31. Scrolling

The application window SHALL remain fixed while internal view content scrolls.

Main Pane:

    Action Log scrolls.

File Tree:

    Tree content scrolls.

Review:

    Review content scrolls.

Task:

    Task content may scroll.

Command Palette:

    Command results may scroll.

Permission:

    Focused permission content does not become a background transcript.

No view SHALL cause automatic window growth.


-------------------------------------------------------------------------------

# 32. Resize Behavior

At:

    919 × 635

the composition SHALL match the locked reference as closely as possible.

At larger sizes:

    content may gain breathing room,
    major geometry remains stable.

At smaller sizes:

    content SHALL adapt without becoming unusable.

The application SHALL NOT automatically resize its window.

The user controls the window.


-------------------------------------------------------------------------------

# 33. Visual Tokens

The desktop visual language SHALL preserve the locked reference palette.

Primary:

    Cyan / Teal

Claire identity:

    Pink / Magenta

Success / additions:

    Green

Error / removals:

    Red

Warning / confirmation:

    Yellow

Secondary:

    Dim Grey

The visual system SHALL not use color as the sole semantic carrier.


-------------------------------------------------------------------------------

# 34. Typography

The desktop implementation SHALL use a typography hierarchy matching the
reference.

Primary considerations:

    - title hierarchy,
    - compact status text,
    - readable action log,
    - readable code,
    - prominent prompt,
    - distinct Claire identity.

Font selection SHALL preserve the appearance and relative hierarchy of the
reference.

Typography SHALL NOT be replaced by generic oversized dashboard headings.


-------------------------------------------------------------------------------

# 35. Borders and Surfaces

The implementation SHALL use borders and surfaces according to the locked
reference.

Do NOT:

    - wrap every Action Log line in a card,
    - box Claire unnecessarily,
    - create nested containers solely because a React component exists,
    - add dashboard-style cards that do not appear in the reference.

Whitespace SHALL be used deliberately.

The visual hierarchy SHALL come from:

    spacing
    typography
    color
    alignment
    imagery
    restrained borders.


-------------------------------------------------------------------------------

# 36. Desktop Boot Sequence

When the user starts the Desktop application:

    1. Desktop window opens.
    2. Boot Screen becomes active.
    3. Tauri starts the local ClaireCoder application process when required.
    4. Local transport is established.
    5. Protocol handshake occurs.
    6. Application readiness is confirmed.
    7. Boot progress reaches ready state.
    8. Main Pane becomes active.

The user SHALL NOT need to manually start the Python backend for normal
Desktop operation.

The application SHALL automatically start the required local backend process.


-------------------------------------------------------------------------------

# 37. Bootstrap Security

The Desktop ↔ backend bootstrap SHALL use a short-lived local connection token
or equivalent local trust mechanism.

The token SHALL:

    - be generated for the current launch,
    - have limited lifetime,
    - not be treated as a provider credential,
    - not be persisted as a long-term secret,
    - be invalid after the associated application lifecycle ends.

The exact token transport/mechanism SHALL follow CC-ADR-008.


-------------------------------------------------------------------------------

# 38. Provider Configuration

The Desktop GUI SHALL NOT store provider API keys in:

    React state
    localStorage
    sessionStorage
    frontend source
    Action Log
    browser-visible persistent storage

Persistent provider credentials SHALL use the application configuration layer.

Preferred persistent storage:

    operating-system secure credential store.

The GUI MAY provide configuration controls, but the GUI SHALL not become the
credential authority.

The actual credential SHALL be handled below the frontend boundary.


-------------------------------------------------------------------------------

# 39. Error / Disconnect Presentation

The Desktop GUI SHALL clearly distinguish:

    Application unavailable
    Connecting
    Reconnecting
    Connected
    Request failed
    Engineering operation failed
    Permission pending

Transport disconnect SHALL NOT automatically mean:

    engineering success
    engineering failure
    operation cancellation

The frontend SHALL recover authoritative state through the backend after
reconnection where possible.


-------------------------------------------------------------------------------

# 40. Animation

Animations SHALL be used to support:

    - boot sequence,
    - Claire state transitions,
    - subtle activity transitions,
    - panel transitions where defined.

Animations SHALL NOT:

    - block interaction,
    - obscure permission decisions,
    - alter application state,
    - become required for semantic understanding.

The mascot's visual state SHALL remain synchronized with authoritative
application state.


-------------------------------------------------------------------------------

# 41. Reduced Motion / Accessibility

Where feasible, users SHALL be able to reduce or disable non-essential
animation.

Disabling animation SHALL NOT:

    - remove important information,
    - change engineering behavior,
    - prevent interaction.

The application SHALL preserve semantic state through text and layout.


-------------------------------------------------------------------------------

# 42. Design Invariants

The following are locked invariants:

    1. Reference window = 919 × 635.
    2. Window does not auto-grow from content.
    3. User may manually resize.
    4. Header remains fixed.
    5. Action Log scrolls internally.
    6. Prompt remains fixed.
    7. Claire remains graphical in Desktop.
    8. Nine mascot states remain supported.
    9. Only one primary view owns the viewport.
    10. Secondary views do not open separate windows.
    11. Main Pane does not remain scrollable underneath another view.
    12. Keyboard and mouse controls are equivalent.
    13. Esc semantics are view-specific.
    14. Explicit confirmations resolve their pending interaction.
    15. Engineering authority remains below the Desktop frontend.
    16. Provider credentials never belong to React presentation state.
    17. Desktop startup automatically starts the required local backend.
    18. Local backend communication uses the approved local transport.
    19. Visual reference remains authoritative.
    20. Desktop does not become a second Engineering Engine.


-------------------------------------------------------------------------------

# 43. Implementation Guidance

React components SHOULD map to visual responsibilities.

Suggested structure:

    DesktopApp
      ├── BootScreen
      ├── MainPane
      │     ├── Header
      │     ├── ActionLog
      │     ├── ClaireWidget
      │     ├── PromptBar
      │     └── ShortcutBar
      ├── PermissionView
      ├── FileTreeView
      ├── ReviewView
      ├── TaskView
      └── CommandPaletteView

The exact component structure MAY change during implementation.

The visual responsibilities SHALL remain separated.

Engineering behavior SHALL remain outside individual visual components.


-------------------------------------------------------------------------------

# 44. Validation

Before Desktop implementation is considered visually complete:

    1. Compare 919×635 Main Pane against the locked reference.
    2. Compare Boot Screen against the reference.
    3. Compare Claire states against the mascot reference.
    4. Compare Permission View.
    5. Compare File Tree View.
    6. Compare Review View.
    7. Compare Task View.
    8. Compare Command Palette.
    9. Verify keyboard shortcuts.
    10. Verify mouse parity.
    11. Verify view replacement.
    12. Verify Esc semantics.
    13. Verify fixed window behavior.
    14. Verify internal scrolling.
    15. Verify backend startup.
    16. Verify reconnect behavior.
    17. Verify credential isolation.


-------------------------------------------------------------------------------

# 45. Final Design Lock

This document is the authoritative Desktop visual and interaction
specification.

The following are NOT negotiable implementation details:

    919 × 635 reference geometry
    fixed-header behavior
    internal Action Log scrolling
    fixed Prompt
    graphical Claire identity
    nine mascot states
    view replacement
    one active primary view
    no panel child windows
    keyboard/mouse parity
    Esc semantics
    explicit confirmation semantics
    automatic local backend startup
    credential isolation

Framework implementation may vary.

The product behavior and visual hierarchy may not.


###############################################################################

END OF DESKTOP-DESIGN.md

###############################################################################