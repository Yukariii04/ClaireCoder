# ClaireCoder V1 — Project Memory

## 1. System Architecture & Core Invariants

ClaireCoder is a **modular, backend-agnostic software engineering agent** within the Claire Ecosystem.

### Core Subsystems (CC-ADR-001)

| Subsystem | Responsibility |
|---|---|
| **Engineering Engine** | Central orchestration coordinating all operational subsystems |
| **Model Gateway** | Provider-independent model execution and capability negotiation boundary |
| **Context Engine** | Relevance-based information assembly for model requests |
| **Workflow & Planning** | Adaptive task decomposition, dependency resolution, and execution control |
| **Tool Ecosystem** | Executable engineering capabilities (filesystem, terminal, Git, diagnostics) |
| **Workspace Sandbox** | Safe, project-root-bounded filesystem access and mutation tracking |
| **Skill System** | Reusable expertise, methodology, and instructions |
| **Permission Engine** | Centralized ALLOW / ASK / DENY authorization boundary |
| **Engineering Session** | Persistent state of ongoing engineering tasks |
| **Command System** | Explicit user-invoked operations (slash commands, CLI parameters) |
| **Interaction Layer** | CLI / TUI user-facing presentation and interactive input capture |

### Key Architectural Invariants
- **Model → Permission bypass**: FORBIDDEN
- **Model → Execution-state mutation**: FORBIDDEN
- **Model → Verification authority**: FORBIDDEN (model claims do not prove correctness)
- **Tool → Permission bypass**: FORBIDDEN
- **Interface → Engineering Engine replacement**: FORBIDDEN
- **Model Gateway SHALL NOT depend on Engineering Engine**
- **Tools SHALL NOT control Workflow state**
- **Skills SHALL NOT bypass Permission Engine**
- **Single Execution Owner**: `AgentRuntime` owns the execution lifecycle; roles, tools, and UI adapt to it.
- **Verification Authority**: Only structured verification gates determine task success.
- **Filesystem Confinement**: Tools only mutate within authoritative workspace boundaries.

### Technology & Constraints
- **Language**: Python 3.10+
- **V1 Target**: Local CLI / TUI coding agent (Windows / Linux / macOS)
- **Zero Heavy Infrastructure**: No microservices, distributed databases, vector DBs, or Kubernetes.

### Document Chain
```
RFD (9 docs) → RES (8 docs) → ADR (6 docs) → PRD (10 docs) → IMPLEMENTATION
```

---

## 2. Authoritative Repository State

- **Active Milestone**: CLI / TUI Stage 7 Correction #22 (Provider Reliability) Completed and Verified.
- **Baseline Test Suite Status**: **1038 passed, 0 failures, 0 errors, 0 warnings** (`pytest -W error`).
- **Milestone Scope**: All 22 Corrections of Stage 7 implemented, verified, and integrated without regressions.
- **Repository Health**: Clean working tree, zero compiler/lint warnings, zero open technical debt.
- **Next Authorized Action**: Absolute STOP. Await user review and explicit authorization before proceeding to Correction #23 or next milestone.

---

## 3. Subsystem Architecture & Boundary Model

The active codebase enforces strict separation of concerns across dedicated packages:

```
clairecoder/
├── core/             # Fundamental domain types, event models, and abstract interfaces
├── gateway/          # Provider-agnostic model routing, adapters (Anthropic, Gemini, Ollama, OpenAI-compatible), CredentialStore
├── context/          # Immutable token budgeting, relevant context assembly, and workspace instruction discovery
├── workflow/         # TaskGraph (DAG dependencies, failure blocking), Task models, schema-driven Planner
├── runtime/          # AgentRuntime orchestrator, EventEmitter, RuntimeEvent protocol, AgentRun, RoleRegistry
├── session/          # Session models, SessionStatus, atomic JSON SessionStore, schema versioning, checkpointing & resume
├── workspace/        # Workspace sandbox, path safety enforcement, ChangeTracker, directory safety limits
├── tools/            # Tool abstraction, ToolResult model, deterministic ToolRegistry, core filesystem/terminal tools
├── changeset/        # ChangeSet, ChangedFile, unified diff generation, ChangeSetStore
├── verification/     # Verifier interface, DefaultVerifier, VerificationResult, VerificationEngine
├── permissions/      # Centralized permission policy enforcement, pending invocation tracking
└── tui/              # Pure Python terminal presentation, TranscriptView, ActivityMapper, ActivityEvent, overlays
```

---

## 4. Stage 7 Evolutionary Architecture (Corrections #1 – #20)

