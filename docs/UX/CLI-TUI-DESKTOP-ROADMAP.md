###############################################################################

# CLAIRE PROJECT
# CLAIRECODER V1 — FRONTEND IMPLEMENTATION ROADMAP

# Document       : CLI-TUI-DESKTOP-ROADMAP.md
# Version        : 2.1.0
# Status         : FINAL
#
# Authorities:
#   CC-PRD-002
#   CC-ADR-002
#   CC-PRD-011
#   CC-ADR-007
#   CC-PRD-012
#   CC-ADR-008
#   TUI-DESIGN.md
#   DESKTOP-DESIGN.md

###############################################################################


# 1. Purpose

This document defines the implementation sequence for the ClaireCoder V1
developer-facing frontends and the remaining productization work.

The roadmap covers two distinct presentation surfaces:

    Terminal
        CLI + TUI

    Desktop
        Tauri + React GUI

Both surfaces consume the same approved ClaireCoder application and Interaction
boundaries.

The roadmap SHALL NOT introduce a second Engineering Engine or duplicate
engineering ownership.


-------------------------------------------------------------------------------

# 2. Architectural Baseline

The final frontend architecture is:

                         ClaireCoderV1
                              │
              ┌───────────────┴────────────────┐
              │                                │
        Terminal Frontend                Desktop Frontend
              │                                │
          CLI / TUI                     Tauri + React
              │                                │
              └───────────────┬────────────────┘
                              │
                     Shared application /
                     interaction semantics
                              │
                    Existing V1 subsystems

Shared authoritative systems remain:

    - Engineering Engine
    - Model Gateway
    - Tool system
    - Skill system
    - Permission Engine
    - Context Engine
    - Workflow
    - Execution
    - Verification
    - Session / application lifecycle


-------------------------------------------------------------------------------

# 3. Completed Stages

The following implementation work is already complete and SHALL NOT be
reimplemented.

## Stage 1 — CLI / TUI Foundation

Completed:

    - TUI package foundation
    - CLI package foundation
    - presentation abstractions
    - terminal states
    - prompt foundation
    - header foundation
    - transcript foundation
    - architecture separation
    - initial CLI shell

Status:

    COMPLETE


## Stage 2 — Transcript / Activity Renderer

Completed:

    - ActivityModel
    - ActivityRenderer
    - streaming transcript
    - activity correlation
    - diff presentation foundation
    - presentation event adapter
    - mascot mapping foundation

Status:

    COMPLETE


## Stage 2 Corrections

Completed:

    - public Engine event subscription
    - InteractionController subscription boundary
    - activity correlation corrections
    - real Engine → Interaction → TUI integration
    - architectural private-state protections

Status:

    COMPLETE


## Stage 3 — Permission UI

Completed:

    - Permission presentation
    - confirmation interaction
    - permission event integration
    - permission/TUI boundary
    - permission integration testing

Status:

    COMPLETE


## Stage 3 Correction

Completed:

    - clean-environment import correction
    - package import validation
    - regression validation

Status:

    COMPLETE


## Stage 4 — Diff / Review / Command Palette

Completed:

    - diff renderer
    - Review view
    - Command Palette
    - preview harness
    - command routing
    - terminal presentation surfaces

Status:

    COMPLETE


## Stage 4 Correction

Completed:

    - application/UI command ownership correction
    - `/help` routing correction
    - presentation routing validation
    - visual preview validation

Status:

    COMPLETE


-------------------------------------------------------------------------------

# 4. Stage 5 — Terminal Experience Finalization

Purpose:

Finalize the terminal experience according to the revised terminal product
contract.

The existing terminal appearance SHALL remain visually locked.

This stage SHALL NOT redesign the TUI.

Work:

    1. Remove graphical mascot rendering from terminal runtime.
    2. Remove terminal mascot-specific presentation paths.
    3. Remove terminal mascot sprite/state dependencies.
    4. Replace graphical startup mascot with CLAIRECODER wordmark.
    5. Preserve:
           - dark terminal canvas,
           - cyan/teal palette,
           - pink/magenta identity accent,
           - compact composition,
           - activity hierarchy,
           - diff presentation,
           - permission surface,
           - File Tree,
           - Review,
           - Task,
           - Command Palette,
           - prompt placement,
           - shortcut footer.
    6. Preserve `Claire:` text/persona presentation.
    7. Finalize terminal glass-style prompt treatment.
    8. Remove terminal image-protocol dependencies.
    9. Validate IDE-terminal-size presentation.
    10. Validate Full / Compact / Minimal / CI behavior.
    11. Update terminal tests to reflect the mascot-removal decision.
    12. Preserve the old terminal visual appearance except for the explicitly
        approved mascot removal.

