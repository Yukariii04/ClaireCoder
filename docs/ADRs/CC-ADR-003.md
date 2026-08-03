###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                    Architecture Decision Record
#
# Document Number : CC-ADR-003
# Title           : Tool & Skill Extension Architecture
# Version         : 1.0.0
# Status          : Accepted
#
###############################################################################

# 1. Decision Summary

ClaireCoder SHALL use a unified extension architecture in which Tools and
Skills are separate but complementary systems.

Tools SHALL provide executable capabilities.

Skills SHALL provide reusable expertise, methodology, instructions, and
supporting resources.

A Skill SHALL be able to request or recommend Tools, but SHALL NOT directly
bypass the Permission Engine.

ClaireCoder SHALL support three primary Skill acquisition paths:

1. Manual installation / selection.
2. Curated Skill Collections.
3. Third-party Skill sources.

The architecture SHALL make adding a Skill simple enough that a user does not
need to modify ClaireCoder's core source code.

Tools SHALL have explicit contracts and permission boundaries.

Skills SHALL use progressive loading so that installing many Skills does not
consume the model context window.

The extension architecture SHALL support built-in, community, local, and
future external extensions without coupling them to the Engineering Engine.

-------------------------------------------------------------------------------

# 2. Context

The ClaireCoder RES phase established several requirements.

ClaireCoder is intended to contain a large preinstalled Skill roster, including
specialized engineering and design Skills, while allowing users to choose
which Skills they want during setup.

The intended Skill ecosystem includes:

- built-in Skills,
- curated collections,
- manually selected Skills,
- third-party Skills,
- locally written Skills,
- GitHub-based Skills,
- future external sources.

The user should not have to install every Skill.

The setup process should allow the user to choose from the available roster.

The user should also be able to add additional Skills later from another
source.

At the same time, Skills must not become equivalent to Tools.

A Skill may tell the agent how to perform a task, but the actual ability to
read files, edit files, execute commands, run tests, browse the web, or use
other capabilities must come from Tools.

This separation is necessary for:

- security,
- portability,
- context efficiency,
- reuse,
- extension management.

-------------------------------------------------------------------------------

# 3. Problem

A coding agent can become difficult to maintain if expertise and execution
capabilities are combined.

For example, a UI/UX Skill should not need to implement:

- filesystem access,
- terminal execution,
- browser control,
- image inspection,
- file editing.

Likewise, a terminal Tool should not contain instructions for:

- React architecture,
- accessibility,
- database design,
- UI/UX methodology.

Combining these responsibilities would produce:

- duplicated capabilities,
- unclear security boundaries,
- difficult extension management,
- excessive context usage,
- difficult testing,
- tightly coupled third-party extensions.

ClaireCoder therefore requires two distinct extension concepts.

-------------------------------------------------------------------------------

# 4. Decision

ClaireCoder SHALL use the following conceptual architecture:

                           CLAIRECODER
                                │
                       ENGINEERING ENGINE
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
                 ▼                             ▼
             SKILL SYSTEM                 TOOL SYSTEM
                 │                             │
        ┌────────┼────────┐          ┌─────────┼─────────┐
        │        │        │          │         │         │
      Built-in Collection Third-Party Filesystem Terminal Git
        │        │        │          │         │         │
        │        │        │          Search    Test      Web
        │        │        │          Edit      LSP       MCP
        │        │        │
        └────────┴────────┘
                 │
                 ▼
          Skill Activation
                 │
                 ▼
          Context Engine
                 │
                 ▼
           Model Gateway

All executable Tool operations SHALL pass through:

                    PERMISSION ENGINE
                           │
                    ┌──────┼──────┐
                    ▼      ▼      ▼
                  ALLOW   ASK    DENY

Skills SHALL NOT bypass this boundary.

-------------------------------------------------------------------------------

# 5. Tool Architecture

## 5.1 Tool Definition

A Tool SHALL represent an executable capability available to ClaireCoder.

Examples include:

- read file,
- write file,
- edit file,
- search repository,
- execute terminal command,
- run tests,
- inspect Git,
- perform web search,
- retrieve web content,
- use browser,
- invoke MCP capability.

