###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Product Requirements Document
#
# Document Number : CC-PRD-003
# Title           : ClaireCoder Tool & Skill System
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

The ClaireCoder Tool & Skill System provides the capability layer through
which ClaireCoder can perform engineering operations and load reusable
engineering expertise.

The system SHALL maintain a clear distinction between:

    TOOLS
        Executable capabilities.

    SKILLS
        Reusable instructions, methodologies, workflows, references, and
        engineering expertise.

Tools SHALL perform operations.

Skills SHALL influence how ClaireCoder approaches work.

Neither system SHALL be tightly coupled to a specific model provider.

The system SHALL support built-in capabilities as well as extensible
community and user-provided capabilities.

ClaireCoder SHALL make adding a Skill intentionally simple.

Skills MAY originate from:

- the ClaireCoder built-in roster,
- curated collections,
- GitHub repositories,
- local directories,
- user-created Skills,
- compatible third-party sources.

The system SHALL allow users to select which Skills they want installed or
enabled during ClaireCoder setup.

-------------------------------------------------------------------------------

# 2. Product Goal

The goal of CC-PRD-003 is to create an extensible capability ecosystem that
allows ClaireCoder to grow without modifying its Engineering Engine for every
new capability.

The intended model is:

    Engineering Engine
           │
           ├───────────────┐
           ▼               ▼
        Skills            Tools
           │               │
           │               ▼
           │          Executable
           │          Capabilities
           │
           ▼
      Engineering
       Expertise

Skills and Tools SHALL remain independently replaceable.

-------------------------------------------------------------------------------

# 3. Problem Statement

A coding agent becomes limited if every engineering behavior must be
implemented directly inside its core.

ClaireCoder needs to support:

- reusable engineering methodologies,
- specialized coding practices,
- UI/UX expertise,
- repository practices,
- testing practices,
- anti-slop guidance,
- project-specific expertise,
- external community contributions,
- executable development operations.

These concerns should not be hard-coded into the Engineering Engine.

The Tool & Skill System therefore provides an extension boundary.

-------------------------------------------------------------------------------

# 4. Scope

## 4.1 In Scope

This PRD covers:

- Tool architecture.
- Skill architecture.
- Tool registration.
- Skill registration.
- Tool discovery.
- Skill discovery.
- Skill installation.
- Skill enablement.
- Skill disabling.
- Skill removal.
- Built-in Skill roster.
- Skill collections.
- User-selected Skill installation.
- Local Skill sources.
- GitHub Skill sources.
- Third-party Skill sources.
- User-created Skills.
- Skill metadata.
- Skill versioning.
- Skill dependencies.
- Skill activation.
- Skill retrieval.
- Tool discovery.
- Tool registration.
- Tool invocation interface.
- Tool result handling.
- Tool metadata.
- Tool capability declarations.
- Tool validation.
- Tool isolation.
- Tool permission integration.
- Extension lifecycle.

-------------------------------------------------------------------------------

## 4.2 Out of Scope

This PRD SHALL NOT define:

- the Engineering Engine itself,
- model provider implementation,
- model inference,
- final Permission Engine architecture,
- complete Workflow architecture,
- repository intelligence implementation,
- final CLI/TUI design,
- third-party marketplace infrastructure,
- automatic unrestricted Skill installation,
- unrestricted Tool execution,
- distributed Tool execution infrastructure.

-------------------------------------------------------------------------------

# 5. Core Distinction

ClaireCoder SHALL preserve the following distinction.

## Tool

A Tool is an executable capability.

Examples:

- read file,
- write file,
- edit file,
- search repository,
- execute command,
- run tests,
- inspect git state.

A Tool produces an operation or result.

## Skill

A Skill is reusable engineering expertise.

A Skill MAY contain:

- instructions,
- methodology,
- constraints,
- references,
- examples,
- decision guidance,
- supporting resources.

A Skill influences agent behavior but is not itself an executable operation.

-------------------------------------------------------------------------------

# 6. Design Philosophy

ClaireCoder SHALL NOT become a monolithic collection of hard-coded agent
behaviors.