Acceptance target:

    A developer can run the TUI inside a typical IDE terminal and receive the
    intended compact ClaireCoder terminal appearance without any graphical
    mascot dependency.


-------------------------------------------------------------------------------

# 5. Stage 6 — CLI Completion

Purpose:

Turn the existing CLI shell into a usable frontend over ClaireCoderV1.

Work:

    1. CLI entry point.
    2. launcher-compatible invocation.
    3. interactive launch routing.
    4. direct objective submission.
    5. session selection.
    6. session resumption.
    7. model selection.
    8. mode selection.
    9. status command.
    10. non-interactive execution.
    11. CI output.
    12. exit codes.
    13. structured/log-friendly formatting.
    14. CLI/TUI shared command semantics.
    15. graceful configuration/model errors.
    16. provider-independent model selection.

Acceptance target:

    clairecoder

and:

    clairecoder "engineering objective"

operate through the approved application boundary.


-------------------------------------------------------------------------------

# 6. Stage 7 — Multi-Provider Configuration / Credential / Bootstrap

Purpose:

Establish the real Model Gateway configuration and provider environment
required for ClaireCoder V1.

This stage SHALL validate the revised multi-provider Model Gateway architecture
before Desktop implementation depends on it.

The implementation SHALL treat the following as distinct concepts:

    Provider
    Adapter
    Endpoint
    Runtime
    Router
    Provider Profile
    Model Profile
    Credential Reference
    Model


## 7.1 Provider / Runtime Scope

The Stage 7 provider architecture SHALL support:

    Cloud / Hosted Providers

        - Groq
        - OpenAI
        - Anthropic
        - Gemini
        - OpenRouter

    Local / Self-Hosted Systems

        - Ollama
        - LM Studio
        - vLLM
        - OmniRoute

    Custom

        - user-defined compatible endpoints.


## 7.2 Adapter Families

The Gateway SHALL validate at least two distinct adapter paths.

OpenAI-Compatible Adapter:

    - Groq
    - OpenAI
    - OpenRouter
    - OmniRoute
    - Ollama
    - LM Studio
    - vLLM
    - other compatible endpoints

Native Adapter Families:

    - Anthropic
    - Gemini

The stage SHALL prove that the Gateway is genuinely adapter-based rather than
being an OpenAI-compatible passthrough with interchangeable credentials.

The distinction SHALL remain:

    Provider
        ≠
    Adapter


## 7.3 Provider Profiles

The configuration system SHALL support multiple Provider Profiles.

A Provider Profile MAY define:

    - Provider identity
    - Adapter
    - Endpoint
    - Runtime
    - Router
    - Credential reference
    - Default Model
    - Available Models
    - Capability metadata
    - Provider-specific parameters

Multiple Profiles MAY exist for the same Provider.

Examples:

    groq-fast
    openai-primary
    anthropic-primary
    gemini-primary
    openrouter-main
    omni-local
    ollama-local
    lmstudio-local


## 7.4 Model Profiles

The configuration system SHALL support Model Profiles.

A Model Profile MAY define:

    - preferred Model
    - Provider Profile
    - reasoning level
    - fallback Model
    - capability requirements
    - latency preference
    - cost preference

Model Profiles SHALL remain separate from Provider Profiles and the underlying
Gateway entities.


## 7.5 Configuration Lifecycle

The provider/model configuration lifecycle SHALL be:

    DISCOVER / CONFIGURE
            ↓
        VALIDATE
            ↓
         REGISTER
            ↓
    CAPABILITY DETECTION
            ↓
      MODEL AVAILABLE
            ↓
          SELECT
            ↓
         EXECUTE


## 7.6 Credentials

Credential storage SHALL be provider/profile scoped.

The system SHALL support multiple credential references simultaneously.

Examples:

    groq-primary
    openai-primary
    anthropic-primary
    gemini-primary
    openrouter-primary
    omni-local

A Provider Profile SHALL reference a credential rather than expose or own the
raw secret.

Persistent credentials SHOULD use the operating system secure credential store
where available.

Environment variables MAY remain a supported source.

The system SHALL NOT assume one global API-key slot.