### Stage 7 Baseline — Multi-Provider Configuration, Credentials & Bootstrap
- Multi-provider architecture supporting OpenAI, Groq, Anthropic, Google Gemini, OpenRouter, OmniRoute, Ollama, LM Studio, vLLM, and custom endpoints.
- Native adapters for Anthropic (`AnthropicAdapter`), Google Gemini (`GeminiAdapter`), Ollama (`OllamaAdapter`), and unified OpenAI-compatible (`OpenAICompatibleAdapter`).
- OS-level credential management (`CredentialStore`) using platform-native keyring (Windows Credential Manager) — zero plaintext secrets in storage or logs.
- Interactive TUI Setup Wizard (`SetupWizard`) with 9 sequential configuration stages and capability inference heuristics.

### Correction #1 — Live TUI Workflow Integration, State Sync & Streaming
- Real background execution thread for natural-language prompts without blocking TUI event loop.
- Incremental streaming chunks (`STREAMING_CHUNK` / `RESPONSE_COMPLETE`) updating transcript activities in place via stable correlation keys.
- Authoritative header projection synchronizing model, directory, mode, and token context usage (`1.2k/32.8k`).

### Correction #2 — Real Engineering Agent Workflow & Single-Owner Rendering
- Natural language prompts route through real engineering loop: Prompt → `EngineeringEngine` → `Planner` → `WorkflowManager` → `ExecutionManager` → Tools → `Verifier`.
- Implemented real I/O tools (`ReadFileTool`, `WriteFileTool`, `ReplaceFileContentTool`, `ListDirTool`, `DeleteFileTool`, `SearchTool`, `TerminalTool`).
- Zero-subprocess native Win32 clipboard paste (`OpenClipboard`, `GetClipboardData`).
- Thread-safe single-owner terminal rendering via `_event_queue` eliminating terminal race conditions.

### Correction #3 — Runtime State Integrity, Geometry & Test Consolidation
- Authoritative model propagation: `ConfigurationManager` → `ProviderProfile` → `ModelProfile` → `ModelGateway` → `Engine`. Removed unsafe fallbacks.
- Card geometry invariants: top/body/bottom borders strictly match `terminal_width`.
- Consolidated historical test suite files into clean, maintainable subsystem suites.

### Correction #4 — Provider Discovery / Validation & Atomic Profiles
- User-Agent normalization (`ClaireCoder/1.0`) preventing Cloudflare WAF 403 blocks.
- Lightweight reachability checks (`validate_provider`) separated from model parsing (`discover_models`).
- Atomic `(provider_profile_id, model_id)` configuration pairs in `active.json` allowing multi-provider profile coexistence.
- Live `/model` command switching with execution guards blocking changes during active agent runs.

### Correction #5 — Keyring Recovery, Wizard Boundary & Exit Integrity
- Pre-flight verification of OS keyring backend health (`CredentialStore.check_backend_health`).
- Decoupled wizard synchronization via `register_runtime_sync_callback`.
- Exit state management (`TuiApplication.stop`) preventing double cleanups and trailing ghost frames.

### Correction #6 — Windows Credential Usability & Interaction Router
- Explicit auto-recovery of `WinVaultKeyring` on Windows.
- Deterministic heuristic interaction router classifying conversational intents vs engineering workflows.
- Real `/mode` command semantics enforcing read-only policies in Plan and Review modes.
- Leaked tool-call JSON filtering stripping raw function payloads from transcripts.

### Correction #7 — Input/Task Viewports, Model Selector & Bounded Replanning
- Cursor-following horizontal scrolling viewport (`PromptInput.render_line`).
- Multiline wrapping and viewport scrolling for complex objectives (`TaskViewOverlay`).
- Interactive two-level provider-to-model selector overlay (`ModelSelectorOverlay`).
- Bounded replanning budget (`max_replans = 2`) preventing infinite failure loops.

### Correction #8 — Live TUI Viewports & Windows Terminal Integrity
- Word-boundary wrapping for agent transcript responses respecting terminal width.
- Keyboard input dispatching and Esc back-stack navigation for overlays.
- Dynamic terminal size detection (`shutil.get_terminal_size`) adapting across 40–160 column widths.

### Correction #9 — Authoritative Run State Machine (`AgentRun`)
- Single-owner execution lifecycle (`AgentRun`, `RunState`: `PENDING`, `RUNNING`, `PAUSED`, `SUCCEEDED`, `FAILED`, `CANCELLED`).
- Cooperative cancellation propagation across loops, streaming chunks, tool execution, and engine tasks.
- Execution boundary mode policy enforcement (`ToolExecutor.set_mode_policy`) blocking unauthorized disk mutations.

