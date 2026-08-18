# ClaireCoder TUI Design V2
# Status      : FINAL

## 1. Purpose

This document defines the visual and interaction design for the ClaireCoder V1
terminal interface.

The TUI is a presentation layer over the already-approved ClaireCoder
architecture. It MUST NOT own engineering orchestration, workflow state,
execution state, verification state, permission policy, model/provider logic,
or tool execution.

ClaireCoder should feel immediately familiar to users of terminal-native coding
agents while retaining its own visual identity through the established
ClaireCoder visual language and restrained terminal aesthetic.

The graphical Claire mascot is a Desktop GUI concern and is NOT rendered by
the terminal interface.


## 2. Design Principles

1. **Terminal-first** — the interface remains native to the terminal rather than
   becoming an IDE clone.

2. **Conversation-first** — the main experience is one continuous scrollback
   conversation.

3. **Agent activity is transparent** — tool calls, edits, tests, verification,
   failures, and approvals are visible in context.

4. **Permissions are explicit** — privileged actions use the existing
   Permission Engine and are presented through clear confirmation UI.

5. **Diffs are contextual** — changes appear inline when useful and collapse to
   summaries when large.

6. **Workflow-aware, not workflow-owning** — task and workflow state may be
   displayed, but the TUI never becomes its owner.

7. **Advanced UI is opt-in** — file tree, task view, and review views are
   overlays or temporary panes rather than permanent dashboard chrome.

8. **Minimal chrome** — persistent status information is useful but must not
   dominate the transcript.

9. **Claire is persona, not terminal artwork** — Claire remains part of the
   terminal identity through the textual `Claire:` persona and ClaireCoder
   visual language.

10. **Responsive to terminal size** — the TUI degrades gracefully while
    preserving the locked visual hierarchy.


## 3. Canonical Visual Reference

The locked image remains the visual source of truth for the ClaireCoder TUI.

Reference:

    ClaireCoder-TUI-Design-V1.png

The reference establishes:

    - dark terminal canvas
    - cyan/teal primary UI language
    - restrained pink/magenta accenting
    - thin terminal borders
    - monospace text hierarchy
    - inline tool activity
    - inline diffs
    - permission confirmation card
    - optional file tree
    - review/change screen
    - task/workflow view
    - command palette

The existing visual composition and hierarchy SHALL remain unchanged.

This revision does NOT redesign:

    - borders
    - spacing
    - typography hierarchy
    - activity blocks
    - diff presentation
    - permission presentation
    - file tree
    - review view
    - task view
    - command palette
    - prompt placement
    - footer/shortcut presentation
    - color language

The only visual identity change is removal of graphical mascot rendering from
the terminal surface.


## 4. Main TUI Layout

The default view remains a single scrollback pane.

The following compact representation is authoritative for the intended terminal
appearance and density:

    ┌─ ClaireCoder ──────────────────────────────────────────────── v0.1 ─┐
    │ dir: ~/projects/foo   model: claire-large   mode: IMPLEMENT        │
    │ session: main        task: 2/5        context: 12.4k/200k           │
    ├────────────────────────────────────────────────────────────────────┤
    │                                                                    │
    │  ✓ Reading src/decoder.py                                         │
    │                                                                    │
    │  ● Editing src/decoder.py                                         │
    │    ┌────────────────────────────────────────────────────────────┐  │
    │    │ 42   def decode(self, tokens):                             │  │
    │    │ 43 -     return self._greedy(tokens)                       │  │
    │    │ 43 +     if self.streaming:                                │  │
    │    │ 44 +         return self._stream_decode(tokens)             │  │
    │    │ 45 +         return self._greedy(tokens)                   │  │
    │    └────────────────────────────────────────────────────────────┘  │
    │    +18 -4                                                           │
    │                                                                    │
    │  ◌ Running pytest tests/decoder/                                   │
    │    12 passed in 1.2s                                               │
    │                                                                    │
    │  ✓ Verification passed                                             │
    │    All criteria satisfied.                                         │
    │                                                                    │
    │  Claire:                                                            │
    │    Streaming decode support added with a safe fallback.            │
    │    All tests are passing.                                          │
    │                                                                    │
    ├────────────────────────────────────────────────────────────────────┤
    │ > add support for interrupting mid-stream█                        │
    │ ctrl+c interrupt   ctrl+t file tree   ctrl+r review changes       │
    │ ctrl+p task view   ? help   /commands                             │
    └────────────────────────────────────────────────────────────────────┘

