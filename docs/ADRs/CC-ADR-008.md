###############################################################################

#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-008
# Title           : ClaireCoder Desktop Frontend & Local Application Boundary
# Version         : 1.0.0
# Status          : FINAL

###############################################################################


# 1. Decision Summary

This ADR defines the architecture for the ClaireCoder Desktop GUI Interaction
Layer introduced by CC-PRD-012.

The Desktop GUI SHALL be implemented as:

    Tauri
        +
    React

and SHALL operate as a thin graphical frontend to the existing ClaireCoder
application.

The Desktop GUI SHALL NOT embed or recreate the Engineering Engine.

The preferred runtime architecture SHALL be:

    ┌────────────────────────────────────────────┐
    │              Tauri Desktop App             │
    │                                            │
    │  React UI                                 │
    │  Desktop Interaction Adapter              │
    │  View / Presentation State                │
    └──────────────────────┬─────────────────────┘
                           │
                   Local Application
                   Transport Boundary
                           │
                           ▼
    ┌────────────────────────────────────────────┐
    │       ClaireCoder Application Process      │
    │                                            │
    │  ClaireCoderV1                            │
    │  Interaction / Application APIs           │
    └──────────────────────┬─────────────────────┘
                           │
                           ▼
    ┌────────────────────────────────────────────┐
    │              Existing V1 System            │
    │                                            │
    │ Engine │ Workflow │ Execution │ Verification
    │ Tools  │ Skills   │ Gateway   │ Permissions│
    │ Context                                      │
    └────────────────────────────────────────────┘

The Desktop GUI SHALL communicate with the local application through a
controlled local WebSocket boundary.

The local WebSocket SHALL provide:

    - request/response communication,
    - streaming application events,
    - request correlation,
    - controlled connection lifecycle,
    - reconnection support.

The Desktop GUI SHALL NOT directly import Python engineering modules into the
React frontend.

Credential handling SHALL remain below the frontend boundary.

Provider credentials SHALL NOT be stored in React component state,
localStorage, sessionStorage, or frontend source.

The application-side configuration layer SHALL own credential access.

Where persistent provider credentials are required, the preferred storage
mechanism SHALL be the operating system's secure credential/keychain facility,
with the backend/application process responsible for reading and using the
credential.

-------------------------------------------------------------------------------

# 2. Context

CC-PRD-012 introduces a second graphical frontend for ClaireCoder.

The existing ClaireCoder architecture already provides:

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

The Desktop GUI therefore does not need to own those concerns.

The principal architectural problem is to allow a graphical frontend to:

    - send user commands,
    - submit engineering objectives,
    - receive streaming activity,
    - display permission requests,
    - receive results,
    - control approved session operations,

without coupling React components directly to the Python implementation.

A second requirement is process separation.

The graphical frontend SHOULD remain independently renderable and replaceable,
while the ClaireCoder application process SHOULD remain independently testable
and executable.

A third requirement is credential isolation.

Provider credentials such as API keys SHALL remain outside the presentation
layer and SHALL be usable by both the Desktop frontend and the CLI through the
same application/configuration system.


-------------------------------------------------------------------------------

# 3. Decision

The Desktop GUI SHALL use a local application-client architecture.

The Desktop application SHALL contain:

    Tauri Shell
    React Frontend
    Desktop Interaction Adapter
    Desktop Presentation/View Layer

The local backend SHALL contain:

    ClaireCoder application runtime
    ClaireCoderV1
    Interaction/Application interfaces
    Model Gateway
    Engineering subsystems

The preferred communication path SHALL be:

    React/Tauri
        ↓
    Desktop Interaction Adapter
        ↓
    Local WebSocket Client
        ↓
    Local ClaireCoder Application Service
        ↓
    ClaireCoderV1
        ↓
    Existing V1 Architecture

The Desktop frontend SHALL interact through public contracts exposed by the
local application service.