The same installation MAY have:

    OpenAI credential
    +
    Groq credential
    +
    Anthropic credential
    +
    Gemini credential
    +
    OpenRouter credential
    +
    OmniRoute/local configuration

simultaneously.


## 7.7 Local Runtime Configuration

Local systems SHALL be first-class.

Examples:

    Ollama
        local endpoint

    LM Studio
        local endpoint

    vLLM
        local endpoint

    OmniRoute
        local gateway endpoint

The Engineering Engine SHALL not need to know whether the selected Model is
local, cloud-hosted, self-hosted, or routed.


## 7.8 OmniRoute

OmniRoute SHALL remain a distinct self-hosted local AI gateway.

A typical local endpoint MAY be:

    http://localhost:20128

The implementation SHALL NOT hard-code that port as universal.

The endpoint SHALL remain configurable.

OmniRoute SHALL NOT be conflated with OpenRouter.


## 7.9 OpenRouter

OpenRouter SHALL remain a distinct hosted routed provider.

It SHALL NOT be treated as the same system as OmniRoute.

The configuration system SHALL allow both to coexist independently.


## 7.10 Capability Validation

The stage SHALL validate that the selected execution path accurately reports:

    - Tool calling
    - structured output
    - vision
    - reasoning
    - streaming
    - context capacity

Provider-level capability SHALL NOT automatically be treated as Model-level
capability.


## 7.11 Provider Validation

The stage SHALL validate each supported Provider independently where practical.

Required architectural validation:

    OpenAI-Compatible Adapter
        ↓
    Groq

and:

    Native Adapter
        ↓
    Anthropic OR Gemini

This proves both adapter families independently.

The final Stage 7 validation SHOULD cover:

    Groq
    OpenAI
    Anthropic
    Gemini
    OpenRouter
    OmniRoute
    Ollama
    LM Studio
    vLLM


## 7.12 Adapter Conformance

Every production Adapter SHALL conform to the normalized Model Gateway
contract.

At minimum, conformance testing SHALL verify:

    - model invocation
    - structured response normalization
    - streaming behavior where supported
    - Tool-call normalization where supported
    - error normalization
    - capability reporting


## 7.13 Failure / Fallback Validation

Validate:

    - authentication failure,
    - endpoint failure,
    - rate limiting,
    - protocol mismatch,
    - adapter failure,
    - capability mismatch,
    - temporary Provider failure.

Fallback SHALL distinguish:

    Provider fallback
    Model fallback
    Capability fallback
    Execution retry / recovery

Material Model changes SHALL remain visible to the user.


## 7.14 Test Strategy

Provider tests SHALL be divided into:

    Adapter Conformance Tests

        Test normalized Gateway behavior without external services.

    Live Provider Tests

        Test real Provider APIs where credentials/services are available.

    Local Runtime Tests

        Test actual local endpoints where runtimes are installed.

    Configuration Tests

        Test Provider Profiles, Model Profiles, credentials, endpoints,
        and local/cloud coexistence.

Live tests MAY be unavailable in CI.

When unavailable, mocked/fake Adapter tests SHALL still validate the Gateway
contract.

At minimum, one OpenAI-compatible Provider and one native Provider SHALL be
proven independently.


## 7.15 Acceptance Criteria

Stage 7 is complete only when:

    1. Model Gateway is Provider-independent.
    2. OpenAI-compatible and native Adapter paths both work.
    3. Groq can be configured and invoked.
    4. At least one native Provider can be configured and invoked.
    5. OpenAI can be represented and invoked.
    6. OpenRouter can be represented independently.
    7. OmniRoute can be represented independently.
    8. Ollama can be represented.
    9. LM Studio can be represented.
    10. vLLM can be represented.
    11. Multiple Provider Profiles can coexist.
    12. Multiple credential references can coexist.
    13. Local and cloud Models can coexist.
    14. Model Profiles can select configured Providers/Models.
    15. Adapter conformance tests pass.
    16. Capability negotiation works.
    17. Streaming works where supported.
    18. Structured Gateway failures are produced.
    19. Credentials do not enter Model context or ordinary logs.
    20. Adding a Provider does not require modification of the Engineering
        Engine.
    21. OpenRouter and OmniRoute remain distinct configurations.
    22. The complete existing V1 regression suite remains passing.


## 7.16 Stage 7 Boundary

Stage 7 SHALL NOT implement:

    - Desktop GUI,
    - Desktop WebSocket transport,
    - Desktop credential screens,
    - advanced automatic model benchmarking,
    - complex cost optimization,
    - distributed model orchestration.