This compact representation is a design reference, NOT a hard terminal
dimension.

The implementation SHALL adapt to available terminal width and height without
changing the established visual hierarchy.

The TUI SHALL remain practical inside:

    - IDE integrated terminals
    - standalone terminal windows
    - split terminal panes
    - SSH sessions
    - narrow terminal environments


## 5. Persistent Status Bar

The status area should expose the most useful current state:

    dir: ~/projects/foo
    model: claire-large
    mode: IMPLEMENT
    session: main
    task: 2/5
    context: 12.4k/200k

Provider-dependent information such as estimated cost may be displayed when
available, but it is not required for local or non-metered providers.


## 6. Agent Activity Blocks

Agent activity is rendered inline using compact semantic states.

    ◌ Running
    ✓ Completed
    ⚠ Approval required
    ✗ Failed

Examples:

    ✓ Reading src/decoder.py
    ● Editing src/router.py
    ◌ Running pytest tests/decoder/
    ✓ Verification passed
    ✗ 3 tests failed

Each activity block may be expanded or collapsed.

Collapsed output SHOULD summarize instead of flooding scrollback.


## 7. Inline Diffs

Small diffs are rendered inline at the point of change.

Large diffs collapse automatically to a summary.

    src/decoder.py   +18 -4

Selecting the summary expands the full diff.


## 8. Permission / Confirmation Prompt

Privileged operations use a dedicated confirmation surface.

The visual treatment SHALL remain the same compact terminal card style from the
existing design.

    ┌─ Permission Required ───────────────────────────────────┐
    │                                                          │
    │ ClaireCoder wants to run:                                │
    │                                                          │
    │   $ rm src/decoder_v1_deprecated.py                      │
    │                                                          │
    │ [y] yes      [n] no                                      │
    │ [a] yes, always this session   [d] diff                 │
    │                                                          │
    │ Claire:                                                  │
    │   This will permanently delete the file.                │
    │   Are you sure?                                          │
    │                                                          │
    │                 (Esc to cancel)                         │
    └──────────────────────────────────────────────────────────┘

The TUI displays Permission Engine decisions. It does not make authorization
decisions itself.


## 9. Claire Identity Layer

The terminal retains Claire as a textual persona.

The standard presentation is:

    Claire:
        Streaming decode support added with a safe fallback.
        All tests are passing.
        What would you like to work on next?

The terminal SHALL NOT render:

    - the graphical Claire mascot
    - mascot state images
    - mascot sprite sheets
    - half-block Claire reconstruction
    - terminal image protocol Claire rendering
    - [Claire IDLE]
    - [Claire WORKING]
    - internal mascot state names

This is a terminal-only decision.

The canonical graphical Claire remains part of the Desktop GUI.


## 10. Startup / Loading Screen

The terminal SHALL retain the same branded startup concept but without
graphical Claire artwork.

    ╔══════════════════════════════════════════════════════╗
    ║                                                      ║
    ║             CLAIRECODER                              ║
    ║             Engineering. Automated.                 ║
    ║                                                      ║
    ║ Initializing ClaireCoder Engine...                   ║
    ║                                                      ║
    ║ > Loading configuration                    [ OK ]    ║
    ║ > Connecting model gateway                 [ OK ]    ║
    ║ > Registering tools                        [ OK ]    ║
    ║ > Preparing workspace                      [ OK ]    ║
    ║ > Loading skills                           [ OK ]    ║
    ║ > Starting session                         [ OK ]    ║
    ║                                                      ║
    ║ Launching... ███████████████████████████ 100%       ║
    ║                                                      ║
    ║ ┌──────────────────────────────────────────────────┐ ║
    ║ │    "Let's build something amazing together."     │ ║
    ║ │                                   - Claire       │ ║
    ║ └──────────────────────────────────────────────────┘ ║
    ╚══════════════════════════════════════════════════════╝