No React component SHALL directly import:

    - Engineering Engine implementation,
    - WorkflowManager implementation,
    - ExecutionManager implementation,
    - VerificationEngine implementation,
    - PermissionEngine implementation,
    - ToolExecutor implementation,
    - provider SDKs.


-------------------------------------------------------------------------------

# 4. Why Local WebSocket

A local WebSocket is selected as the primary Desktop ↔ Application transport
because the Desktop GUI requires both:

    COMMAND FLOW

        User action
            ↓
        Application request
            ↓
        Application response

and:

    STREAMING FLOW

        EngineeringEngine event
            ↓
        Application event stream
            ↓
        Desktop UI update

The transport therefore needs to support bidirectional long-lived
communication rather than only one-shot request/response calls.

A WebSocket boundary also provides a clean transport-independent application
contract.

The frontend SHALL NOT depend on Python internals merely because the backend is
implemented in Python.

The transport itself SHALL remain replaceable behind the Desktop Application
Boundary if a future architecture decision explicitly supersedes this ADR.


-------------------------------------------------------------------------------

# 5. Transport Architecture

The Desktop application SHALL communicate with the local application through:

    ws://127.0.0.1:<dynamic-port>/<service-path>

The implementation SHALL prefer loopback binding.

The backend SHALL NOT bind to:

    0.0.0.0

for the normal Desktop runtime.

The application SHOULD use a dynamically selected local port rather than a
fixed globally reserved port.

The Desktop startup process SHALL obtain the actual connection information
through an approved bootstrap/handshake mechanism.

The frontend SHALL NOT assume a hard-coded port.


-------------------------------------------------------------------------------

# 6. Local Trust Boundary

The local transport SHALL be treated as a trusted local application boundary,
not as an Internet-facing API.

The backend SHALL nevertheless validate:

    - message shape,
    - protocol version,
    - request type,
    - request identifier,
    - authorization context,
    - payload schema.

The backend SHALL reject malformed or unsupported messages.

The frontend SHALL NOT be granted direct access to private subsystem objects.


-------------------------------------------------------------------------------

# 7. Connection Handshake

The Desktop client SHALL perform an initial handshake after connection.

Conceptual sequence:

    Desktop
        ↓
    HELLO
        ↓
    Backend
        ↓
    READY
        ↓
    Desktop

The handshake SHOULD establish:

    - protocol version,
    - application version,
    - session capability,
    - supported commands,
    - server readiness,
    - optional feature capabilities.

The exact payload schema SHALL be defined at implementation level.

Protocol incompatibility SHALL produce an explicit error rather than silently
continuing with incompatible semantics.


-------------------------------------------------------------------------------

# 8. Message Model

The transport SHALL distinguish at minimum between:

    REQUEST
    RESPONSE
    EVENT
    ERROR

Conceptual request:

    {
        "type": "request",
        "request_id": "...",
        "command": "...",
        "payload": {...}
    }

Conceptual response:

    {
        "type": "response",
        "request_id": "...",
        "status": "ok",
        "payload": {...}
    }

Conceptual event:

    {
        "type": "event",
        "event": "...",
        "sequence": ...,
        "payload": {...}
    }

These examples define the conceptual protocol only.

The exact schema SHALL be finalized during implementation.

The key requirement is that:

    request_id

is stable across the request lifecycle and allows the Desktop client to
associate responses/errors with the initiating request.


-------------------------------------------------------------------------------

# 9. Event Streaming

The backend SHALL expose application events through the same local transport.

The intended path is:

    Existing Application Event
        ↓
    Application Event Adapter
        ↓
    WebSocket EVENT message
        ↓
    Desktop Interaction Adapter
        ↓
    React View Model
        ↓
    UI

The Desktop frontend SHALL NOT infer authoritative engineering events from
visual changes.

The backend SHALL remain responsible for producing the event.

The Desktop GUI SHALL treat events as projections of authoritative application
state.


-------------------------------------------------------------------------------

# 10. Event Ordering

Events transmitted to the Desktop frontend SHALL carry enough sequencing
information to preserve deterministic presentation order.