Those belong to later stages or remain optional V1 extensions.


## 7.17 Stage 7 Dependency

Stage 7 depends on finalized:

    CC-PRD-002
    CC-ADR-002

The Desktop architecture SHALL consume the resulting Model Gateway and
configuration boundary rather than creating another Provider system.


-------------------------------------------------------------------------------

# 7A. Stage 7 Architecture Lock

The intended provider model is:

                              MODEL GATEWAY
                                   │
                       Provider / Adapter Registry
                                   │
              ┌────────────────────┼─────────────────────┐
              │                    │                     │
       OpenAI-Compatible      Native APIs          Local Systems
          Adapter               Adapters
              │                    │                     │
      ┌───────┼──────┬──────┐      ├── Anthropic        ├── Ollama
      │       │      │      │      └── Gemini           ├── LM Studio
     Groq   OpenAI OpenRouter OmniRoute                ├── vLLM
                                                       └── local gateways

The Engineering Engine sees only the normalized Model Gateway interface.

No Provider, Adapter, Runtime, Router, or credential implementation may leak
into the Engineering Engine.


-------------------------------------------------------------------------------

# 8. Stage 8 — Desktop Application Foundation

Purpose:

Create the Desktop process and frontend architecture defined by CC-PRD-012
and CC-ADR-008.

Work:

    1. Tauri shell.
    2. React application.
    3. automatic local backend process startup.
    4. dynamic local port.
    5. loopback-only binding.
    6. WebSocket transport.
    7. protocol handshake.
    8. request/response model.
    9. event stream.
    10. request correlation.
    11. event sequencing.
    12. connection lifecycle.
    13. bootstrap security token.
    14. backend readiness detection.
    15. graceful startup failure handling.

Acceptance target:

    Double-click Desktop application
        ↓
    backend automatically starts
        ↓
    local WebSocket connects
        ↓
    handshake succeeds
        ↓
    Desktop enters application-ready state.


-------------------------------------------------------------------------------

# 9. Stage 9 — Desktop Main Experience

Purpose:

Implement the locked Desktop visual experience.

Reference geometry:

    919 × 635

Work:

    1. Boot Screen.
    2. Main Pane.
    3. Header.
    4. Action Log.
    5. Prompt.
    6. Bottom navigation.
    7. graphical Claire.
    8. nine mascot states.
    9. streaming activity.
    10. Claire text messages.
    11. fixed Header.
    12. internal Action Log scrolling.
    13. fixed Prompt.
    14. manual resize support.
    15. reference visual fidelity.

The Desktop GUI SHALL reproduce the locked visual reference rather than
reinterpret it.


-------------------------------------------------------------------------------

# 10. Stage 10 — Desktop Secondary Views

Implement:

    File Tree View
    Review Changes View
    Task / Workflow View
    Command Palette View
    Permission View

Each SHALL:

    - exist inside the same application window,
    - replace the active Main Pane view,
    - own the primary viewport,
    - implement its own internal scrolling where required.

No secondary panel SHALL become a separate window.

No Main Pane content SHALL remain interactively active beneath a secondary view.


-------------------------------------------------------------------------------

# 11. Stage 11 — Desktop Interaction Integration

Connect the complete Desktop frontend to the shared application boundary.

Work:

    1. command submission
    2. session operations
    3. streaming events
    4. Tool activity
    5. Permission interaction
    6. Workflow state
    7. Execution state
    8. Verification state
    9. Task progress
    10. completion
    11. interruption
    12. error handling
    13. reconnect behavior
    14. state resynchronization
    15. provider/model selection
    16. model configuration status

Keyboard and mouse interaction SHALL produce the same application semantics.


-------------------------------------------------------------------------------

# 12. Stage 12 — Desktop UX Completion

Validate every locked interaction rule.

Required validation:

    Ctrl+T
        File Tree

    Ctrl+R
        Review

    Ctrl+P
        Task

    ?
        Command Palette

    Enter
        Submit / activate

    Esc
        View-specific close/cancel

    Ctrl+C
        Engineering interruption

Validate:

    - view replacement,
    - panel ownership,
    - scroll ownership,
    - confirmation semantics,
    - review semantics,
    - keyboard/mouse parity,
    - resize behavior,
    - 919 × 635 reference composition,
    - Claire state synchronization.


-------------------------------------------------------------------------------