The startup sequence SHOULD be brief and skippable.


## 11. Optional File Tree

Ctrl+T opens the file tree.

The visual style SHALL remain the same compact bordered presentation.

    ┌─ Files ─────────────────────────────────────────── x ─┐
    │                                                        │
    │ project/                                               │
    │ └─ src/                                                │
    │    ├─ decoder.py                            M          │
    │    ├─ tokenizer.py                                     │
    │    ├─ router.py                             +          │
    │    └─ utils.py                                         │
    │ └─ tests/                                              │
    │    ├─ test_decoder.py                       M          │
    │    └─ test_router.py                                   │
    │ └─ docs/                                               │
    │ README.md                                              │
    │ pyproject.toml                                         │
    │                                                        │
    │ M modified   + new   plain = untouched                 │
    └────────────────────────────────────────────────────────┘

The file tree is OFF by default.


## 12. Review / Changes View

Ctrl+R opens the session change review.

    ┌─ Changes this session ───────────────────────────── x ─┐
    │                                                        │
    │ src/decoder.py               +18 -4                    │
    │ src/router.py                +6 -0   (new)             │
    │ tests/test_decoder.py        +22 -0                    │
    │                                                        │
    │ ------------------------------------------------------ │
    │ 3 files changed                                        │
    │ 46 insertions(+)                                       │
    │ 4 deletions(-)                                         │
    │                                                        │
    │ [enter] view diff   [c] commit   [q] back              │
    │                                                        │
    │ Press enter on a file to view full diff                │
    └────────────────────────────────────────────────────────┘

The review view is presentation-only and reflects repository/session state from
the underlying system.


## 13. Task / Workflow View

Ctrl+P opens the optional workflow view.

    ┌─ Current Workflow ───────────────────────────────── x ─┐
    │                                                        │
    │ 1   Understand objective                     ✓         │
    │ 2   Plan changes                             ✓         │
    │ 3   Implement changes                        ▶         │
    │ 4   Verify                                   ○         │
    │ 5   Complete                                 ○         │
    │                                                        │
    │ Task Progress                                          │
    │ ████████████████░░░░░░░░░░░░░░░░░░░░░░  40%            │
    │                                                        │
    │ Objective:                                             │
    │ Add streaming decode support with                      │
    │ interrupt capability.                                  │
    └────────────────────────────────────────────────────────┘

The TUI displays workflow state from the Workflow subsystem. It does not
maintain its own workflow state machine.


## 14. Command Palette

`?` opens the command/shortcut palette.

    ┌─ Commands ───────────────────────────────────────── x ─┐
    │                                                        │
    │ APPLICATION / INTERACTION                              │
    │ /help         Show help                                │
    │ /status       Show status                              │
    │ /model        Switch model                             │
    │ /mode         Switch mode                              │
    │ /session      Session menu                             │
    │ /plan         Show current plan                        │
    │ /pause        Pause execution                          │
    │ /resume       Resume execution                         │
    │ /cancel       Cancel execution                         │
    │ /clear        Clear screen                             │
    │ /exit         Exit ClaireCoder                         │
    │                                                        │
    │ UI / PRESENTATION                                      │
    │ /tree         Toggle file tree                         │
    │ /review       Review changes                           │
    │ /compact      Toggle compact mode                      │
    │                                                        │
    │        Type / or ? to open this menu                   │
    └────────────────────────────────────────────────────────┘

The command palette routes application/interaction commands through the
existing Interaction Layer.

UI/presentation commands operate within the TUI presentation layer.


## 15. Interaction Input States

- **NORMAL** — Prompt accepts normal user input.
- **STREAMING** — Agent output is streaming.
- **CONFIRMATION** — Permission confirmation owns keyboard focus.
- **OVERLAY** — File tree, review, workflow, or command palette owns keyboard
  focus.