A monotonically increasing sequence value SHOULD be associated with streamed
events within a connection/session scope.

The Desktop frontend SHALL:

    - preserve event ordering,
    - detect gaps where practical,
    - avoid silently reordering authoritative events,
    - avoid inventing missing events.

If an event stream becomes inconsistent, the frontend SHOULD request an
application state refresh rather than fabricating intermediate state.


-------------------------------------------------------------------------------

# 11. Request Correlation

Requests SHALL use stable request identifiers.

Conceptually:

    User action
        ↓
    request_id = abc123
        ↓
    Application
        ↓
    response(request_id=abc123)

The same request correlation model SHALL support:

    - command submission,
    - session operations,
    - permission responses,
    - view-triggering application commands,
    - model/configuration operations,
    - cancellation requests.

Request correlation SHALL remain transport-level behavior and SHALL NOT become
an additional engineering state machine.


-------------------------------------------------------------------------------

# 12. Command Ownership

The Desktop GUI SHALL preserve the command ownership already defined by the
Interaction Layer.

Application commands such as:

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

SHALL route through the approved Interaction/Application boundary.

The Desktop adapter MAY translate:

    mouse click
    keyboard shortcut
    graphical button
    menu selection

into the same underlying command request.

The Desktop frontend SHALL NOT create a second command semantics system.


-------------------------------------------------------------------------------

# 13. Presentation-Only Navigation

Desktop-only view changes may be handled by the Desktop presentation layer
when they do not require engineering-state ownership.

Examples:

    Main Pane
        ↓
    File Tree View

    Main Pane
        ↓
    Command Palette View

    Main Pane
        ↓
    Task View

These are presentation state changes.

They SHALL NOT require the Desktop frontend to create corresponding Workflow,
Execution, Verification, or Permission state.


-------------------------------------------------------------------------------

# 14. Permission Boundary

Permission authority remains entirely below the Desktop frontend.

The conceptual chain SHALL remain:

    Tool Operation Requested
        ↓
    Permission Engine
        ↓
    Permission Request Event
        ↓
    Desktop Permission View
        ↓
    User Decision
        ↓
    Interaction/Application Boundary
        ↓
    Permission Engine
        ↓
    Decision Result
        ↓
    Desktop UI

The Desktop GUI SHALL NOT:

    - decide ALLOW / ASK / DENY,
    - modify permission policy,
    - execute a Tool after user confirmation,
    - bypass PermissionEngine.


-------------------------------------------------------------------------------

# 15. Tool Boundary

The Desktop GUI SHALL never execute a Tool.

The architecture SHALL remain:

    Desktop GUI
        ↓
    Application Boundary
        ↓
    Engineering System
        ↓
    ToolExecutor
        ↓
    PermissionEngine
        ↓
    Tool

The React layer SHALL only display Tool activity and collect user interaction
where an approved application operation exists.


-------------------------------------------------------------------------------

# 16. Workflow / Execution / Verification Boundaries

Workflow:

    WorkflowManager remains authoritative.

Execution:

    ExecutionManager remains authoritative.

Verification:

    VerificationEngine remains authoritative.

The Desktop frontend SHALL display these states through application responses
and events.

The Desktop frontend SHALL NOT:

    - create Tasks,
    - reorder Tasks,
    - implement recovery logic,
    - decide execution success,
    - implement retries,
    - evaluate Verification evidence.


-------------------------------------------------------------------------------

# 17. Desktop View State

The Desktop frontend MAY maintain presentation state such as:

    active_view
    selected_item
    scroll_position
    search_query
    keyboard_focus
    local_input_text
    animation_state

These are presentation concerns.

The Desktop frontend SHALL NOT store an authoritative second copy of:

    Workflow state
    Execution state
    Verification state
    Permission policy
    Engineering session lifecycle


-------------------------------------------------------------------------------

# 18. View Replacement Model

The Desktop application SHALL follow the view-replacement model defined by
CC-PRD-012.