Instead:

    CORE
      │
      ├── Tools
      │
      ├── Skills
      │
      ├── Workflows
      │
      └── Models

shall remain modular.

The addition of a new Skill SHOULD NOT require modifying the Engineering
Engine.

The addition of a new Tool SHOULD NOT require rewriting the Engineering
Engine.

-------------------------------------------------------------------------------

# 7. Tool Architecture

The Tool System SHALL provide a normalized interface for executable
capabilities.

Conceptual flow:

    Engineering Engine
            ↓
        Tool Request
            ↓
      Permission Engine
            ↓
           Tool
            ↓
       Tool Execution
            ↓
        Tool Result
            ↓
      Engineering Engine

The Tool System SHALL NOT bypass the Permission Engine.

-------------------------------------------------------------------------------

# 8. Tool Categories

The architecture SHALL support Tool categories such as:

- filesystem,
- repository,
- shell,
- search,
- testing,
- build,
- version control,
- browser,
- web,
- image/vision,
- process,
- package management,
- project-specific tools.

The category system SHALL remain extensible.

-------------------------------------------------------------------------------

# 9. Tool Metadata

Each Tool SHOULD declare:

- identifier,
- name,
- description,
- version,
- category,
- input schema,
- output schema,
- permissions required,
- platform requirements,
- dependencies,
- availability state.

Tool metadata SHALL allow the Engineering Engine to understand whether a Tool
is suitable for a requested operation.

-------------------------------------------------------------------------------

# 10. Tool Invocation

The Engineering Engine SHALL request Tools through a normalized Tool
interface.

Conceptually:

    TOOL REQUEST
        │
        ├── Tool ID
        ├── Arguments
        ├── Task ID
        └── Session ID
                ↓
          Permission Check
                ↓
            Execution
                ↓
             Result

The exact invocation schema SHALL be determined during implementation.

-------------------------------------------------------------------------------

# 11. Tool Input Validation

Tools SHALL validate their input before execution.

Invalid input SHALL produce a structured Tool failure.

The Tool System SHALL not assume that model-generated Tool arguments are
correct.

-------------------------------------------------------------------------------

# 12. Tool Result Contract

A Tool result SHOULD contain:

- success state,
- output,
- structured metadata,
- error information where applicable,
- execution information where useful.

The Engineering Engine SHALL be able to distinguish:

    SUCCESS
    FAILURE
    DENIED
    CANCELLED
    TIMEOUT
    UNAVAILABLE

-------------------------------------------------------------------------------

# 13. Tool Discovery

The Tool System SHOULD expose available Tools to the Engineering Engine
based on:

- current Mode,
- current Workflow,
- installed capabilities,
- platform,
- permissions,
- Task requirements.

The system SHOULD avoid exposing irrelevant Tools unnecessarily.

-------------------------------------------------------------------------------

# 14. Tool Availability

A Tool MAY be:

- installed,
- enabled,
- disabled,
- unavailable,
- incompatible,
- blocked by permissions.

The Tool System SHALL represent these states explicitly.

-------------------------------------------------------------------------------

# 15. Tool Permissions

Tool execution SHALL remain subordinate to the Permission Engine.

The Tool System SHALL provide enough metadata for the Permission Engine to
make an authorization decision.

Examples:

    READ FILE
    WRITE FILE
    EXECUTE COMMAND
    NETWORK ACCESS
    DELETE FILE
    MODIFY REPOSITORY

The Tool itself SHALL not independently grant permission.

-------------------------------------------------------------------------------

# 16. Tool Isolation

Tools SHALL remain isolated from the Engineering Engine.

The Engineering Engine SHALL request capabilities rather than importing
Tool-specific implementation logic.

This allows Tools to be:

- replaced,
- extended,
- disabled,
- platform-specific.

-------------------------------------------------------------------------------

# 17. Skill Architecture

A Skill SHALL represent reusable engineering expertise.

A Skill MAY define:

- purpose,
- instructions,
- methodology,
- constraints,
- preferred practices,
- examples,
- supporting references,
- required Tools,
- compatible environments.

A Skill SHALL NOT need to contain executable code.

A Skill MAY reference Tools when its methodology requires executable
capabilities.