A Tool SHALL have a defined contract.

-------------------------------------------------------------------------------

## 5.2 Tool Contract

A Tool SHOULD expose:

- Tool name,
- description,
- input schema,
- output schema,
- capability metadata,
- permission requirements,
- execution behavior,
- error behavior.

The Tool contract SHALL be independent from any particular model provider.

-------------------------------------------------------------------------------

## 5.3 Tool Input

Tool inputs SHALL be structured.

The Tool SHALL validate inputs before execution.

Invalid input SHOULD result in a structured Tool error rather than an
unhandled failure.

-------------------------------------------------------------------------------

## 5.4 Tool Output

Tool outputs SHOULD be structured where practical.

The Tool system SHOULD distinguish:

- successful result,
- failure,
- partial result,
- permission denial,
- cancellation,
- timeout.

The Context Engine MAY summarize or persist large Tool results.

-------------------------------------------------------------------------------

## 5.5 Tool Permissions

Every executable Tool SHALL declare or expose its permission requirements.

Examples:

Filesystem Tool:

- read,
- write,
- delete.

Terminal Tool:

- command execution,
- environment access,
- network access where applicable.

Git Tool:

- repository read,
- repository modification,
- remote operations.

The Permission Engine SHALL determine whether the Tool may execute.

-------------------------------------------------------------------------------

# 6. Core Tool Categories

The initial Tool architecture SHALL support the following conceptual
categories.

## 6.1 Filesystem

Capabilities:

- read,
- write,
- edit,
- create,
- rename,
- delete,
- directory inspection.

-------------------------------------------------------------------------------

## 6.2 Search

Capabilities:

- filename search,
- text search,
- symbol search,
- repository search,
- dependency search.

-------------------------------------------------------------------------------

## 6.3 Terminal

Capabilities:

- execute commands,
- inspect output,
- terminate processes,
- retrieve command results.

-------------------------------------------------------------------------------

## 6.4 Git

Capabilities:

- status,
- diff,
- log,
- branch information,
- stage,
- commit,
- restore,
- reset,
- remote operations where enabled.

-------------------------------------------------------------------------------

## 6.5 Testing

Capabilities:

- run tests,
- run selected tests,
- inspect failures,
- collect structured test output.

Testing MAY internally use the Terminal Tool or eventually become a
specialized Tool.

The final implementation SHALL avoid unnecessary duplication.

-------------------------------------------------------------------------------

## 6.6 Diagnostics

Capabilities MAY include:

- linting,
- formatting,
- compiler diagnostics,
- static analysis,
- language-server information.

-------------------------------------------------------------------------------

## 6.7 Web

Capabilities MAY include:

- search,
- retrieval,
- documentation lookup,
- browser interaction.

-------------------------------------------------------------------------------

## 6.8 MCP

MCP capabilities SHALL be exposed through the Tool architecture.

MCP Tools SHALL receive the same fundamental permission treatment as native
Tools.

-------------------------------------------------------------------------------

# 7. Skill Architecture

## 7.1 Skill Definition

A Skill SHALL represent reusable expertise or methodology.

A Skill MAY contain:

- instructions,
- methodology,
- workflows,
- checklists,
- templates,
- references,
- examples,
- supporting files,
- Tool recommendations.

A Skill SHALL not be required to implement the underlying Tools it uses.

-------------------------------------------------------------------------------

# 8. Skill Structure

A Skill SHOULD have a predictable structure.

Conceptually:

Skill
│
├── metadata
├── instructions
├── references
├── examples
├── templates
└── supporting resources

The exact file structure SHALL be determined during implementation.

-------------------------------------------------------------------------------

# 9. Skill Metadata

Skill metadata SHOULD describe:

- Skill name,
- description,
- author,
- source,
- version,
- category,
- tags,
- compatibility,
- required capabilities,
- dependencies,
- trust status.

Metadata SHOULD remain compact enough to be available for Skill discovery
without loading the complete Skill.

-------------------------------------------------------------------------------

# 10. Progressive Skill Loading

ClaireCoder SHALL use progressive Skill loading.

The initial Skill roster SHALL NOT be inserted entirely into model context.