The active viewport SHALL contain exactly one primary view.

Possible active views include:

    MainPane
    PermissionView
    FileTreeView
    ReviewView
    TaskView
    CommandPaletteView

Opening a secondary view SHALL replace the current view inside the same
application window.

The Desktop frontend SHALL NOT implement these as independent child windows.

The Main Pane SHALL NOT remain active and scrollable underneath a secondary
view.


-------------------------------------------------------------------------------

# 19. Esc Handling

The Desktop presentation layer SHALL apply view-specific Esc semantics.

    File Tree
        Esc → return to Main Pane.

    Task View
        Esc → return to Main Pane.

    Command Palette
        Esc → return to Main Pane.

    Permission
        Esc → cancel pending permission interaction.

    Review
        Esc → back/discard according to active review state.

Esc SHALL remain a presentation/interaction action.

Esc SHALL NOT directly mutate ExecutionManager.

Esc SHALL NOT automatically cancel an Engineering operation.


-------------------------------------------------------------------------------

# 20. Desktop ↔ Backend Session

The Desktop client SHALL maintain a connection to the application process, but
the application process SHALL own the authoritative engineering session.

The Desktop may request:

    - create session,
    - resume session,
    - inspect session,
    - close session,

through approved application contracts.

The Desktop SHALL NOT persist engineering session state independently.


-------------------------------------------------------------------------------

# 21. Backend Process Lifecycle

The preferred Desktop runtime SHALL use a dedicated local ClaireCoder
application process.

The Desktop shell SHALL be able to determine whether the backend is:

    STARTING
    READY
    BUSY
    DISCONNECTED
    STOPPING
    STOPPED
    FAILED

The lifecycle controller SHALL remain outside the React presentation
components.

The Tauri Desktop runtime SHALL ensure that the required local ClaireCoder
application process is available during normal Desktop startup. Process
supervision MAY be implemented by the Tauri shell or an equivalent approved
lifecycle mechanism.

Process supervision SHALL NOT become engineering orchestration.


-------------------------------------------------------------------------------

# 22. Startup Sequence

The preferred startup lifecycle is:

    Desktop application launch
        ↓
    Validate local environment
        ↓
    Start local ClaireCoder application process
        ↓
    Establish local transport
        ↓
    Perform handshake
        ↓
    Confirm application readiness
        ↓
    Enter Desktop Main Pane

The Boot Screen SHALL present meaningful startup progress.

The Boot Screen SHALL NOT independently perform Engineering Engine startup
logic.

Actual readiness SHALL be determined by the application process.


-------------------------------------------------------------------------------

# 23. Shutdown Sequence

Normal shutdown SHALL conceptually be:

    User exits Desktop
        ↓
    Frontend requests application shutdown / session closure
        ↓
    Application completes safe shutdown behavior
        ↓
    Transport closes
        ↓
    Backend process stops where owned by Desktop
        ↓
    Desktop exits

The Desktop SHALL NOT forcibly terminate the backend during an active
engineering operation unless the user explicitly performs an approved forced
termination action and the application boundary supports it.


-------------------------------------------------------------------------------

# 24. Reconnection

A temporary connection loss SHALL NOT automatically imply engineering failure.

The Desktop client SHOULD:

    1. detect disconnect,
    2. mark the frontend as disconnected,
    3. attempt controlled reconnection,
    4. re-establish protocol state,
    5. request a current application/session snapshot,
    6. resume presentation from authoritative state.

The frontend SHALL NOT replay arbitrary historical UI mutations to reconstruct
truth.

The backend/application snapshot SHALL be authoritative after reconnection.


-------------------------------------------------------------------------------

# 25. Reconnection Failure

If reconnection cannot be established, the Desktop SHALL clearly indicate:

    Application unavailable.

It MAY offer:

    reconnect
    restart application
    exit

The frontend SHALL NOT claim:

    completed
    failed
    cancelled

merely because the transport was lost.


-------------------------------------------------------------------------------

# 26. Credential Boundary