-------------------------------------------------------------------------------

# 18. Skill Metadata

Each Skill SHOULD declare:

- identifier,
- name,
- description,
- version,
- author/source,
- license information where available,
- source location,
- category,
- dependencies,
- required Tools,
- compatibility,
- activation state.

Metadata SHALL be sufficient for the user to understand what they are
installing.

-------------------------------------------------------------------------------

# 19. Skill Sources

The Skill System SHALL support three primary acquisition paths.

## 19.1 Manual

The user directly provides or creates a Skill.

Example:

    User-created local Skill

## 19.2 Collection

The user selects a curated Skill Collection.

Example:

    ClaireCoder Recommended Collection
        ├── Stop Slop
        ├── Impeccable
        ├── Caveman
        └── Ponytail

The exact default roster SHALL be determined through the Skill research and
final product configuration.

## 19.3 Third Party

The user obtains a Skill from an external source.

Examples:

- GitHub repository,
- local directory,
- compatible third-party source.

These acquisition paths SHALL converge into the same Skill registration
system.

-------------------------------------------------------------------------------

# 20. Skill Installation Flow

The conceptual installation flow SHALL be:

    SOURCE
      ↓
    DISCOVER
      ↓
    INSPECT METADATA
      ↓
    VALIDATE
      ↓
    USER CONFIRMATION
      ↓
    INSTALL
      ↓
    REGISTER
      ↓
    ENABLE / DISABLE

The system SHALL not execute arbitrary third-party Skill content merely
because it was discovered.

-------------------------------------------------------------------------------

# 21. Setup Skill Roster

During ClaireCoder setup, the user SHALL be able to select Skills from the
available roster.

The setup flow SHOULD provide:

- Skill name,
- short description,
- source,
- version,
- category,
- selection state.

The user SHALL be able to:

- select a Skill,
- deselect a Skill,
- inspect Skill information,
- continue without optional Skills.

-------------------------------------------------------------------------------

# 22. Built-in Skills

ClaireCoder SHALL support a built-in Skill roster.

The roster MAY contain Skills such as:

- Stop Slop,
- Impeccable,
- Caveman,
- Ponytail,
- UI/UX-oriented Skills,
- Open Design-oriented Skills,
- additional engineering Skills.

The exact roster SHALL remain configurable.

Skills SHALL not become inseparable from the ClaireCoder core.

-------------------------------------------------------------------------------

# 23. Stop Slop

Stop Slop SHALL be treated as an external Skill rather than hard-coded into
the Engineering Engine.

When installed and enabled, it MAY influence output quality by providing
guidance against repetitive, generic, low-quality, or stereotypical AI
writing and implementation behavior.

ClaireCoder SHALL load the Skill according to the standard Skill mechanism.

The Skill SHALL remain independently replaceable or removable.

-------------------------------------------------------------------------------

# 24. Skill Collections

A Collection SHALL be a curated group of Skills.

A Collection MAY contain:

- Skills,
- metadata,
- versions,
- compatibility information,
- descriptions,
- recommended configuration.

Installing a Collection SHALL NOT force the user to permanently retain every
Skill inside it.

The user SHALL be able to review and select its contents where practical.

-------------------------------------------------------------------------------

# 25. Third-Party Skills

Third-party Skills SHALL be supported.

The system SHALL display available source information before installation.

Third-party Skills SHOULD be treated as untrusted extensions until validated.

ClaireCoder SHALL not assume that an external Skill is safe merely because
it is hosted on a recognized platform.

-------------------------------------------------------------------------------

# 26. GitHub Skills

The Skill System SHALL support importing Skills from GitHub-compatible
sources.

A GitHub Skill source MAY identify:

- repository,
- path,
- revision or version,
- Skill metadata.

The system SHOULD support installing a Skill from a repository without
requiring the user to manually copy its contents into the ClaireCoder
installation.

-------------------------------------------------------------------------------

# 27. Local Skills

Users SHALL be able to add Skills from local sources.

Examples:

    ./my-skill/
    ./skills/ui-review/
    ~/clairecoder-skills/example/