# 13. Stage 13 — Desktop Security / Credential Integration

Purpose:

Expose the already-established Stage 7 Provider/Model configuration through
the Desktop application without creating another configuration or credential
authority.

Validate:

    - Provider Profile access,
    - Model Profile access,
    - credential reference handling,
    - OS secure credential storage,
    - backend-owned credential use,
    - React secret isolation,
    - transport trust boundary,
    - bootstrap token,
    - loopback-only server binding,
    - malformed request rejection,
    - protocol compatibility.

The Desktop SHALL consume the Stage 7 configuration boundary.

It SHALL NOT invent a separate credential model.

The GUI SHALL never expose raw provider credentials unnecessarily.


-------------------------------------------------------------------------------

# 14. Stage 14 — Packaging / Distribution

Desktop:

    - Windows installer
    - macOS package
    - Linux package/AppImage where supported

Terminal:

    - CLI launcher
    - package installation
    - environment setup
    - non-interactive operation

The exact packaging mechanism SHALL be finalized during implementation.


-------------------------------------------------------------------------------

# 15. Stage 15 — Full End-to-End Validation

Validate both frontend surfaces independently and together.

## Terminal

    Launch
      ↓
    Configuration
      ↓
    Provider / Model selection
      ↓
    Objective
      ↓
    Activity
      ↓
    Permission
      ↓
    Tools
      ↓
    Verification
      ↓
    Completion


## Desktop

    Launch
      ↓
    Backend startup
      ↓
    WebSocket handshake
      ↓
    Configuration
      ↓
    Provider / Model selection
      ↓
    Objective
      ↓
    Streaming activity
      ↓
    Permission View
      ↓
    Tool execution
      ↓
    Verification
      ↓
    Completion


## Cross-Frontend

Both frontends SHALL exercise the same:

    - Engineering Engine,
    - Model Gateway,
    - Workflow,
    - Execution,
    - Verification,
    - Permission Engine,
    - Context,
    - Tool system,
    - Session/application semantics.

No frontend-specific Provider/Model execution path SHALL bypass the shared
Model Gateway.


-------------------------------------------------------------------------------

# 16. Stage 16 — Final V1 Audit

The final audit SHALL verify:

    - architecture boundaries,
    - public API usage,
    - no private-state bypass,
    - no duplicate engineering systems,
    - provider independence,
    - adapter architecture,
    - local/cloud coexistence,
    - credential isolation,
    - CLI correctness,
    - TUI correctness,
    - Desktop correctness,
    - visual fidelity,
    - interaction fidelity,
    - regression safety,
    - packaging integrity,
    - documentation consistency.

The complete V1 regression suite SHALL pass with zero project-owned warnings.


-------------------------------------------------------------------------------

# 17. Documentation Workflow

Authoritative documents:

    Model Gateway

        CC-PRD-002
        CC-ADR-002

    Terminal

        CC-PRD-011
        CC-ADR-007
        TUI-DESIGN.md

    Desktop

        CC-PRD-012
        CC-ADR-008
        DESKTOP-DESIGN.md

Implementation stages SHALL NOT silently modify these requirements.

If implementation reveals a genuine architectural conflict:

    STOP
        ↓
    document discrepancy
        ↓
    propose correction
        ↓
    update authoritative document
        ↓
    resume implementation

No frontend framework default may override a locked product requirement.

No Provider-specific implementation detail may silently redefine the Model
Gateway architecture.


-------------------------------------------------------------------------------

# 18. Implementation Command Workflow

Every implementation stage SHALL follow the established process:

    1. Read authoritative documents.
    2. Inspect current source.
    3. Perform pre-implementation audit.
    4. Identify exact implementation boundary.
    5. Implement the smallest compliant change.
    6. Add/update tests.
    7. Run targeted tests.
    8. Run subsystem regression tests.
    9. Run full regression suite.
    10. Perform post-implementation source audit.
    11. Update memory/update documentation.
    12. Produce stage report.
    13. Produce clean archive.
    14. STOP.
    15. Await independent audit/authorization.

The implementation command SHOULD include concise code snippets whenever a
behavior is easy to misunderstand and a snippet can remove ambiguity.


-------------------------------------------------------------------------------

# 19. Correction Policy

Corrections SHALL be numbered independently within their owning stage.

Example:

    Stage 5
        Correction #1
        Correction #2

    Stage 7
        Correction #1
        Correction #2