The conceptual flow SHALL be:

Installed Skills
      │
      ▼
Skill Metadata
      │
      ▼
Skill Selection / Relevance
      │
      ▼
Load Skill Instructions
      │
      ▼
Load Supporting References
      │
      ▼
Active Skill Context

This allows ClaireCoder to contain many Skills without consuming the model's
entire context window.

-------------------------------------------------------------------------------

# 11. Skill Activation

A Skill MAY become active through:

- explicit user selection,
- Mode requirements,
- Workflow requirements,
- task relevance,
- explicit command,
- automatic relevance detection.

Automatic activation SHOULD remain transparent to the user.

The interface SHOULD make active Skills inspectable.

-------------------------------------------------------------------------------

# 12. Skill Deactivation

Users SHOULD be able to disable or deactivate Skills.

Possible reasons include:

- conflicting methodologies,
- context reduction,
- temporary specialization,
- user preference,
- debugging.

Deactivation SHALL NOT uninstall the Skill.

-------------------------------------------------------------------------------

# 13. Skill Sources

ClaireCoder SHALL support three primary Skill acquisition paths.

## Path 1 — Manual

The user directly chooses or adds a Skill.

Sources MAY include:

- local files,
- local directories,
- manually created Skill packages.

-------------------------------------------------------------------------------

## Path 2 — Curated Collections

ClaireCoder SHALL support curated Skill Collections.

A Collection represents a group of Skills designed to work together.

Examples MAY include:

- Frontend Collection,
- Backend Collection,
- Full-Stack Collection,
- UI/UX Collection,
- Python Collection,
- Game Development Collection,
- Testing Collection.

The exact collections SHALL be determined later.

During ClaireCoder setup, the user SHALL be able to choose which Collections
to install.

The user SHALL not be forced to install every available Skill.

-------------------------------------------------------------------------------

## Path 3 — Third-Party

Users SHALL be able to add Skills from external sources.

Potential sources include:

- GitHub,
- local repositories,
- URLs,
- community registries,
- future Skill marketplaces.

Third-party Skills SHALL be treated as untrusted by default until the user
explicitly trusts them according to the Permission and Extension system.

-------------------------------------------------------------------------------

# 14. Skill Collection Architecture

A Collection SHALL be a distribution mechanism rather than a fundamentally
different Skill type.

Conceptually:

Collection
    │
    ├── Skill A
    ├── Skill B
    ├── Skill C
    └── Skill D

Installing a Collection SHOULD install or register its constituent Skills.

Users SHOULD be able to:

- install an entire Collection,
- inspect its contents,
- select individual Skills,
- remove individual Skills later.

A Collection SHALL not prevent independent Skill management.

-------------------------------------------------------------------------------

# 15. Setup Experience

During initial ClaireCoder setup, the Skill selection experience SHOULD
provide:

1. Recommended Collections.
2. Individual Skills.
3. Custom Skill source.
4. Skip / configure later.

The user SHOULD be able to:

- choose a Collection,
- choose individual Skills,
- add a custom source,
- continue without optional Skills.

The setup process SHALL not make Skill configuration mandatory beyond the
minimum required ClaireCoder core functionality.

-------------------------------------------------------------------------------

# 16. Preinstalled Skill Roster

ClaireCoder SHALL support a preinstalled roster of Skills.

The roster MAY include specialized Skills such as:

- UI/UX,
- design methodology,
- code quality,
- anti-slop practices,
- repository engineering,
- frontend engineering,
- backend engineering,
- testing,
- documentation,
- architecture,
- debugging.

Specific Skills established by the current research include Impeccable,
Caveman, Ponytail, and Stop Slop. They SHALL be treated as candidate Skills
for later Skill-specific integration decisions.

UI/UX Pro and Open Design are project-requested Skill candidates but are not
yet established by the current RES/RFD research. They SHALL therefore undergo
Skill-specific research before being treated as established Skills.

None of these Skills SHALL be hardcoded into this ADR as mandatory V1 Skills.

-------------------------------------------------------------------------------

# 17. Third-Party Skill Installation

The installation process SHOULD be:

Source
  ↓