Local Skills SHALL use the same registration and validation process as
external Skills.

-------------------------------------------------------------------------------

# 28. User-Created Skills

Users SHALL be able to create Skills without modifying ClaireCoder core
source code.

A minimal user-created Skill SHOULD require only:

- identifier,
- instructions,
- metadata.

The system SHOULD make the process intentionally simple.

-------------------------------------------------------------------------------

# 29. Skill Validation

Before a Skill becomes active, ClaireCoder SHOULD validate:

- required metadata,
- supported format,
- dependency declarations,
- source integrity,
- compatibility,
- referenced resources.

Validation SHALL not guarantee that a Skill is trustworthy.

Trust and permissions SHALL remain separate concerns.

-------------------------------------------------------------------------------

# 30. Skill Dependencies

A Skill MAY depend on:

- another Skill,
- a Tool,
- a runtime capability,
- an external resource.

The system SHALL detect missing dependencies before activation where practical.

A missing optional dependency SHOULD not necessarily prevent installation.

A missing required dependency SHOULD prevent activation until resolved.

-------------------------------------------------------------------------------

# 31. Skill Activation

A Skill MAY be:

- installed,
- enabled,
- disabled,
- unavailable,
- incompatible,
- removed.

Installation SHALL not automatically imply permanent activation.

The active Skill set MAY vary by:

- Mode,
- Workflow,
- project,
- user configuration.

-------------------------------------------------------------------------------

# 32. Skill Retrieval

The system SHALL make relevant Skills available to the Engineering Engine
when appropriate.

Skill retrieval MAY use:

- explicit user selection,
- Mode configuration,
- Workflow requirements,
- Task requirements,
- Skill metadata,
- semantic relevance.

The system SHOULD avoid loading every installed Skill into every model
context.

-------------------------------------------------------------------------------

# 33. Skill Context Management

The Skill System SHALL provide Skills to the model through controlled
context injection.

A Skill SHALL not automatically consume the entire model context merely
because it is installed.

The system SHOULD provide only the relevant Skill material for the current
Task.

-------------------------------------------------------------------------------

# 34. Skill Priority

When multiple Skills are active, the system SHALL provide a mechanism for
resolving conflicting guidance.

Possible priority sources include:

1. explicit user instruction,
2. higher-priority system constraints,
3. active Workflow requirements,
4. Skill priority,
5. general Skill guidance.

The exact priority implementation SHALL be finalized during architecture
implementation.

-------------------------------------------------------------------------------

# 35. Skill Conflicts

The Skill System SHOULD detect obvious conflicts where possible.

Examples:

    Skill A:
    "Use framework X."

    Skill B:
    "Do not use framework X."

The system SHOULD expose the conflict rather than silently pretending that
both instructions are compatible.

The Engineering Engine MAY request clarification where the conflict affects
the task materially.

-------------------------------------------------------------------------------

# 36. Skill Versioning

Skills SHOULD support versions.

The system SHOULD retain enough metadata to identify:

- installed version,
- available version,
- source,
- update state.

Updating a Skill SHALL not silently change unrelated ClaireCoder core
behavior.

-------------------------------------------------------------------------------

# 37. Skill Updates

The user SHOULD be able to:

- update a Skill,
- keep the current version,
- disable updates,
- remove the Skill.

Automatic updates SHALL not be required for V1.

If implemented later, update behavior SHALL respect user trust and
configuration.

-------------------------------------------------------------------------------

# 38. Tool and Skill Relationship

Skills MAY recommend or require Tools.

Example:

    UI/UX Skill
         ↓
    Requires:
         ├── screenshot Tool
         ├── filesystem Tool
         └── browser Tool

The Skill SHALL describe the requirement.

The Skill SHALL not directly bypass Tool registration or permissions.

-------------------------------------------------------------------------------

# 39. Tool and Skill Independence

A Tool SHALL be usable without a Skill.

A Skill SHALL be installable without immediately executing Tools.

This separation SHALL allow:

- generic Tools,
- specialized Skills,
- multiple Skills using the same Tool,
- multiple Tools supporting the same Skill.

-------------------------------------------------------------------------------

