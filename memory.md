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
- **Current**: CLI / TUI Stage 7 Correction #12 (Structured Runtime Event Protocol + EventEmitter Pub/Sub + Correlation IDs + EngineBridge Legacy Translation + RuntimeEventTuiListener + File/Command/Verification Event Extraction) completed.
- **Completed**: Phase 1-12, CLI / TUI Stage 1-6 (Corrections #1-#10), Stage 7 (Corrections #1-#12).

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
- **Stage 7 — Multi-Provider Configuration / Credential / Bootstrap**:
  - Multi-provider architecture supporting OpenAI, Groq, Anthropic, Google Gemini, OpenRouter, OmniRoute, Ollama, LM Studio, vLLM, and Custom endpoints simultaneously.
  - Native adapters for Anthropic (`AnthropicAdapter`) and Google Gemini (`GeminiAdapter`); native local adapter for Ollama (`OllamaAdapter`); unified OpenAI-compatible family adapter (`OpenAICompatibleAdapter`).
  - OS-level secure credential management (`CredentialStore`) using platform-native keyring (Windows Credential Manager) — zero secrets in plaintext/logs/transcript.
  - Persistent provider profile and active model management (`ConfigurationManager`) stored in `.clairecoder/config/`.
  - Unified model discovery service (`discover_models`) with automatic capability inference heuristics (`text`, `tool_calling`, `vision`, `reasoning`, `structured_output`, `streaming`).
  - Interactive TUI Setup Wizard (`SetupWizard`) with 9 sequential stages: provider selection, credential entry, validation, model discovery, scrollable model picker with capability badges, capability breakdown, skill selection, summary, and secure persistence.
  - Real `/model` command with model inspection, capabilities display, and active profile switching.
  - Bootstrap flow populates ModelGateway from disk configuration; header updates with active model.
- **Stage 7 Correction #1 — Live TUI Workflow Integration + Runtime State Synchronization + Header State + Real /model + /mode + Bootstrap Timing**:
  - **Live Workflow Execution**: Natural language prompt submission triggers real asynchronous model workflow execution in a background thread without blocking the TUI event loop.
  - **Incremental Streaming Response**: Streamed model response chunks (`STREAMING_CHUNK` / `RESPONSE_COMPLETE`) dynamically update the transcript activity in place via stable `correlation_key` and trigger immediate visual redraw.
  - **Authoritative Header Projection**: TUI header is an authoritative reflection of application runtime state (`directory`, `model`, `mode`, `session`, `task_progress`, `context_usage`), synchronizing via engine events (`MODEL_SWITCHED`, `MODE_CHANGED`) and runtime state.
  - **Live Mode Switching (`/mode`)**: Switching modes via `/mode` updates `InteractionController.mode` and emits `MODE_CHANGED` event to update the TUI header immediately.
  - **Live Model Switching (`/model`)**: Command `/model` displays real registered models, providers, and capabilities; `/model <model_id>` switches the active runtime model and emits `MODEL_SWITCHED` event to update the TUI header and context capacity.
  - **Minimum Boot Screen Timing**: Guaranteed minimum 3.5s human-visible loading screen presentation during live terminal execution while remaining instantaneous for scripted tests.
  - **Token Tracking & Context Formatting**: Tracks token usage from model responses and dynamically displays context usage (e.g. `1.2k/32.8k`).
- **Stage 7 Correction #2 — Real Engineering-Agent Workflow + Clipboard Paste + Wizard Validation + Single-Owner Rendering + TUI Geometry / Alignment Integrity**:
  - **Real Engineering-Agent Workflow**: Natural-language prompt submission routes through the full engineering agent pipeline (User Prompt → `TuiApplication` → `InteractionController` → `ClaireCoderV1.run()` → `EngineeringEngine` → `Planner` → `WorkflowManager` → `ExecutionManager` → `EngineeringEngine.interaction_loop` (with tools) → `VerificationEngine` → `DefaultVerificationRunner` → Completion). Direct chat bypass removed.
  - **Real Core Tools & Aliases**: Implemented genuine I/O operations for `ReadFileTool`, `WriteFileTool`, `ReplaceFileContentTool`, `ListDirTool`, `DeleteFileTool`, `SearchTool`, and `TerminalTool`. Registered tool aliases (`list_dir`, `read_file`, `write_to_file`, `replace_file_content`, `run_command`, `search`).
  - **Default Verification Runner**: Implemented `DefaultVerificationRunner` evaluating real file presence, size, and content matching on disk without treating model claims as verification authority.
  - **Native Windows Clipboard Paste**: Zero-subprocess Win32 ctypes clipboard reader (`OpenClipboard`, `GetClipboardData`, `CloseClipboard`) mapping `\x16` (`Ctrl+V`), `Shift+Insert`, and `paste` with whitespace normalization and credential masking (`•` * length).
  - **Single-Owner Terminal Rendering**: Thread-safe event marshaling via `_event_queue`. Only the main TUI thread executes `redraw()`, `render_frame()`, `clear()`, and physical terminal writes. Background worker threads exclusively enqueue `Event` objects.
  - **Non-Blocking Key Polling**: `TerminalInput.read_key_timeout(0.03)` with `msvcrt.kbhit()` allows asynchronous background validation, model discovery, and streaming events to update the screen in real-time.
  - **TUI Geometry & Alignment Integrity**: Strict row and column bounding, fixed header/prompt/footer rows, ANSI-aware clipping, zero line wrapping, and zero scrollback pushing.
- **Stage 7 Correction #3 — Live Runtime State Integrity + Wizard/UI Geometry + Renderer Recovery + Active Model Propagation + Test Suite Consolidation**:
  - **Authoritative Model Propagation**: Unified pipeline `ConfigurationManager` -> active `ProviderProfile` -> active `ModelProfile` -> `ModelGateway` -> `ClaireCoder session/runtime` -> `EngineeringEngine` -> `ModelRequest.model_id`. Removed unsafe `"default-model"` fallback. Rejection with clean `ModelError` if unconfigured.
  - **Wizard Card Geometry & Single-Source Width**: `WizardCardGeometry` mathematical invariant `len(top_border) == len(body_row) == len(bottom_border) == card_width <= terminal_width` tested across widths 40..160.
  - **Provider Error Containment & Stale-Event Protection**: Clean formatting for HTTP 401/403/timeouts without raw tracebacks to stderr. Stale-event protection with `generation` and `request_id` discarding late async discovery callbacks.
  - **Single Render Owner & Duplicate Frame Elimination**: Box width bounded to `terminal_width`. 120+ cycle redraw stress test proving zero duplicate headers or wrapping.
  - **Session Pause Semantics**: `ObjectiveStatus.PAUSED` and `EXECUTION_RESUMED`. Blocks natural language prompts when paused with clear actionable message without spawning orphaned objectives.
  - **Test Suite Consolidation**: Migrated all historical `test_stage6_correction_*.py` and `test_stage7_correction_*.py` files into cohesive subsystem test modules.
- **Stage 7 Correction #4 — Provider Discovery/Validation Integrity + Ollama Runtime Identity + Live Provider/Model Switching + Atomic Active Profile**:
  - **Groq 403 Resolution & Credential Normalization**: Standardized `User-Agent: ClaireCoder/1.0 (Windows; x64) curl/8.0` preventing Cloudflare WAF 403 blocks. Implemented `normalize_credential` and `get_credential_fingerprint`.
  - **Ollama Runtime Identity & Memory Synchronization**: `ClaireCoderV1.load_providers_from_config()` auto-loads and registers all configured providers and models in `ModelGateway` at startup.
  - **Validation vs. Discovery Separation**: Lightweight reachability/auth checks (`validate_provider`) separated from model list parsing (`discover_models`).
  - **Atomic Active Model Configuration & Multi-Provider Coexistence**: `ConfigurationManager` tracks atomic `(provider_profile_id, model_id)` pairs in `active.json`. Multi-provider profiles coexist simultaneously.
  - **Live Switching & Active Execution Guard (`/model`)**: `/model` displays real provider badges, active indicators, and capabilities; `/model <model_id>` atomically switches active provider and model while blocking switching during active engineering execution.
  - **Inspection Hooks & Debug Metadata**: Added safe `last_request_debug` hooks on `ModelGateway` and adapters.
- **Stage 7 Correction #5 — Credential Backend Recovery + Wizard Application Boundary + Startup/Runtime Exception Visibility + Exit Frame Integrity**:
  - **Credential Backend Pre-Check & Recovery (`CredentialStore.check_backend_health`)**: Pre-flight verification of OS keyring backend health before attempting credential persistence.
  - **Clean Wizard Application Boundary (`register_runtime_sync_callback`)**: Replaced all private and forbidden references with clean callback pattern.
  - **Exit Idempotency & Render Guard (`TuiApplication.stop`, `TuiApplication.redraw`)**: Strict exit state management preventing double cleanup and trailing duplicate frames.
  - **Runtime Exception Visibility (`_handle_runtime_failure`)**: Replaced silent catch loops with visible diagnostic recording to both stderr and the TUI transcript.
  - **Terminal Auto-Size Detection (`TerminalCapability`)**: Dynamic terminal geometry detection via `shutil.get_terminal_size((104, 30))`.
- **Stage 7 Correction #6 — Windows Credential Backend Usability + Transactional Setup Save + Arbitrary Active Provider/Model Restoration + Interaction Router + Real Mode Semantics**:
  - **Windows Credential Backend Usability (`_ensure_backend`)**: Explicit configuration and auto-recovery of `WinVaultKeyring` (Windows Credential Manager).
  - **Transactional Setup Save**: Wizard save validates and confirms runtime synchronization via callback.
  - **Arbitrary Active Provider & Model Restoration**: Authoritative persisted pair `(provider_profile_id, model_id)` restored on startup without provider/model bias.
  - **Interaction Router (Conversational vs Engineering Intent)**: Deterministic heuristic classifier routes greetings/general questions directly without spawning workflow objectives.
  - **Real Mode Semantics & Policy Propagation (`/mode`)**: `/mode` inspects and updates operational mode and propagates policy constraints.
  - **Leaked Tool-Call JSON Filtering (`_filter_tool_call_json`)**: Strips raw internal function invocation payloads from user-facing transcripts.
- **Stage 7 Correction #7 — Real Agent Workflow + Input/Task Viewports + Interactive Model Selector + Task Result Lifecycle + Terminal Integrity**:
  - **Prompt Viewport (`PromptInput.render_line`)**: Cursor-following horizontal scrolling viewport keeping the cursor visible at all times.
  - **Task View Multiline Wrapping & Scrolling (`TaskViewOverlay`)**: Full multiline word-wrapping for long objectives across available card inner width; fixed card geometry.
  - **Interactive Provider → Model Selector Overlay (`ModelSelectorOverlay`)**: Two-level interactive selection overlay with live status badges.
  - **Task Result Lifecycle & Bounded Replanning**: Eliminated attribute error by querying `ExecutionManager` for `ExecutionTask.result`; enforced bounded replan budget (`max_replans = 2`).
- **Stage 7 Correction #8 — Live Windows Behavior / Agent State / TUI Viewport / Provider Setup / Model Selector / Terminal Integrity**:
  - **Transcript Word Wrapping**: Long Claire responses word-wrap at terminal width with word boundaries and fallback character wrap.
  - **Wizard Input Forwarding**: Setup Wizard launched from `/model` dispatches all keys to `wizard.handle_key()`.
  - **Wizard Esc Back-Stack**: Pressing Esc returns to Model Selector overlay when launched from there.
  - **Task View Terminal State Coherence**: Shows lifecycle states beyond ACTIVE (Complete, Failed, Cancelled, Interrupted).
  - **Duplicate `_dispatch_interactive_input` Elimination**: Removed shadowed duplicate method.
- **Stage 7 Correction #9 — Real Agent Core + Runtime State + TUI + Providers**:
  - **Authoritative Run State Machine (`AgentRun`)**: `RunState` enum and `AgentRun` class as single owner of execution lifecycle.
  - **Agent Loop Integration**: `process_natural_language()` creates `AgentRun` with cooperative cancellation checks.
  - **Mode Policy Enforcement at Execution Boundary**: `ToolExecutor.set_mode_policy()` blocks write/create/delete operations in plan/review mode at invocation boundary.
  - **Cancellation Reaches Execution Boundary**: `interrupt_active_session()` and `/cancel` cancel cooperative flag and engine objective.
  - **Model Switching Guard Uses Run State**: `/model` switch guard uses authoritative `AgentRun.state == RunState.RUNNING`.
  - **TUI Run State Projection**: `RUN_STATE_CHANGED` event maps run states to header display.
- **Stage 7 Correction #10 — Real Agent Behavior + Harness Integrity + Tool Safety + Provider Normalization + Permission Resume + Context/Session Continuity**:
  - **Permission Resume & Pending Invocation (§4)**: `PendingToolInvocation` records exact tool name, arguments, requested time, and invocation ID. `ToolExecutor.resolve_permission(invocation_id, decision)` resumes exact execution on ALLOW or marks DENIED without rerunning or losing arguments.
  - **Real Target Identification in Permission Requests (§5)**: File tools extract canonical workspace paths for `target_resources` instead of generic strings.
  - **Central Workspace Security Boundary (§6)**: Implemented `resolve_workspace_path()` in `clairecoder.tools.workspace` rejecting relative path escapes (`../`), drive jumping, and symlink escapes with `WorkspaceSecurityError`. Enforced across all core filesystem tools.
  - **Terminal Tool cwd Bound to Workspace (§7)**: `TerminalTool` defaults `cwd` to authoritative workspace root with bounds check against escaping workspace root.
  - **Removal of False Success Semantics (§8)**:
    - `ReadFileTool` returns `ToolState.FAILURE` when file does not exist.
    - `GitStatusTool` returns `ToolState.FAILURE` when git is missing or repository is uninitialized.
    - `GitCommitTool` returns `ToolState.FAILURE` on empty commits or missing git.
    - `DiagnosticsTool` returns `ToolState.FAILURE` when diagnostics fail or linter reports syntax errors.
  - **Real Edit/Patch Capability with Unified Diff (§9, §10)**: `WriteFileTool` and `ReplaceFileContentTool` compute and attach unified diffs to `ToolResult.metadata["diff"]` for transparent mutation inspection.
  - **Provider-Neutral Message History (§11)**: Implemented `AgentMessage` with roles (`user`, `assistant`, `system`, `tool`), durable content, tool calls, and serialized persistence.
  - **Canonical Provider Adapter Transforms (§12)**: Adapters transform provider-neutral `AgentMessage` into provider-specific schemas.
  - **Streaming Tool-Call Accumulation (§13)**: `ToolCallAccumulator` handles partial JSON streaming chunks, reconstructing complete function name and argument payloads before dispatch.
  - **Model Capability Negotiation (§14)**: `CapabilityState` tracks verified capabilities (`TOOL_CALLING`, `STREAMING`, `VISION`, etc.) and enforces pre-flight validation before routing tool schemas.
  - **Provider + Model Unambiguous Identity (§15)**: `model_key(provider_id, model_id)` creates stable, canonical identifiers preventing name collisions.
  - **ModePolicy Dataclass & Multi-Boundary Enforcement (§16)**: Centralized `ModePolicy` defining read/write/terminal execution permissions per mode (`PLAN`, `IMPLEMENT`, `REVIEW`, `DEBUG`).
  - **AgentRun Runtime Cancellation Authority (§17)**: `AgentRun.is_cancelled` respected across loops, streaming chunks, tool execution, and engine tasks.
  - **Unified Agent Budget & Loop Detection (§18, §19)**: `AgentBudget` enforces step, token, and tool-call limits. Loop detector tracks `action_signature()` to detect repetitive tool calls.
  - **Structured Failure Context in Replanning (§20)**: Tool and verification failures enrich `failure_context` into planner prompts for recovery rather than naive retries.
  - **Tool Result Normalization & Length Budgeting (§23)**: `NormalizedToolResult` caps large tool outputs with truncation markers preserving head/tail context.
  - **Durable Session History & Compaction (§24, §25)**: Serializes message history to session store; bounded compaction summarizes aged conversational turns.
  - **Bounded Retry / Backoff on Provider Failure (§27)**: Exponential backoff with jitter on transient provider failures (`429`, `503`, timeouts).
  - **Engine Event Protocol Additions (§29)**: Standardized events: `RUN_STARTED`, `RUN_COMPLETED`, `RUN_FAILED`, `RUN_CANCELLED`, `MODEL_STARTED`, `MODEL_COMPLETED`, `MODEL_FAILED`, `TOOL_STARTED`, `TOOL_FAILED`, `TOOL_DIFF`, `VERIFICATION_STARTED`, `VERIFICATION_COMPLETED`.
  - **Project Instruction Discovery (§34)**: Discovers and injects workspace `AGENTS.md` and `CLAUDE.md` instructions into agent system context.
  - **E2E Coding Agent Acceptance Tests (§36, §37)**: 72 new comprehensive tests in `tests/tools/test_correction_10.py` and `tests/tools/test_mode_policy.py`.
  - **Test Suite Pass Rate**: 656 passed, 0 skipped, 0 failures, 0 errors, 0 warnings (`pytest -W error`).

### Current State
- **Active Stage**: Stage 7 Correction #15 Completed and Verified.
- **Next Steps**: Await user testing feedback and authorization before proceeding to Correction #16.

### Phase Status
- **Phase 1-12**: Completed and Approved.
- **CLI / TUI Stage 1-4**: Completed and Approved.
- **CLI / TUI Stage 5 (Terminal Experience Finalization)**: Completed and Approved.
- **CLI / TUI Stage 6 (CLI Completion + Correction #10)**: Completed and Verified.
- **CLI / TUI Stage 7 (Multi-Provider Configuration + Real Workflow)**: Completed and Approved.
- **CLI / TUI Stage 7 Correction #1 (Live TUI Workflow Integration & State Sync)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #2 (Real Engineering-Agent Workflow & Clipboard & Single-Owner Rendering)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #3 (Live Runtime State Integrity & Test Suite Consolidation)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #4 (Provider Discovery/Validation Integrity & Ollama Runtime Identity & Live Switching)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #5 (Credential Backend Recovery & Wizard Boundary & Exit Integrity)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #6 (Windows Credential Backend + Transactional Save + Arbitrary Restore + Interaction Router + Real Mode Semantics)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #7 (Real Agent Workflow + Input/Task Viewports + Interactive Model Selector + Task Result Lifecycle + Terminal Integrity)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #8 (Live Windows Behavior / TUI Viewport / Provider Setup / Model Selector / Terminal Integrity)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #9 (Real Agent Core + Runtime State + TUI + Providers)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #10 (Real Agent Behavior + Harness Integrity + Tool Safety + Provider Normalization + Permission Resume + Context/Session Continuity)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #11 (Runtime State + Activity/Lifecycle Consistency)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #12 (Structured Runtime Event Protocol + EventEmitter + Bridge + TUI Listener)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #13 (Structured Task Graph + Semantic Task Model + Dependency Resolution + Failure Propagation + Attempt Tracking + Planner Preservation)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #14 (Agent Runtime Extraction + Decoupled Execution Lifecycle + Thin App + Clean Failure & Verification Boundaries + Non-Contradictory State Machine)**: Completed and Verified.
- **CLI / TUI Stage 7 Correction #15 (Structured Planner + Schema-Driven ModelRequest + Compact DAG Prompting + Strict Plan Validation + Safe Provider Fallback + Task Metadata Preservation)**: Completed and Verified.

### Recent Artifacts
- `Phase_CLI_TUI_Stage_7_Correction_15.zip`
- `Phase_CLI_TUI_Stage_7_Correction_14.zip`
- `Phase_CLI_TUI_Stage_7_Correction_13.zip`
- `Phase_CLI_TUI_Stage_7_Correction_12.zip`

### Documentation Baseline Lock (2026-08-18)
- **Status**: All 9 authoritative frontend documents finalized to FINAL.
- **Model Gateway**: CC-PRD-002 (v2.0.0 FINAL), CC-ADR-002 (v2.0.0 FINAL).
- **Terminal**: CC-PRD-011 (v2.0.0 FINAL), CC-ADR-007 (v2.0.0 FINAL), TUI-DESIGN.md (FINAL).
- **Desktop**: CC-PRD-012 (v1.0.0 FINAL), CC-ADR-008 (v1.0.0 FINAL), DESKTOP-DESIGN.md (v1.0.0 FINAL).
- **Roadmap**: CLI-TUI-DESKTOP-ROADMAP.md (v2.1.0 FINAL).