Inspect Metadata
  ↓
Validate Structure
  ↓
Determine Trust
  ↓
Show User
  ↓
Install / Reject
  ↓
Register Skill
  ↓
Available for Activation

Installation SHALL not automatically grant unrestricted Tool permissions.

-------------------------------------------------------------------------------

# 18. Local Skill Development

Users SHOULD be able to create Skills locally.

A local Skill SHOULD be discoverable through:

- configured Skill directories,
- project-level Skill directories,
- explicit import commands.

This allows users to create private Skills without publishing them.

-------------------------------------------------------------------------------

# 19. GitHub Skill Installation

GitHub SHALL be considered a supported third-party Skill source.

The system SHOULD allow users to specify a repository or supported path.

ClaireCoder SHALL inspect the source before registration.

The final GitHub source format SHALL be defined during implementation
planning.

-------------------------------------------------------------------------------

# 20. Skill Versioning

Skills SHOULD support versions.

A Skill version MAY be represented by:

- semantic version,
- Git commit,
- release,
- source revision.

ClaireCoder SHOULD retain enough metadata to determine which Skill version
is installed.

Automatic updates SHALL remain optional.

-------------------------------------------------------------------------------

# 21. Skill Dependencies

A Skill MAY declare dependencies on:

- other Skills,
- Tools,
- capabilities,
- external resources.

The dependency system SHALL remain simple.

A Skill SHALL not automatically install arbitrary executable software without
going through the appropriate permission and installation flow.

-------------------------------------------------------------------------------

# 22. Skill Trust

Skill trust SHALL be represented independently from Skill usefulness.

Potential trust states include:

- Built-in,
- Trusted,
- Community,
- Unverified,
- Blocked.

The exact trust model SHALL be finalized in CC-ADR-006.

Trust SHALL influence:

- installation warnings,
- execution permissions,
- automatic activation,
- external Tool access.

-------------------------------------------------------------------------------

# 23. Skill and Tool Relationship

The relationship SHALL be:

Skill
  │
  │ provides expertise
  ▼
Engineering Engine
  │
  │ requests capability
  ▼
Tool
  │
  ▼
Permission Engine
  │
  ▼
Execution

A Skill SHALL not execute arbitrary commands simply because the Skill
instructions request them.

The Tool system and Permission Engine remain authoritative.

-------------------------------------------------------------------------------

# 24. Skill and Model Relationship

Skills SHALL be model-independent.

A Skill SHOULD not contain instructions that assume a single model provider
unless the Skill explicitly declares such a requirement.

The Context Engine SHALL load Skill instructions into whichever model is
currently selected.

-------------------------------------------------------------------------------

# 25. Skill and Mode Relationship

Modes and Skills SHALL remain independent.

A Mode MAY recommend or activate Skills.

A Skill MAY be useful in multiple Modes.

Example:

UI/UX Skill:

- Build Mode,
- Review Mode,
- Research Mode.

The Skill SHALL not become a Mode itself.

-------------------------------------------------------------------------------

# 26. Extension Discovery

ClaireCoder SHOULD provide an extension discovery mechanism.

Discovery MAY include:

- installed Skills,
- available Collections,
- local Skills,
- GitHub Skills,
- community sources.

The system SHALL clearly identify the source of an extension.

-------------------------------------------------------------------------------

# 27. Extension Installation

Extension installation SHOULD use a common lifecycle:

DISCOVER
   ↓
INSPECT
   ↓
VALIDATE
   ↓
TRUST
   ↓
INSTALL
   ↓
REGISTER
   ↓
ACTIVATE

The lifecycle SHALL apply to Skills and future extension types where
appropriate.

-------------------------------------------------------------------------------

# 28. Extension Removal

Users SHOULD be able to remove extensions without affecting the ClaireCoder
core.

Removing a Skill SHALL remove its registration and local resources while
preserving unrelated Skills.

A Collection MAY be removed while allowing individually retained Skills to
remain installed.

-------------------------------------------------------------------------------

# 29. Tool Registry

ClaireCoder SHOULD maintain a Tool registry.

The registry MAY contain:

- Tool identifier,
- name,
- description,
- schema,
- capabilities,
- permissions,
- source,
- availability.

The registry SHALL provide the Engineering Engine with a discoverable set of
available capabilities.

-------------------------------------------------------------------------------

# 30. Skill Registry

ClaireCoder SHOULD maintain a Skill registry.

The registry MAY contain:

- Skill identifier,
- name,
- description,
- version,
- source,
- trust state,
- dependencies,
- activation state,
- metadata.

The registry SHALL not require loading full Skill instructions.

-------------------------------------------------------------------------------

# 31. Extension Isolation

Extensions SHOULD be isolated from internal ClaireCoder implementation
details.

An extension SHOULD interact through public interfaces.

This allows:

- core updates,
- extension compatibility,
- testing,
- version management.

Extensions SHALL not rely on private internal modules unless explicitly
supported.

-------------------------------------------------------------------------------

# 32. Permission Integration

The Tool and Skill systems SHALL integrate with the Permission Engine.

The permission flow SHALL be:

Skill / Workflow / Agent
          │
          ▼
       Tool Request
          │
          ▼
   Permission Engine
          │
     ┌────┼────┐
     ▼    ▼    ▼
   ALLOW ASK DENY
     │
     ▼
 Tool Execution

There SHALL be no alternate execution path.

-------------------------------------------------------------------------------

# 33. Failure Handling

The extension system SHALL distinguish:

- invalid Skill,
- incompatible Skill,
- unavailable Tool,
- missing dependency,
- permission denial,
- installation failure,
- runtime failure.

A Skill failure SHOULD not automatically crash the entire Engineering
Engine.

The Engineering Engine SHOULD be able to continue or request user
intervention where possible.

-------------------------------------------------------------------------------

# 34. Security Considerations

Third-party extensions can contain instructions or executable behavior that
may be unsafe.

Therefore:

- Skills SHALL not bypass permissions.
- Tools SHALL remain permission-controlled.
- Third-party sources SHALL be identifiable.
- Untrusted extensions SHALL not automatically receive privileged access.
- Credentials SHALL not be exposed to Skills unnecessarily.
- Repository content SHALL not automatically become trusted Skill policy.

Detailed security decisions belong to CC-ADR-006.

-------------------------------------------------------------------------------

# 35. Decision Rationale

This architecture was selected because it preserves the distinction between
knowledge and capability.

Tools answer:

"What can ClaireCoder do?"

Skills answer:

"How should ClaireCoder approach this type of work?"

This makes it possible to:

- add expertise without adding executable code,
- add Tools without rewriting Skills,
- reuse Skills across models,
- reuse Tools across Skills,
- control execution centrally,
- install third-party Skills safely,
- maintain a large Skill roster without context overload.

The three acquisition paths also make the Skill ecosystem accessible to both
technical and non-technical users.

-------------------------------------------------------------------------------

# 36. Alternatives Considered

## Alternative A — Skills Contain Their Own Tools

Decision:

REJECTED.

Reason:

This creates duplicated execution capabilities and weakens permission
boundaries.

-------------------------------------------------------------------------------

## Alternative B — Every Skill Is a Tool

Decision:

REJECTED.

Reason:

Skills provide expertise and instructions, not necessarily executable
capabilities.

-------------------------------------------------------------------------------

## Alternative C — Only Built-in Skills

Decision:

REJECTED.

Reason:

The ClaireCoder vision requires an extensible ecosystem and easy third-party
Skill addition.

-------------------------------------------------------------------------------

## Alternative D — Community Registry Only

Decision:

REJECTED FOR V1.

Reason:

Users must be able to create and install local Skills without depending on a
central registry.

-------------------------------------------------------------------------------

## Alternative E — Install Every Skill Automatically

Decision:

REJECTED.

Reason:

This wastes context, creates unnecessary configuration, and removes user
control.

-------------------------------------------------------------------------------

# 37. Consequences

## Positive Consequences

- Clear Tool/Skill separation.
- Strong extension model.
- Easy Skill installation.
- Local Skill support.
- GitHub Skill support.
- Curated Collections.
- User-controlled setup.
- Progressive context loading.
- Centralized permission enforcement.
- Provider independence.
- Reusable Tools.
- Reusable Skills.