### Correction #10 — Real Agent Behavior, Tool Safety, Canonical Messages & Budgeting
- Permission resume: `PendingToolInvocation` records arguments and resumes execution on approval without rerunning.
- Canonical workspace path resolution (`resolve_workspace_path`) rejecting traversal escapes (`../`, symlinks) with `WorkspaceSecurityError`.
- Removal of false-success semantics: missing files, failed linters, and empty git operations return explicit failure states.
- Unified diff generation attached to `ToolResult.metadata["diff"]` on all file modifications.
- Provider-neutral message history (`AgentMessage`) with canonical provider schema transformations.
- Streaming tool-call accumulator reconstructing fragmented JSON across chunks.
- Multi-boundary operational budget (`AgentBudget`) tracking step, token, and tool-call limits with loop detection.

### Correction #11 — Runtime State & Activity Consistency
- Coherent runtime state synchronization between `AgentRun`, `InteractionController`, and `TuiApplication`.
- Clean error boundary mapping preventing internal exception leaks to terminal frame.

### Correction #12 — Structured Runtime Event Protocol & EventEmitter
- Standardized typed event protocol (`RuntimeEvent`, `EventType`) replacing loose string dictionaries.
- Decoupled publish/subscribe architecture via `EventEmitter`.
- Stable correlation IDs (`run_id`, `task_id`, `tool_call_id`) tracking end-to-end event lifecycles.
- Legacy event translation bridge (`EngineBridge`) and non-invasive `RuntimeEventTuiListener`.

### Correction #13 — Real Structured Task Graph
- Enriched `Task` model with semantic intent: `title`, `type` (`TaskType`), `inputs`, `expected_outputs`, `validation`, `attempts`, `failure_evidence`.
- Deterministic DAG management via `TaskGraph`: dependency validation, cycle rejection, and topological ready calculation.
- Monotonic failure propagation: dependent tasks transition to `BLOCKED` when prerequisites fail.
- Re-trying a task unblocks dependent tasks back to `PENDING`.
- Schema preservation through `Planner` to `Plan` to `TaskGraph`.

### Correction #14 — Dedicated Agent Runtime Extraction
- Extracted 250-line execution loop out of `app.py` into dedicated `AgentRuntime`.
- `ClaireCoderV1` reduced to a thin composition, bootstrap, and UI coordination boundary.
- Clean execution gating: execution failure marks task `FAILED`, cascades `BLOCKED` to dependents, and strictly blocks verification.
- Verification failure sets `VALIDATION_FAILURE`, marks task `FAILED`, and strictly prevents task/run completion.
- Structured `RunResult` reporting programmatic outcomes.

### Correction #15 — Schema-Driven Structured Planner
- Schema-driven output contract (`PLAN_SCHEMA`) using `ModelRequest.structured_output_schema`.
- Pre-flight capability negotiation falling back to strict fenced-JSON parsing when models lack schema support.
- Strict plan validation (`validate_plan`) rejecting empty IDs, self-dependencies, unknown dependencies, and cycles.
- Compact DAG dependency prompting providing clear topological examples to models.

### Correction #16 — ChangeSet & Deterministic Diff Store
- First-class `ChangeSet` model recording all file creations, modifications, and deletions for an execution task.
- Zero-external-process unified diff generator producing normalized patch headers (`/dev/null` for creations/deletions).
- `WorkspaceSnapshot` and `ChangeTracker` capturing before/after file states and calculating exact line insertions/deletions.
- Binary file detection safety preventing corrupt diff generation.
- `ExecutionResult` and `RuntimeEvent` integration exposing `changeset_id` and diff metadata.

### Correction #17 — Verification as a First-Class Boundary & Bounded Recovery
- Decoupled execution success from task correctness (`Task -> Execute -> ExecutionResult -> Verify -> VerificationResult -> Recovery`).
- Elimination of false successes: an executor completing without error cannot mark a task successful without verification pass.
- Abstract `Verifier` contract and `DefaultVerifier` evaluating command exit codes, test failures, and criteria evidence.
- Extended task states: `EXECUTED` and `VERIFYING`.
- Bounded recovery budget: retries up to `max_retries` before transitioning to structured replanning or terminal failure.
- Persistent failure evidence surviving runtime lifecycle and attached to `RunResult`.