Provider credentials SHALL remain outside the React presentation layer.

The React frontend SHALL NOT:

    - store API keys in localStorage,
    - store API keys in sessionStorage,
    - embed API keys in JavaScript source,
    - transmit credentials through ordinary UI state without a protected
      application endpoint,
    - write plaintext provider secrets into UI logs.

Credential handling SHALL occur through the application/configuration boundary.

The preferred persistent credential mechanism SHALL be the host operating
system's secure credential/keychain facility.

The backend/application configuration layer SHALL be responsible for:

    - reading credentials,
    - writing credentials,
    - selecting provider credentials,
    - supplying credentials to ModelGateway.

The Desktop frontend MAY request operations such as:

    set provider credential
    remove provider credential
    test provider credential

through a protected application/configuration interface.

The frontend SHALL receive masked or status-oriented credential information
rather than raw secret values wherever possible.


-------------------------------------------------------------------------------

# 27. Environment / Configuration Integration

The application configuration layer SHALL remain the authoritative provider
configuration layer.

The Desktop GUI SHALL NOT define an independent provider configuration format.

The same configuration architecture SHALL be usable by:

    CLI
    TUI
    Desktop GUI

A future configuration system MAY support sources such as:

    - environment variables,
    - secure OS credential store,
    - project configuration,
    - user configuration,

but the precedence and exact format SHALL be defined by the configuration
implementation/architecture rather than the Desktop React layer.


-------------------------------------------------------------------------------

# 28. Provider Independence

The Desktop GUI SHALL remain provider-independent.

It SHALL NOT directly import:

    OpenAI SDK
    Anthropic SDK
    Google SDK
    Groq SDK
    provider-specific runtime libraries

The Desktop SHALL communicate through the application/Model Gateway boundary.

The Desktop MAY display:

    provider name
    model name
    endpoint status

through normalized application metadata.


-------------------------------------------------------------------------------

# 29. Local Security

The backend SHALL bind only to the local interface for the normal Desktop
runtime.

The application SHALL avoid exposing an unauthenticated remote service.

The local transport SHOULD use an application-specific ephemeral connection
endpoint.

Where practical, the bootstrap handshake SHOULD include a short-lived local
connection token so that unrelated local processes cannot trivially impersonate
the Desktop client.

The token SHALL not be persisted as a long-term credential.

The exact bootstrap-token mechanism SHALL be implemented by the Desktop runtime.


-------------------------------------------------------------------------------

# 30. Frontend Authorization Boundary

The Desktop frontend is not an authorization authority.

Any operation requiring engineering authorization SHALL cross the application
boundary.

The Desktop frontend SHALL not treat:

    button visibility
    route visibility
    disabled controls
    React state

as security authorization.

Backend/application validation SHALL remain authoritative.


-------------------------------------------------------------------------------

# 31. Error Model

The Desktop transport/application boundary SHALL distinguish at minimum:

    INVALID_REQUEST
    UNAUTHORIZED_OPERATION
    APPLICATION_ERROR
    TRANSPORT_ERROR
    VALIDATION_ERROR
    NOT_FOUND
    CONFLICT
    DISCONNECTED
    PROTOCOL_ERROR

The exact error taxonomy MAY expand during implementation.

The frontend SHALL present a meaningful user-facing representation while
retaining the underlying error category for diagnostics.


-------------------------------------------------------------------------------

# 32. Logging

The Desktop frontend SHALL NOT log provider credentials or secrets.

The backend SHALL avoid logging:

    - API keys,
    - access tokens,
    - secret configuration values.

Request identifiers SHOULD be available for correlating Desktop-visible errors
with backend diagnostics.


-------------------------------------------------------------------------------

# 33. Protocol Versioning

The local Desktop transport SHALL include a protocol version.

The backend and Desktop SHALL verify compatibility during handshake.

Incompatible versions SHALL fail explicitly.

Protocol evolution SHOULD remain backward-compatible where practical, but no
implicit compatibility SHALL be assumed.