# 40. Extension Registry

ClaireCoder SHALL maintain a registry of installed extensions.

The registry SHALL represent at least:

- Tools,
- Skills,
- source,
- version,
- installation state,
- activation state,
- compatibility.

The registry SHALL not require a remote marketplace.

-------------------------------------------------------------------------------

# 41. Extension Sources

The architecture SHALL remain source-agnostic.

A source MAY be:

- built-in,
- local,
- GitHub,
- curated collection,
- third-party source.

The source SHALL be represented as metadata rather than embedded into the
Engineering Engine.

-------------------------------------------------------------------------------

# 42. Trust Boundary

Third-party extensions SHALL be treated as potentially untrusted.

The system SHALL distinguish:

    DISCOVERED
        ≠
    VALIDATED
        ≠
    TRUSTED
        ≠
    ENABLED

A Skill containing only instructions SHALL still be treated as external
content.

A Tool capable of executing operations SHALL receive stronger permission
controls.

-------------------------------------------------------------------------------

# 43. Security

The Tool & Skill System SHALL:

- preserve Permission Engine authority,
- avoid unrestricted execution,
- isolate third-party Tools where practical,
- validate extension metadata,
- avoid exposing secrets to Skills unnecessarily,
- preserve source information,
- provide removal/disable mechanisms.

The V1 implementation SHALL favor explicit user control over unrestricted
extension automation.

-------------------------------------------------------------------------------

# 44. Performance

The system SHOULD avoid loading all installed Skills into memory or model
context simultaneously.

Skills SHOULD be loaded when required.

Tool discovery SHOULD remain lightweight.

The extension registry SHALL not require a remote service.

-------------------------------------------------------------------------------

# 45. Compatibility

The Tool & Skill System SHALL remain compatible with:

- local ClaireCoder installations,
- hosted models,
- local models,
- different Model Profiles,
- different Modes,
- different Workflows.

Skills SHALL not depend on a specific model unless explicitly declared.

Tools SHALL not depend on a specific model.

-------------------------------------------------------------------------------

# 46. Acceptance Criteria

CC-PRD-003 SHALL be considered successfully implemented when:

### AC-001 — Tool/Skill Separation

Tools and Skills are represented as distinct extension types.

### AC-002 — Tool Registration

A Tool can be registered without modifying the Engineering Engine.

### AC-003 — Tool Invocation

The Engineering Engine can request a registered Tool.

### AC-004 — Permission Boundary

Tool execution passes through the Permission Engine.

### AC-005 — Tool Results

Tool results are returned through a normalized interface.

### AC-006 — Skill Registration

A Skill can be registered without modifying ClaireCoder core.

### AC-007 — Manual Skills

A user can add a locally created Skill.

### AC-008 — Local Source

A Skill can be installed from a local source.

### AC-009 — GitHub Source

A compatible Skill can be installed from a GitHub source.

### AC-010 — Collection

A user can inspect and select Skills from a Collection.

### AC-011 — Third Party

A user can add a Skill from a third-party source.

### AC-012 — Setup Roster

The setup flow can present a Skill roster and allow user selection.

### AC-013 — Enable/Disable

Installed Skills can be enabled and disabled.

### AC-014 — Skill Retrieval

Relevant enabled Skills can be supplied to the Engineering Engine.

### AC-015 — Context Control

Installed Skills are not automatically injected in their entirety into
every model request.

### AC-016 — Metadata

Skills and Tools expose sufficient metadata for discovery and validation.

### AC-017 — Dependencies

Required Skill dependencies can be detected.

### AC-018 — Versioning

Installed Skill versions can be identified.

### AC-019 — Extension Registry

Installed Tools and Skills can be enumerated through a registry.

### AC-020 — Third-Party Trust

External extensions are distinguishable from built-in extensions.

### AC-021 — Removal

Users can disable or remove installed Skills.

### AC-022 — Tool Isolation

Tool implementations remain outside the Engineering Engine.

### AC-023 — Skill Independence

Skill implementations remain outside the Engineering Engine.

### AC-024 — Model Independence

Skills and Tools do not require a specific model provider.

### AC-025 — V1 Simplicity