### Correction #18 — Bounded Agent Roles & Subagents Architecture
- Lightweight role abstraction (`Role`: `PLANNER`, `IMPLEMENTER`, `VERIFIER`, `RECOVERY`) separating reasoning responsibilities.
- Abstract `AgentRole` contract and concrete implementations (`PlannerRole`, `ImplementerRole`, `VerifierRole`, `RecoveryRole`).
- `RoleContext` carrying strictly bounded information without exposing raw mutable runtime internals.
- Decoupled `RoleRegistry` for swappable role resolution and test injection.
- Single orchestration authority preserved: `AgentRuntime` coordinates all roles, task graphs, state transitions, and event emissions.
- Failure containment: role exceptions captured into structured `RoleResult(success=False)` preventing false-success states.

### Correction #19 — Tool & Workspace Layer Boundary
- Dedicated `Workspace` abstraction owning all safe project-root filesystem I/O (`read_file`, `write_file`, `delete_file`, `list_files`).
- Path safety boundary (`path_safety.py`) rejecting relative escapes (`../`), drive jumps, and symlink escapes with `WorkspacePathEscapeError`.
- Structured `Tool` interface and `ToolResult` model (`success`, `output`, `error`, `duration`, `metadata`, `changed_files`, `changeset_id`).
- Core tools implemented: `ReadFileTool`, `WriteFileTool`, `DeleteFileTool`, `ListFilesTool`, `RunCommandTool`.
- Deterministic `ToolRegistry` with duplicate protection, unknown tool rejection, and test injection capabilities.
- Tasks track filesystem changes via `workspace.create_tracker()` flowing mutations directly into `ChangeSetStore`.

### Correction #20 — TUI Activity System & Stream Presentation
- Structured presentation layer replacing raw event dumps with modern coding agent UX (`ActivityStatus`, `ActivityOperation`, `ActivityEvent`).
- Clean visual markers: `●` (running), `✓` (completed), `✗` (failed).
- Concise activity stream:
  - `● Reading src/foo.py` → `✓ Read 213 lines`
  - `● Editing src/foo.py` → `✓ Editing src/foo.py \n   +12 -4`
  - `● Running pytest` → `✓ Running pytest \n   14 passed`
  - `✓ Verification passed`
- Compact execution change summary derived directly from `ChangeSet` (`N files changed +X -Y Review`).
- In-place transcript updates using stable correlation keys (`rtool_<id>`, `rcmd_<id>`, `rver_<id>`), eliminating duplicate entries between started and completed states.
- Concise error presentation: strips raw Python tracebacks and extracts salient exit codes and test failure counts.
- Strict architecture boundary: presentation layer only; zero diff, execution, or verification logic moved into the TUI.

### Correction #21 — Session / Persistence & Runtime Resume
- **Session Types (`clairecoder.session.types`)**:
  - Structured, typed data models: `Session`, `SessionStatus` (`ACTIVE`, `COMPLETED`, `FAILED`, `INTERRUPTED`), `SessionMetadata`, `SessionRunState`, `ChangeSetReference`.
  - Schema versioning (`schema_version = 1`, `CURRENT_SCHEMA_VERSION = 1`) with deterministic round-trip serialization and deserialization (`to_dict` / `from_dict`).
  - Strict error hierarchy (`clairecoder.session.errors`): `SessionError`, `SessionNotFoundError`, `SessionCorruptedError`, `UnsupportedSchemaVersionError`, `SessionStorageError`.
- **Atomic File Store (`clairecoder.session.store.SessionStore`)**:
  - Local filesystem storage layout (`.clairecoder/sessions/<session-id>.json`).
  - Atomic write strategy: temporary file in target directory -> flush -> `os.fsync` -> `os.replace`. Corrupted/interrupted writes leave existing sessions unharmed.
  - Standard store operations: `create()`, `get()`, `save()`, `list()`, `delete()`, `exists()`.
- **Runtime Persistence & Resumption (`AgentRuntime`)**:
  - Checkpoints persisted at key execution boundaries: session created, run started, task started, changeset/execution completed, verification passed/failed, recovery/replan completed, run completed/failed/interrupted.
  - Non-fatal containment: persistence failures emit `AGENT_ERROR` and log structured warnings without crashing the execution loop.
  - Resume mechanism (`AgentRuntime.resume_session`): restores `TaskGraph` state, preserves already-completed and verified tasks without re-executing them, sanitizes in-flight tasks to `READY`, and continues execution.
  - Interruption safety: `KeyboardInterrupt` / SIGINT captured to immediately checkpoint session as `SessionStatus.INTERRUPTED`, emit `SESSION_INTERRUPTED`, and preserve full resumability.
- **Event Protocol Integration**:
  - Integrated into existing `RuntimeEvent` protocol with `session_id` field and new event types: `SESSION_CREATED`, `SESSION_RESUMED`, `SESSION_CHECKPOINTED`, `SESSION_COMPLETED`, `SESSION_FAILED`, `SESSION_INTERRUPTED`.