-------------------------------------------------------------------------------

# 34. Testing Architecture

The Desktop architecture SHALL be testable independently of real model
credentials.

Tests SHALL include:

## Transport Unit Tests

    - message encoding,
    - message decoding,
    - request IDs,
    - response correlation,
    - event sequencing,
    - protocol versioning.

## Connection Tests

    - connect,
    - handshake,
    - disconnect,
    - reconnect,
    - backend unavailable.

## Application Integration Tests

    - objective submission,
    - streaming events,
    - permission request,
    - permission response,
    - Tool activity,
    - Verification activity,
    - Workflow activity,
    - session operations.

## Security Tests

Verify that:

    - credentials do not appear in frontend source,
    - credentials do not appear in frontend logs,
    - provider SDKs are absent from the React boundary,
    - backend validation remains authoritative,
    - malformed requests are rejected.

## Architectural Tests

Verify that the Desktop frontend cannot:

    - execute Tools directly,
    - mutate Workflow directly,
    - mutate Execution directly,
    - mutate Verification directly,
    - make Permission decisions,
    - instantiate a second Engineering Engine.


-------------------------------------------------------------------------------

# 35. Rejected Alternatives

## 35.1 Engineering Engine Inside React

REJECTED.

React SHALL remain a presentation/frontend environment.

Embedding the Engineering Engine would violate frontend separation and make
the Desktop application responsible for engineering lifecycle ownership.

## 35.2 Direct Python Imports From React

REJECTED.

React SHALL communicate through the local application boundary.

## 35.3 Separate Desktop Engineering Engine

REJECTED.

There SHALL be exactly one authoritative Engineering Engine.

## 35.4 REST-Only Communication

REJECTED as the primary transport.

REST alone would require a separate streaming mechanism for the real-time
application event stream, creating two communication paths for the same
frontend.

A local WebSocket provides a unified bidirectional channel.

## 35.5 Browser localStorage for API Keys

REJECTED.

Provider credentials must not be persisted in browser storage.

## 35.6 Plaintext Credential Files as the Preferred Secret Store

REJECTED as the preferred persistent mechanism.

The operating system secure credential store is preferred.

## 35.7 Child Window Per Panel

REJECTED.

Desktop panels SHALL replace the active view inside the same fixed application
window.

## 35.8 Frontend-Owned Permission State

REJECTED.

PermissionEngine remains authoritative.


-------------------------------------------------------------------------------

# 36. Consequences

## Positive

This decision provides:

    - one Engineering Engine,
    - one approved application boundary,
    - a real graphical frontend,
    - streaming event delivery,
    - transport independence,
    - shared CLI/Desktop application semantics,
    - clean credential isolation,
    - controlled local security,
    - predictable reconnection behavior,
    - testable frontend/backend separation.

It also allows future frontends to consume the same application boundary without
rewriting engineering logic.

## Negative

The architecture introduces:

    - another process,
    - transport protocol maintenance,
    - lifecycle/reconnection handling,
    - Desktop packaging complexity.

These costs are accepted because they produce a clean frontend/application
boundary.

## Neutral

The exact WebSocket message schema and Tauri IPC implementation details remain
implementation-level concerns unless explicitly promoted into a future ADR.


-------------------------------------------------------------------------------

# 37. Implementation Order

The Desktop implementation SHOULD proceed in this order:

    1. Local application service boundary
           ↓
    2. Transport protocol / handshake
           ↓
    3. Backend process lifecycle
           ↓
    4. Desktop Tauri shell
           ↓
    5. React application shell
           ↓
    6. Main Pane
           ↓
    7. Action Log streaming
           ↓
    8. Prompt / command integration
           ↓
    9. Claire graphical identity
           ↓
    10. Permission View
           ↓
    11. File Tree View
           ↓
    12. Review View
           ↓
    13. Task View
           ↓
    14. Command Palette
           ↓
    15. Session / persistence integration
           ↓
    16. Reconnection / failure handling
           ↓
    17. Credential/configuration integration
           ↓
    18. Packaging / installer preparation
           ↓
    19. Desktop integration tests
           ↓
    20. Final Desktop validation