## Negative Consequences

- Two extension systems must be maintained.
- Skill discovery requires metadata.
- Third-party extension validation introduces complexity.
- Version compatibility must eventually be managed.
- Automatic Skill activation requires careful relevance handling.

These costs are accepted because extensibility is a core ClaireCoder
requirement.

-------------------------------------------------------------------------------

# 38. V1 Boundary

The following SHALL be part of the V1 architecture:

Tools:

- Tool contract,
- Tool registry,
- core filesystem capability,
- search,
- terminal,
- Git,
- testing,
- diagnostics,
- permission integration.

Skills:

- Skill metadata,
- Skill registry,
- progressive loading,
- built-in Skills,
- local Skills,
- curated Collections,
- third-party Skill installation,
- Skill activation/deactivation,
- permission integration.

The following MAY remain optional extensions:

- centralized public Skill marketplace,
- automatic Skill updates,
- advanced Skill dependency resolution,
- automatic community ranking,
- remote Skill execution,
- complex extension sandboxing.

-------------------------------------------------------------------------------

# 39. Implementation Guidance

The implementation SHOULD initially favor:

- simple Tool interfaces,
- simple Skill metadata,
- filesystem-based Skill packages,
- Git-based installation,
- explicit registries,
- progressive loading,
- deterministic extension lifecycle.

The implementation SHALL avoid:

- requiring a centralized Skill marketplace,
- executing Skill code by default,
- embedding Skills directly into the core,
- making every Skill a Tool,
- loading every installed Skill into every request,
- creating a complex dependency resolver for V1.

-------------------------------------------------------------------------------

# 40. Decision Status

STATUS

ACCEPTED

This ADR establishes the Tool and Skill extension architecture for
ClaireCoder V1.

Later ADRs MAY refine:

- workflow interaction,
- context behavior,
- commands,
- permissions,
- MCP,
- extension security.

Any architectural change to the Tool/Skill boundary SHALL explicitly
supersede this ADR.

-------------------------------------------------------------------------------

# 41. Relationship With Other ADRs

CC-ADR-001

ClaireCoder Core Architecture

Defines the overall component boundaries.

CC-ADR-002

Model Gateway & Provider Architecture

Defines model execution and provider independence.

CC-ADR-003

Tool & Skill Extension Architecture

Defines executable Tools and reusable Skills.

CC-ADR-004

Workflow, Context & Engineering Session Architecture

Defines how Tools and Skills participate in engineering workflows and
context.

CC-ADR-005

Interaction, Modes & Command Architecture

Defines user-facing Skill and Tool controls.

CC-ADR-006

Permission, Autonomy & Security Architecture

Defines the security boundaries governing Tool and extension execution.

-------------------------------------------------------------------------------

# 42. AI Instructions

When implementing or documenting ClaireCoder after this ADR:

1. Keep Tools and Skills separate.
2. Treat Tools as executable capabilities.
3. Treat Skills as reusable expertise and methodology.
4. Keep all Tool execution behind the Permission Engine.
5. Support built-in Skills.
6. Support local Skills.
7. Support curated Skill Collections.
8. Support third-party Skills.
9. Support GitHub as a third-party Skill source.
10. Keep Skill metadata separate from Skill instructions.
11. Use progressive Skill loading.
12. Do not load every installed Skill into model context.
13. Keep Skills model-independent.
14. Keep Skills separate from Modes.
15. Keep Skills separate from Workflows.
16. Keep third-party extensions isolated from internal implementation details.
17. Do not automatically trust third-party extensions.
18. Preserve user control during Skill setup.
19. Preserve individual Skill management after Collection installation.
20. Do not introduce a mandatory centralized marketplace for V1.
21. Keep extension installation simple.
22. Do not allow Skills or Commands to bypass permissions.
23. Preserve the Tool registry and Skill registry concepts.
24. Preserve ClaireCoder's simplicity.
25. Treat this ADR as the authoritative Tool and Skill architecture unless
    explicitly superseded.

###############################################################################

END OF CC-ADR-003

###############################################################################