- **CLI & TUI Integration**:
  - Added CLI flags: `--resume <SESSION_ID>`, `--list-sessions`, `--inspect-session <SESSION_ID>`.
  - TUI activity mapper displays session resume / interrupt transitions while maintaining TUI presentation-only boundary.

## 5. Phase Verification Matrix

| Phase / Milestone | Description | Status |
|---|---|---|
| **Phase 1** | Project Bootstrap & Core Types | Completed & Verified |
| **Phase 2** | Model Gateway | Completed & Verified |
| **Phase 3** | Permission Engine | Completed & Verified |
| **Phase 4** | Tool Ecosystem | Completed & Verified |
| **Phase 5** | Skill System | Completed & Verified |
| **Phase 6** | Context Engine | Completed & Verified |
| **Phase 7** | Engineering Session State | Completed & Verified |
| **Phase 8** | Workflow & Planning | Completed & Verified |
| **Phase 9** | Execution Manager | Completed & Verified |
| **Phase 10** | Engineering Engine Orchestration | Completed & Verified |
| **Phase 11** | Verification & Validation Engine | Completed & Verified |
| **Phase 12** | V1 Integration & Application Boundary | Completed & Verified |
| **CLI / TUI Stage 1–4** | Terminal Foundations, Layout & Overlays | Completed & Verified |
| **CLI / TUI Stage 5** | Terminal Experience Finalization | Completed & Verified |
| **CLI / TUI Stage 6** | CLI Completion & Workspace Tree Discovery | Completed & Verified |
| **Stage 7 Baseline** | Multi-Provider Configuration & Credentials | Completed & Verified |
| **Stage 7 Corrections #1–#10** | Live TUI Workflow, Tools, Permissions, RunState & Boundaries | Completed & Verified |
| **Stage 7 Correction #11** | Runtime State & Activity Consistency | Completed & Verified |
| **Stage 7 Correction #12** | Structured Runtime Event Protocol & EventEmitter | Completed & Verified |
| **Stage 7 Correction #13** | Structured Task Graph & Semantic Task Model | Completed & Verified |
| **Stage 7 Correction #14** | Agent Runtime Extraction & Clean Execution Lifecycle | Completed & Verified |
| **Stage 7 Correction #15** | Schema-Driven Structured Planner & Compact DAG Prompting | Completed & Verified |
| **Stage 7 Correction #16** | ChangeSet / Diff Store & Workspace ChangeTracker | Completed & Verified |
| **Stage 7 Correction #17** | Verification as First-Class Boundary & Bounded Recovery | Completed & Verified |
| **Stage 7 Correction #18** | Bounded Agent Roles & Subagents Architecture | Completed & Verified |
| **Stage 7 Correction #19** | Tool & Workspace Layer Boundary | Completed & Verified |
| **Stage 7 Correction #20** | TUI Activity System & Stream Presentation | Completed & Verified |
| **Stage 7 Correction #21** | Session / Persistence State & Runtime Resume | Completed & Verified |

---

## 6. Artifact Ledger

- `Phase_CLI_TUI_Stage_7_Correction_21.zip`
- `Phase_CLI_TUI_Stage_7_Correction_20.zip`
- `Phase_CLI_TUI_Stage_7_Correction_19.zip`
- `Phase_CLI_TUI_Stage_7_Correction_18.zip`
- `Phase_CLI_TUI_Stage_7_Correction_17.zip`
- `Phase_CLI_TUI_Stage_7_Correction_16.zip`
- `Phase_CLI_TUI_Stage_7_Correction_15.zip`
- `Phase_CLI_TUI_Stage_7_Correction_14.zip`
- `Phase_CLI_TUI_Stage_7_Correction_13.zip`
- `Phase_CLI_TUI_Stage_7_Correction_12.zip`

---

## 7. Documentation Baseline Lock (2026-08-18)

- **Status**: All 9 authoritative frontend documents finalized to FINAL.
- **Model Gateway**: CC-PRD-002 (v2.0.0 FINAL), CC-ADR-002 (v2.0.0 FINAL).
- **Terminal**: CC-PRD-011 (v2.0.0 FINAL), CC-ADR-007 (v2.0.0 FINAL), TUI-DESIGN.md (FINAL).
- **Desktop**: CC-PRD-012 (v1.0.0 FINAL), CC-ADR-008 (v1.0.0 FINAL), DESKTOP-DESIGN.md (v1.0.0 FINAL).
- **Roadmap**: CLI-TUI-DESKTOP-ROADMAP.md (v2.1.0 FINAL).
