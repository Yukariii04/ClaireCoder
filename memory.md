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
- **Current**: Phase 7 completed. Awaiting authorization for Phase 8.
- **Completed**: Phase 1 (Core), Phase 2 (Gateway), Phase 3 (Permissions), Phase 4 (Tools), Phase 5 (Skills), Phase 6 (Context Engine), Phase 7 (Engineering Engine)

## Audit Status: COMPLETE (2026-08-09)
See update.md for full history.

### Phase 7 Architectural Decisions
- **Session Persistence**: Implemented via simple JSON local files. No distributed DBs.
- **Subagent Interface**: Handled via SubagentEngine isolating state mutation and bounding objectives.
- **Workflow Boundaries**: Workflow replanning is pushed to boundary signals (EngineEvent.REPLANNING_STARTED), rather than executed within the EngineeringEngine.

## Repository State
- **Current**: Phase 10 (Interaction Layer) Correction #1 completed. Awaiting authorization for Phase 11.
- **Completed**: Phase 1 (Core), Phase 2 (Gateway), Phase 3 (Permissions), Phase 4 (Tools), Phase 5 (Skills), Phase 6 (Context Engine), Phase 7 (Engineering Engine), Phase 8 (Workflow Planning), Phase 9 (Execution State), Phase 10 (Interaction Layer)
- **Phase 10 Correction**: Fixed InteractionMode to match PRD §16 (PLAN/IMPLEMENT/REVIEW/DEBUG), added all V1 commands per PRD §11, fixed malformed-command handling per PRD §13.
- **Phase 10 Test Count**: 26 interaction tests, 229 total, 0 warnings.
- **Phase 11 (Testing & Verification)**: PENDING.
- **Phase 12 (Integration/V1)**: PENDING.