A correction SHALL:

    - identify the root cause,
    - modify only the affected boundary,
    - add regression coverage,
    - rerun the complete regression suite,
    - produce a correction report,
    - archive the corrected state.

A correction SHALL NOT silently expand the scope of the original stage.


-------------------------------------------------------------------------------

# 20. Stage Completion Rule

A stage is complete only when:

    - implementation matches its authoritative requirements,
    - tests pass,
    - architecture boundaries remain intact,
    - no known blocker remains,
    - documentation is updated,
    - artifact is archived,
    - independent review can begin.

"Tests pass" alone does NOT mean the stage is complete.


-------------------------------------------------------------------------------

# 21. Final Product Shape

The completed ClaireCoder V1 developer experience SHALL be:

                         ClaireCoder V1
                              │
             ┌────────────────┴────────────────┐
             │                                 │
        Terminal Surface                 Desktop Surface
             │                                 │
        CLI + TUI                         Tauri + React
             │                                 │
             └────────────────┬────────────────┘
                              │
                     Shared Application
                     / Interaction Layer
                              │
                     Engineering Engine
                              │
                      Model Gateway
                              │
       ┌──────────────┬───────┼───────┬──────────────┐
       │              │       │       │              │
    Providers      Workflow  Tools  Permission   Verification
       │
       ├── Cloud
       │     ├── Groq
       │     ├── OpenAI
       │     ├── Anthropic
       │     ├── Gemini
       │     └── OpenRouter
       │
       └── Local / Self-Hosted
             ├── Ollama
             ├── LM Studio
             ├── vLLM
             └── OmniRoute

Terminal identity:

    CLAIRECODER
    Claire: text persona

Desktop identity:

    graphical Claire
    nine mascot states
    full locked visual design

Both surfaces remain thin frontends.

All Model execution remains behind the shared Model Gateway.


-------------------------------------------------------------------------------

# 22. Roadmap Lock

This roadmap supersedes the earlier CLI/TUI-only remaining-stage sequence.

Completed stages SHALL remain historical records.

Future implementation SHALL use the sequence:

    Stage 5
        Terminal Experience Finalization
            ↓
    Stage 6
        CLI Completion
            ↓
    Stage 7
        Multi-Provider Configuration /
        Credential / Bootstrap
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


-------------------------------------------------------------------------------

# 23. AI Instructions

When implementing this roadmap:

    1. Treat CC-PRD-002 and CC-ADR-002 as the Model Gateway authorities.
    2. Treat CC-PRD-011 and CC-ADR-007 as the terminal authorities.
    3. Treat TUI-DESIGN.md as the terminal visual authority.
    4. Treat CC-PRD-012 and CC-ADR-008 as the Desktop authorities.
    5. Treat DESKTOP-DESIGN.md as the Desktop visual authority.
    6. Preserve the existing ClaireCoder V1 architecture.
    7. Never create another Engineering Engine.
    8. Never create duplicate Workflow, Execution, Verification, or Permission
       systems.
    9. Keep CLI/TUI and Desktop as frontend surfaces.
    10. Keep all Model execution behind Model Gateway.
    11. Keep Provider-specific API logic inside adapters.
    12. Preserve the Provider/Adapter separation.
    13. Preserve native Anthropic and Gemini adapter paths.
    14. Preserve the OpenAI-compatible adapter family.
    15. Treat local runtimes as first-class.
    16. Keep OpenRouter and OmniRoute distinct.
    17. Preserve independent Provider Profiles.
    18. Preserve independent credential references.
    19. Never store raw Provider credentials in frontend state.
    20. Never expose secrets through normal logs or model context.
    21. Preserve terminal appearance.
    22. Do not reintroduce graphical mascot rendering into the terminal.
    23. Preserve full graphical Claire in Desktop.
    24. Preserve 919 × 635 Desktop reference geometry.
    25. Preserve Desktop view replacement.
    26. Preserve keyboard/mouse parity.
    27. Preserve panel-specific Esc semantics.
    28. Use code snippets in implementation commands when they materially reduce
        ambiguity.
    29. Test every stage independently.
    30. Add adapter conformance tests before adding provider-specific special
        cases.
    31. Preserve the complete V1 regression suite.
    32. Do not commit unless explicitly commanded.
    33. Do not push to remote repositories.
    34. Stop after every stage pending independent authorization.


###############################################################################

END OF CLI-TUI-DESKTOP-ROADMAP.md

###############################################################################