- **INTERRUPTED** — The active operation was interrupted and control returns to
  the interaction layer.
- **EXITING** — The TUI is shutting down cleanly.

The TUI must not create its own engineering/execution state machine from these
states.


## 16. Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+C` | Interrupt the active engineering operation through the existing Interaction / Execution boundaries |
| `Ctrl+T` | Toggle file tree |
| `Ctrl+R` | Review session changes |
| `Ctrl+P` | Toggle workflow/task view |
| `?` | Open command palette/help |
| `Enter` | Submit prompt in normal input. Open/expand the selected item when an overlay has focus |
| `Esc` | Apply the active surface's UI close/cancel behavior |

The TUI MUST NOT treat `Esc` and `Ctrl+C` as equivalent operations.

`Esc` is UI-level.

`Ctrl+C` is engineering-operation interruption.


## 17. Terminal Esc Semantics

File Tree:

    Esc
        Close the File Tree and return to the Main TUI.
        No engineering side effect occurs.

Task / Workflow View:

    Esc
        Close the Task / Workflow view and return to the Main TUI.
        No engineering side effect occurs.

Command Palette:

    Esc
        Close the Command Palette and return to the Main TUI.
        No engineering side effect occurs.

Permission:

    Esc
        Cancel the pending permission interaction.

Review:

    Esc
        Back out of the active review interaction according to its current
        state.

        If a pending review action exists, it is discarded/cancelled according
        to the active review behavior.

Esc SHALL NOT interrupt Engineering execution.


## 18. Modes of Operation

### Full TUI

Default interactive mode with:

    - transcript
    - activity
    - diffs
    - confirmations
    - advanced views
    - status bar
    - Claire text/persona

No graphical mascot rendering is required.

### Compact TUI

Reduces verbose output and optional visual chrome while preserving core
interaction.

Claire remains a text persona.

### Minimal TUI

Removes optional panes while retaining:

    - transcript
    - prompt
    - commands
    - permission interaction

### Non-interactive / CI mode

No interactive overlays or interactive confirmation surfaces.

Output is structured and log-friendly.


## 19. Color / Visual Language

| Element | Meaning |
|---|---|
| Cyan / teal | ClaireCoder primary UI / tool activity |
| Pink / magenta | Claire identity and secondary accent |
| Green `+` / check | Added content / success |
| Red `-` / error | Removed content / failure |
| Yellow | Pending confirmation / warning |
| Dim grey | Collapsed or secondary output |
| Cyan `●` / state glyph | Tool or agent activity marker |

The palette remains restrained and dark-terminal-first.

Semantic meaning SHALL NOT depend solely on color.


## 20. Interaction Rules

1. The Prompt remains visually anchored at the bottom during normal streaming
   output.
2. Agent output streams above the Prompt.
3. The Prompt is suspended when Permission or another focused UI interaction
   owns keyboard input.
4. Long Tool output is collapsed automatically.
5. Large diffs collapse to summaries.
6. Permission prompts interrupt the active flow and clearly identify the
   requested operation.
7. The user can interrupt long-running operations with `Ctrl+C`.
8. All displayed state is read from the approved ClaireCoder architecture.
9. The TUI never performs Tool execution directly.
10. The TUI never makes Permission decisions directly.
11. The TUI never owns Workflow, Execution, or Verification state.


## 21. Architecture Boundary

The intended presentation path is:

    ClaireCoder CLI / TUI
            ↓
    InteractionController
            ↓
    ClaireCoderV1
            ↓
    Existing V1 subsystems

The TUI is a presentation/input layer only.

It must not become another orchestration engine.

It must use approved public interfaces.

It must not access private subsystem state.


## 22. CLI / TUI Shared Behavior

The CLI and TUI SHALL share:

    - command semantics
    - session semantics
    - mode semantics
    - permission semantics
    - application lifecycle semantics
    - engineering result semantics

They MAY differ in:

    - presentation
    - rendering
    - input mechanics
    - output formatting

Shared behavior SHALL remain below the frontend boundary.


## 23. Testing Strategy