The system does not require a remote marketplace or distributed extension
infrastructure.

-------------------------------------------------------------------------------

# 47. Non-Functional Requirements

## NFR-001 — Extensibility

New Tools and Skills SHALL be addable without modifying the Engineering
Engine.

## NFR-002 — Simplicity

Adding a basic Skill SHOULD require minimal configuration.

## NFR-003 — Discoverability

Users SHOULD be able to understand what an extension does before enabling it.

## NFR-004 — Safety

Executable extensions SHALL remain subject to permission controls.

## NFR-005 — Isolation

Extension implementations SHALL remain isolated from core orchestration.

## NFR-006 — Portability

The Skill system SHALL support local and external Skill sources.

## NFR-007 — Reversibility

Users SHALL be able to disable or remove extensions.

## NFR-008 — Maintainability

The registry and extension lifecycle SHALL remain understandable and
testable.

-------------------------------------------------------------------------------

# 48. Deliverables

Implementation of CC-PRD-003 SHALL produce:

1. Tool abstraction.
2. Skill abstraction.
3. Tool registry.
4. Skill registry.
5. Tool metadata system.
6. Skill metadata system.
7. Tool registration.
8. Skill registration.
9. Tool invocation interface.
10. Tool result interface.
11. Tool discovery.
12. Skill discovery.
13. Skill installation lifecycle.
14. Skill enable/disable lifecycle.
15. Skill removal.
16. Local Skill source support.
17. GitHub Skill source support.
18. Collection support.
19. Third-party Skill source support.
20. User-created Skill support.
21. Skill dependency handling.
22. Skill version metadata.
23. Skill retrieval.
24. Skill context loading.
25. Extension trust metadata.
26. Permission integration.
27. Extension validation.
28. automated tests covering Tool and Skill lifecycle behavior.

-------------------------------------------------------------------------------

# 49. Implementation Constraints

The implementation SHALL NOT:

- hard-code individual Skills into the Engineering Engine,
- hard-code individual Tools into the Engineering Engine,
- bypass Permission Engine checks,
- automatically trust third-party extensions,
- require a remote Skill marketplace,
- require every user to install multiple Skills,
- require multiple models,
- inject every installed Skill into every prompt,
- require every Tool to be available on every platform,
- couple Skills to a single model provider.

-------------------------------------------------------------------------------

# 50. Relationship With Other PRDs

CC-PRD-001

ClaireCoder Core Engineering Engine

Consumes Tools and Skills through the capability interfaces defined here.

CC-PRD-002

ClaireCoder Model Gateway & Provider System

Provides the model execution capabilities used by Skills and the Engineering
Engine.

CC-PRD-003

ClaireCoder Tool & Skill System

Defines executable Tools and reusable Skills.

CC-PRD-004

ClaireCoder Workflow, Context & Engineering Session System

Defines how Skills and Tools participate in Workflows, Context
retrieval, and persistent Engineering Sessions.

CC-PRD-005

ClaireCoder Interaction, Modes & Commands

Defines user-facing interaction with Skills, Tools, Modes, and Commands.

CC-PRD-006

ClaireCoder Permission, Autonomy & Security

Defines the authoritative permission and autonomy architecture.

-------------------------------------------------------------------------------

# 51. Implementation Order

The recommended implementation order for this PRD is:

    1. Extension metadata model
            ↓
    2. Tool abstraction
            ↓
    3. Skill abstraction
            ↓
    4. Extension registry
            ↓
    5. Tool registration
            ↓
    6. Skill registration
            ↓
    7. Tool discovery
            ↓
    8. Skill discovery
            ↓
    9. Local Skill source
            ↓
   10. GitHub Skill source
            ↓
   11. Collection support
            ↓
   12. Third-party source support
            ↓
   13. Skill validation
            ↓
   14. Skill dependencies
            ↓
   15. Skill activation
            ↓
   16. Skill retrieval
            ↓
   17. Permission integration
            ↓
   18. Tool execution integration
            ↓
   19. Extension lifecycle tests

The implementation SHALL establish the extension contract before building
large numbers of individual extensions.


