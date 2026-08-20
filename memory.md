# ClaireCoder V1 — Project Memory

## Architecture Overview

ClaireCoder is a **modular, backend-agnostic software engineering agent** within the Claire Ecosystem.

### Core Components (CC-ADR-001)

| Component | Responsibility |
|---|---|
| **Engineering Engine** | Central orchestration — coordinates all subsystems |
| **Model Gateway** | Provider-independent model execution boundary |
| **Context Engine** | Relevance-based information assembly for model calls |
| **Workflow & Planning** | Adaptive task decomposition and execution control |
| **Tool Ecosystem** | Executable engineering capabilities (filesystem, terminal, Git, etc.) |
| **Skill System** | Reusable expertise, methodology, and instructions |
| **Permission Engine** | Centralized ALLOW/ASK/DENY authorization boundary |
| **Engineering Session** | Persistent state of ongoing engineering tasks |
| **Command System** | Explicit user-invoked operations |
| **Interaction Layer** | CLI/TUI user-facing interface |
| **Extension Layer** | Third-party Skills, MCP, external Tools |

### Key Architectural Invariants
- Model → Permission bypass: **FORBIDDEN**
- Model → Execution-state mutation: **FORBIDDEN**
- Model → Verification authority: **FORBIDDEN**
- Tool → Permission bypass: **FORBIDDEN**
- Interface → Engineering Engine replacement: **FORBIDDEN**
- Model Gateway SHALL NOT depend on Engineering Engine
- Tools SHALL NOT control Workflow state
- Skills SHALL NOT bypass Permission Engine

### Technology
- **Language**: Python
- **V1 Target**: CLI/TUI coding agent
- **No**: microservices, distributed databases, vector databases, Kubernetes

## Document Chain

```
RFD (9 docs) → RES (8 docs) → ADR (6 docs) → PRD (10 docs) → IMPLEMENTATION
```

## Repository State
- **Current**: CLI / TUI Stage 6 (Correction #10: Real Workspace File Tree + Interactive Tree Navigation + Direct Secondary-View Navigation + Slash Command Suggestions) completed.
- **Completed**: Phase 1-12, CLI / TUI Stage 1, CLI / TUI Stage 2, CLI / TUI Stage 3, CLI / TUI Stage 4, CLI / TUI Stage 5, CLI / TUI Stage 6 (CLI Completion + Corrections #1-#10).
- **CLI / TUI Stage 6 Correction #10**:
  - Real workspace filesystem discovery via `scan_workspace()` with directories-first/alphabetical ordering and safety bounds (`_MAX_DEPTH=8`, `_MAX_ENTRIES_PER_DIR=200`, `_IGNORED_DIRS`).
  - Normalised `FileTreeItem` data model (`name`, `path`, `is_directory`, `children`, `status`, `expanded`).
  - Interactive Tree Navigation: workspace root starts expanded, child dirs start collapsed, visible flattened list derived dynamically from expansion state.
  - Selection indicator (`▶ ` / `  `) and directory expansion glyphs (`▾ ` / connectors `├─ ` / `└─ `).
  - Fixed internal viewport scrolling (`viewport_height = 10`, card height = 16 rows) with auto-scrolling to keep selection visible; outer TUI frame never grows.
  - Tree keyboard navigation hints in footer (`↑/↓ select  Enter expand/collapse  ←/→ tree`, `PgUp/PgDn scroll   Esc back`).
  - Direct Secondary-View Navigation (`Ctrl+T`, `Ctrl+R`, `Ctrl+P`) dispatched with global priority across Main, Tree, Review, Task, and Palette without requiring `Esc`.
  - Secondary view focus ownership: secondary views absorb printable keys so typing never leaks into Main prompt.
  - Contextual Slash Command Suggestions: popup opens on `/` in command-token position, prefix filtering, slash+space and command+space rules close suggestions, normal prose ignores slashes, Up/Down navigation, Enter accepts suggestion into prompt, Esc dismisses popup.
- **Test Count**: 507 passed, 1 skipped, 0 failures, 0 errors, 0 warnings (`pytest -W error`).
- **Target**: AWAIT AUTHORIZATION TO PROCEED TO STAGE 7.

### Current State
- **Active Stage**: CLI / TUI Stage 6 (Correction #10: Interactive File Tree, Direct Navigation, Slash Suggestions) Completed.
- **Next Steps**: Await authorization to proceed to Stage 7 — Multi-Provider Configuration / Credential / Bootstrap.

### Phase Status
- **Phase 1-12**: Completed and Approved.
- **CLI / TUI Stage 1-4**: Completed and Approved.
- **CLI / TUI Stage 5 (Terminal Experience Finalization)**: Completed and Approved.
- **CLI / TUI Stage 6 (CLI Completion + Correction #10)**: Completed and Verified.

### Recent Artifacts
- `Phase_CLI_TUI_Stage_6_Correction_10.zip`
- `phase_cli_tui_stage_6_correction_10_report.md`

### Documentation Baseline Lock (2026-08-18)
- **Status**: All 9 authoritative frontend documents finalized to FINAL.
- **Model Gateway**: CC-PRD-002 (v2.0.0 FINAL), CC-ADR-002 (v2.0.0 FINAL).
- **Terminal**: CC-PRD-011 (v2.0.0 FINAL), CC-ADR-007 (v2.0.0 FINAL), TUI-DESIGN.md (FINAL).
- **Desktop**: CC-PRD-012 (v1.0.0 FINAL), CC-ADR-008 (v1.0.0 FINAL), DESKTOP-DESIGN.md (v1.0.0 FINAL).
- **Roadmap**: CLI-TUI-DESKTOP-ROADMAP.md (v2.1.0 FINAL).
- **Next Authorized Stage**: Stage 7 — Multi-Provider Configuration / Credential / Bootstrap.