The TUI test suite SHALL cover:

    - rendering
    - prompt handling
    - input focus
    - input states
    - activity rendering
    - diff rendering
    - permission presentation
    - Claire text/persona rendering
    - file tree
    - review view
    - Workflow view
    - command palette
    - keyboard shortcuts
    - terminal adaptation
    - fallback modes
    - Esc semantics

The TUI SHALL NOT require:

    - graphical mascot assets
    - terminal image protocols
    - real model credentials

for ordinary unit tests.

Integration testing SHALL cover:

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


## 24. Design Invariants

The following are locked:

    1. Terminal-first interaction.
    2. Existing TUI visual appearance remains authoritative.
    3. Compact terminal proportions remain the reference.
    4. Terminal does not render graphical Claire artwork.
    5. CLAIRECODER remains terminal brand identity.
    6. Claire remains textual persona in the terminal.
    7. No terminal image protocol is required.
    8. Prompt placement remains unchanged.
    9. Activity presentation remains unchanged.
    10. Diff presentation remains unchanged.
    11. Permission presentation remains unchanged except for mascot removal.
    12. File Tree presentation remains unchanged.
    13. Review presentation remains unchanged.
    14. Task presentation remains unchanged.
    15. Command Palette presentation remains unchanged.
    16. Esc remains UI-level behavior.
    17. Ctrl+C remains engineering-operation interruption.
    18. CLI/TUI remain thin frontend layers.
    19. Engineering ownership remains below the frontend.
    20. Desktop owns the graphical Claire experience.
    21. Terminal and Desktop may differ visually while sharing application
        semantics.
    22. Terminal SHALL NOT be redesigned because the mascot has been removed.


## 25. Relationship With Desktop GUI

The graphical Claire identity SHALL be implemented by the Desktop GUI.

Desktop requirements are defined by:

    CC-PRD-012
    CC-ADR-008
    DESKTOP-DESIGN.md

The Desktop GUI SHALL support:

    - graphical Claire
    - nine mascot states
    - rich visual composition
    - view replacement
    - graphical permission interaction

The terminal SHALL remain:

    - terminal-native
    - compact
    - text-persona based
    - graphical-mascot independent

Both frontends SHALL consume the same approved application and interaction
semantics.


## 26. Terminal Size Adaptation

The compact TUI representation is the design reference for ordinary IDE
terminals.

Recommended reference geometry:

    approximately 96 columns × 30 rows

This is a design target, NOT a hard terminal requirement.

The implementation SHALL adapt to available space.

Recommended hierarchy:

    96+ columns
        Full TUI composition

    approximately 76–95 columns
        Compact presentation

    below approximately 76 columns
        Minimal presentation

The application SHALL NOT force the terminal to resize.

The user controls the terminal size.


## 27. V1 Design Lock

This document and:

    ClaireCoder-TUI-Design-V1.png

together define the terminal visual reference.

The appearance remains locked.

The following remain unchanged from the previous design:

    - dark terminal canvas
    - cyan/teal primary language
    - restrained pink/magenta accents
    - thin borders
    - monospace hierarchy
    - compact terminal proportions
    - activity layout
    - diff layout
    - permission surface
    - File Tree
    - Review
    - Task
    - Command Palette
    - prompt placement
    - shortcut footer
    - keyboard interaction

The only intentional identity change is:

    graphical Claire mascot
        →
    removed from terminal

and:

    Claire mascot identity
        →
    CLAIRECODER branding + Claire text persona

The Desktop GUI retains the full graphical Claire identity.


## 28. Implementation Constraint

Implementation SHALL NOT:

    - redesign the terminal layout
    - widen the terminal composition unnecessarily
    - add graphical mascot rendering
    - add terminal image protocol requirements
    - replace the compact reference with a large dashboard
    - change command ownership
    - bypass InteractionController
    - bypass PermissionEngine
    - own Workflow/Execution/Verification state
    - silently modify the locked visual hierarchy

The implementation SHALL preserve the existing terminal appearance and density
while applying only the explicitly approved terminal identity changes.


###############################################################################

END OF TUI-DESIGN.md

###############################################################################