The V1 documentation set also includes:

CC-PRD-007
    Execution State & Recovery

CC-PRD-008
    Engineering Context & Memory

CC-PRD-009
    Testing & Verification

CC-PRD-010
    Integration & V1 Completion

-------------------------------------------------------------------------------

# 52. Verification Strategy

## Unit Tests

Test:

- Tool metadata,
- Skill metadata,
- registration,
- activation,
- disabling,
- removal,
- dependency resolution,
- validation,
- Tool result states.

## Source Tests

Test:

- local Skill installation,
- GitHub Skill installation,
- Collection installation,
- third-party Skill installation.

## Permission Tests

Test:

- allowed Tool,
- denied Tool,
- permission-required Tool,
- unavailable Tool.

## Retrieval Tests

Test:

- explicit Skill selection,
- relevant Skill retrieval,
- disabled Skill exclusion,
- irrelevant Skill exclusion.

## Lifecycle Test

Demonstrate:

    install
       ↓
    validate
       ↓
    register
       ↓
    enable
       ↓
    retrieve
       ↓
    use
       ↓
    disable
       ↓
    remove

## End-to-End Test

Demonstrate:

    User Task
       ↓
    Engineering Engine
       ↓
    Relevant Skill
       ↓
    Tool Request
       ↓
    Permission
       ↓
    Tool Execution
       ↓
    Result
       ↓
    Engineering Engine

-------------------------------------------------------------------------------

# 53. Out-of-Scope Implementation Decisions

This PRD SHALL NOT prematurely decide:

- exact Skill file format,
- exact Tool schema,
- exact registry database,
- exact GitHub client,
- exact package layout,
- exact marketplace protocol,
- exact sandbox implementation,
- exact extension-signing system,
- exact Skill ranking algorithm,
- exact semantic retrieval implementation.

These decisions SHALL be finalized during implementation or later PRDs where
required.

-------------------------------------------------------------------------------

# 54. Success Definition

ClaireCoder V1 satisfies CC-PRD-003 when new engineering capabilities can be
added without modifying the Engineering Engine.

The resulting architecture SHALL support:

    BUILT-IN
       │
    COLLECTION
       │
    LOCAL
       │
    GITHUB
       │
    THIRD-PARTY
       │
    USER CREATED
       │
       ▼
    EXTENSION REGISTRY
       │
    ┌──┴────┐
    ▼       ▼
  SKILLS   TOOLS
    │       │
    │       ▼
    │   PERMISSION
    │       │
    └───┬───┘
        ▼
  ENGINEERING ENGINE

The system SHALL make extending ClaireCoder easy while keeping executable
operations under explicit permission control.

-------------------------------------------------------------------------------

# 55. AI Instructions

When implementing CC-PRD-003:

1. Treat Tools and Skills as separate extension types.
2. Keep both independent from the Engineering Engine implementation.
3. Keep Tools executable and Skills instructional.
4. Preserve the Tool permission boundary.
5. Support built-in Skills.
6. Support user-created Skills.
7. Support local Skills.
8. Support GitHub Skills.
9. Support curated Skill Collections.
10. Support third-party Skill sources.
11. Allow users to select Skills during setup.
12. Allow users to enable and disable installed Skills.
13. Allow users to remove installed Skills.
14. Preserve Skill metadata and source information.
15. Preserve Skill version information.
16. Detect required Skill dependencies.
17. Do not automatically trust third-party extensions.
18. Do not inject every installed Skill into every model context.
19. Retrieve relevant Skills according to the active engineering context.
20. Keep Skill guidance separate from executable Tool implementation.
21. Allow Skills to reference Tools without bypassing permissions.
22. Preserve model independence.
23. Preserve provider independence.
24. Keep the extension registry local and lightweight.
25. Do not require a remote marketplace for V1.
26. Do not over-engineer extension distribution.
27. Preserve user control over installed and enabled extensions.
28. Preserve ClaireCoder independence from other Claire Ecosystem projects.
29. Treat this PRD as the authoritative product requirement for the Tool &
    Skill System unless explicitly superseded.

###############################################################################

END OF CC-PRD-003

###############################################################################