This order SHALL NOT require rewriting the Engineering Engine.


-------------------------------------------------------------------------------

# 38. Relationship With Other Documents

## CC-PRD-012

Defines the Desktop GUI product requirements.

CC-ADR-008 defines the architecture used to satisfy those requirements.

## CC-PRD-011

Defines the terminal/CLI frontend.

The Desktop GUI shares application and interaction semantics with the terminal
but remains a separate presentation surface.

## CC-ADR-007

Defines the terminal/CLI frontend architecture.

CC-ADR-008 does not replace CC-ADR-007.

## CC-ADR-001

Defines core subsystem boundaries and Engineering Engine responsibilities.

CC-ADR-008 SHALL preserve those boundaries.

## CC-ADR-005

Defines Interaction, Modes, and Commands.

The Desktop GUI consumes those interaction semantics.

## CC-ADR-006

Defines Permission and autonomy architecture.

The Desktop GUI presents permission interaction but does not become the
authority.

## CC-PRD-002

Defines Model Gateway abstraction.

Provider credentials and model interactions remain behind this boundary.


-------------------------------------------------------------------------------

# 39. AI Instructions

When implementing CC-ADR-008:

    1. Treat CC-PRD-012 as the authoritative Desktop product requirement.
    2. Treat DESKTOP-DESIGN.md as the authoritative Desktop UX specification.
    3. Use Tauri + React for the Desktop frontend.
    4. Keep the Desktop frontend as a thin adapter.
    5. Keep ClaireCoderV1 as the authoritative application boundary.
    6. Use a local WebSocket as the primary Desktop ↔ Application transport.
    7. Bind the backend to loopback for normal Desktop operation.
    8. Use a dynamic local port rather than a permanent public port.
    9. Implement an explicit protocol handshake.
    10. Use request IDs for request/response correlation.
    11. Preserve ordered streaming events.
    12. Do not expose private subsystem objects to React.
    13. Do not execute Tools from React.
    14. Do not make Permission decisions in React.
    15. Keep Workflow authoritative in WorkflowManager.
    16. Keep Execution authoritative in ExecutionManager.
    17. Keep Verification authoritative in VerificationEngine.
    18. Keep provider logic behind ModelGateway.
    19. Do not store provider credentials in React localStorage/sessionStorage.
    20. Do not embed provider credentials in frontend source.
    21. Use the backend/application configuration layer for credentials.
    22. Prefer the operating-system secure credential store for persistent
        provider secrets.
    23. Do not create a second session or persistence authority.
    24. Keep the Boot Screen presentation-only.
    25. Keep one active Desktop view at a time.
    26. Do not implement panels as separate windows.
    27. Preserve all documented Esc semantics.
    28. Preserve keyboard/mouse parity.
    29. Preserve 919 × 635 reference geometry.
    30. Do not allow content to force automatic window growth.
    31. Use the canonical Claire graphical assets.
    32. Preserve all nine mascot states.
    33. Handle disconnects explicitly.
    34. Never claim engineering success merely because transport state changed.
    35. Use mocks/fakes where real providers are unnecessary for tests.
    36. Preserve the approved V1 regression suite.
    37. Do not introduce a second Engineering Engine.
    38. Do not introduce speculative distributed infrastructure.
    39. Treat this ADR as the authoritative architecture decision for the
        ClaireCoder Desktop frontend unless explicitly superseded.


-------------------------------------------------------------------------------

# 40. Decision Status

This ADR is currently:

    DRAFT

It SHALL become final only after:

    CC-PRD-012
        +
    CC-ADR-008
        +
    DESKTOP-DESIGN.md
        ↓
    Independent review
        ↓
    Documentation approval

Only after approval SHALL Desktop implementation authorization be issued.


###############################################################################

END OF CC-ADR-008
###############################################################################