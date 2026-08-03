###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Research Document
#
# Document Number : CC-RES-007
# Title           : Modes, Commands & User Interaction Research
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document researches the Modes, Commands, CLI/TUI interaction model, and
user-facing control system required by ClaireCoder.

The objective is to determine how ClaireCoder SHALL provide a professional
coding-agent interface comparable to modern systems such as Claude Code,
Codex, OpenCode, and Hermes Agent while preserving its own architecture and
identity.

The research covers:

- operational Modes,
- slash commands,
- CLI commands,
- custom commands,
- interactive TUI behavior,
- model switching,
- session controls,
- Tool visibility,
- Skill controls,
- approvals,
- interruption,
- cancellation,
- progress,
- status information,
- autonomy controls,
- configuration,
- ClaireCoder's visual identity.

Current coding agents demonstrate that the command layer and interactive
interface are not merely presentation features.

They provide direct control over the agent's workflow.

OpenCode provides built-in commands, custom commands, command arguments,
shell-output injection, file references, command-specific agents, models,
and subtask behavior. Its CLI can launch the TUI, continue or fork sessions,
select models and agents, and configure autonomous approval behavior.
([OpenCode Commands], [OpenCode TUI], [OpenCode CLI])

Hermes Agent provides both a classic CLI and a TUI backed by the same runtime,
with shared sessions, slash commands, model selection, Skill controls,
session switching, subagent observability, approvals, usage information,
and runtime status. ([Hermes CLI Commands], [Hermes TUI])

ClaireCoder SHALL therefore treat its interaction layer as a first-class
system.

-------------------------------------------------------------------------------

# 2. Background

A coding agent is used continuously through an interaction loop.

The user must be able to:

- start an agent,
- select or change a model,
- select a Mode,
- inspect the current session,
- invoke commands,
- install or activate Skills,
- control autonomy,
- approve or reject actions,
- interrupt execution,
- inspect Tool activity,
- compact context,
- resume sessions,
- modify configuration.

Modern coding agents expose these capabilities through combinations of:

- CLI arguments,
- slash commands,
- keyboard shortcuts,
- TUI panels,
- interactive prompts,
- configuration files,
- session controls.

OpenCode's TUI uses slash commands such as `/help`, `/compact`, `/details`,
`/connect`, `/model`, and other commands, while `@` references files and `!`
can execute shell commands directly from the prompt interface.
([OpenCode TUI])

OpenCode also supports custom command files with descriptions, arguments,
agents, models, subtasks, shell-output insertion, and file references.
([OpenCode Commands])

Hermes provides a similar layered interaction model, with classic CLI and TUI
surfaces sharing the same sessions and slash commands. Its TUI includes
model selection, session switching, Skill and agent controls, usage
information, approval panels, and live status. ([Hermes TUI])

ClaireCoder SHALL research these interaction patterns while avoiding
unnecessary duplication between commands, Modes, Skills, and Tools.

-------------------------------------------------------------------------------

# 3. Purpose

This research SHALL determine:

- what a ClaireCoder Mode represents,
- how Modes differ from Skills,
- how Modes differ from Workflows,
- which Modes should exist in V1,
- what commands are required,
- which commands should be built in,
- how custom commands should work,
- how users should switch Modes,
- how model switching should work,
- how Skills should be controlled from the interface,
- how sessions should be controlled,
- how approvals should appear,
- how execution can be interrupted,
- how progress should be represented,
- how Tool activity should be displayed,
- how ClaireCoder's visual identity should appear in the CLI/TUI.

-------------------------------------------------------------------------------

# 4. Scope

## In Scope

- Modes.
- Mode switching.
- Mode-specific behavior.
- Commands.
- Slash commands.
- CLI commands.
- Custom commands.
- Command arguments.
- Command aliases.
- Command discovery.
- TUI.
- CLI.
- Keyboard interaction.
- Model selection.
- Skill selection.
- Skill management commands.
- Session commands.
- Tool visibility.
- Approval interfaces.
- Autonomy controls.
- Execution interruption.
- Cancellation.
- Progress.
- Status.
- Context controls.
- Configuration controls.
- ClaireCoder header.
- Claire visual identity.

## Out of Scope

- Final TUI implementation.
- Final CLI implementation.
- Final command parser.
- Final Mode implementation.
- Final permission implementation.
- Final Skill implementation.
- Final model configuration implementation.
- Final visual design system.
- Desktop GUI.

-------------------------------------------------------------------------------

# 5. Research Questions

### RQ-110

What should a ClaireCoder Mode represent?

---

### RQ-111

How should Modes differ from Skills?

---

### RQ-112

How should Modes differ from Workflows?

---

### RQ-113

Which Modes are required for ClaireCoder V1?

---

### RQ-114

Should users be able to create custom Modes?

---

### RQ-115

How should Mode-specific permissions work?

---

### RQ-116

How should Mode-specific models work?

---

### RQ-117

How should Mode-specific planning depth work?

---

### RQ-118

Which slash commands are essential?

---

### RQ-119

Which commands should be CLI-level commands instead of in-session slash
commands?

---

### RQ-120

How should custom commands be defined?

---

### RQ-121

How should command arguments work?

---

### RQ-122

How should commands invoke Skills, Tools, Workflows, or subagents?

---

### RQ-123

How should users discover available commands?

---

### RQ-124

How should users discover available Modes?

---

### RQ-125

How should model selection work inside a session?

---

### RQ-126

How should Skill activation and deactivation work?

---

### RQ-127

How should session switching and resumption work?

---

### RQ-128

How should users interrupt or cancel an active agent operation?

---

### RQ-129

How should approval requests be represented?

---

### RQ-130

How should Tool activity be displayed without overwhelming the user?

---

### RQ-131

How should progress be represented during long-running tasks?

---

### RQ-132

How should ClaireCoder expose context usage and compression?

---

### RQ-133

How should ClaireCoder expose cost and token information when the provider
supports it?

---

### RQ-134

How should the Claire image and header identity appear without reducing the
professional coding-agent experience?

-------------------------------------------------------------------------------

# 6. Research

## 6.1 Modes

A Mode SHALL represent a distinct operational behavior of the Engineering
Engine.

A Mode MAY influence:

- planning behavior,
- Tool permissions,
- execution autonomy,
- model selection,
- Skill activation,
- validation behavior,
- output style,
- workflow constraints.

A Mode SHOULD NOT merely change personality or wording.

A Mode should change how ClaireCoder performs engineering work.

-------------------------------------------------------------------------------

## 6.2 Mode Versus Skill

The distinction established by CC-RES-003 remains important.

A Skill provides reusable expertise, methodology, or instructions.

A Mode determines how the agent operates.

For example:

UI/UX expertise can be provided through a Skill.

Review behavior can be provided through a Mode.

An engineering-quality Skill can influence implementation methodology.

A Review Mode can restrict execution and prioritize inspection.

Therefore:

Skill
  = "How should the agent perform a specialized type of work?"

Mode
  = "How should the agent operate during this task?"

This boundary SHALL remain explicit.

-------------------------------------------------------------------------------

## 6.3 Mode Versus Workflow

A Workflow represents a sequence or process.

A Mode represents the operational constraints and behavior under which that
process runs.

For example:

Workflow:
  Implement feature → test → review → finalize.

Mode:
  Build Mode.

The same Workflow MAY potentially run under different Modes.

ClaireCoder SHALL avoid collapsing Modes and Workflows into one abstraction.

-------------------------------------------------------------------------------

## 6.4 Candidate V1 Modes

The research identifies the following candidate Modes:

BUILD

Primary software-development Mode.

Expected behavior:

- modify files,
- execute commands,
- run tests,
- implement tasks,
- validate results.

PLAN

Planning and repository-analysis Mode.

Expected behavior:

- inspect repository,
- analyze requirements,
- produce a plan,
- identify affected areas,
- avoid implementation unless explicitly authorized.

REVIEW

Code and engineering review Mode.

Expected behavior:

- inspect changes,
- identify defects,
- evaluate architecture,
- evaluate tests,
- avoid modifying files by default.

RESEARCH

Research-oriented Mode.

Expected behavior:

- gather information,
- inspect documentation,
- compare approaches,
- investigate repository or external information,
- minimize unnecessary modification.

DEBUG

Diagnostic Mode.

Expected behavior:

- reproduce problems,
- gather evidence,
- inspect logs,
- isolate causes,
- make targeted corrections,
- validate fixes.

These are candidate Modes.

The final V1 Mode roster SHALL be determined during later architecture and
ADR work.

-------------------------------------------------------------------------------

## 6.5 Custom Modes

ClaireCoder SHOULD eventually support custom Modes.

A custom Mode MAY define:

- description,
- system behavior,
- default model,
- planning profile,
- Tool permissions,
- Skill requirements,
- autonomy level,
- validation behavior.

However, custom Modes SHOULD NOT be required for basic usage.

The default ClaireCoder experience SHALL remain understandable without users
having to construct their own agent architecture.

-------------------------------------------------------------------------------

## 6.6 Mode Switching

Mode switching SHOULD be available interactively.

Potential interactions include:

- command-based switching,
- keyboard shortcuts,
- TUI selector,
- session startup selection.

A Mode switch SHOULD be visible to the user.

If switching Modes changes:

- model,
- permissions,
- autonomy,
- active Skills,
- execution behavior,

ClaireCoder SHOULD make the relevant changes clear.

-------------------------------------------------------------------------------

## 6.7 Mode Persistence

The active Mode MAY persist for the duration of an Engineering Session.

ClaireCoder SHOULD avoid silently changing Modes between unrelated tasks.

Session state SHOULD record the active Mode when it materially affects the
workflow.

-------------------------------------------------------------------------------

## 6.8 Commands

Commands SHALL provide direct control over ClaireCoder.

The command system SHOULD support:

- built-in commands,
- custom commands,
- arguments,
- aliases,
- command descriptions,
- Skill-backed commands,
- Workflow-backed commands,
- optional model selection,
- optional Mode selection.

OpenCode demonstrates a useful custom-command approach where Markdown command
files can define descriptions, agents, models, subtasks, arguments, shell
output, and file references. ([OpenCode Commands])

ClaireCoder SHOULD investigate a similarly simple command-extension mechanism.

-------------------------------------------------------------------------------

## 6.9 Built-in Commands

The exact command roster SHALL be determined later, but the following
categories are expected to require built-in commands:

Session:

- help,
- sessions,
- resume,
- new,
- clear,
- compact.

Agent:

- mode,
- model,
- skills,
- agents,
- status.

Execution:

- approve,
- deny,
- stop,
- retry,
- continue.

Repository:

- init,
- status,
- diff.

Configuration:

- config,
- providers,
- profile.

Utility:

- version,
- diagnostics,
- exit.

The final names SHALL be researched and standardized later.

-------------------------------------------------------------------------------

## 6.10 Custom Commands

Custom commands SHOULD be easy to create.

A command SHOULD be capable of specifying:

- name,
- description,
- prompt or workflow,
- arguments,
- optional Mode,
- optional model,
- optional Skill,
- optional subagent,
- optional Tool requirements.

Commands SHOULD be stored as portable configuration or Markdown files where
practical.

This keeps the command system accessible to users without requiring them to
modify ClaireCoder's source code.

-------------------------------------------------------------------------------

## 6.11 Command Arguments

ClaireCoder SHOULD support both:

- positional arguments,
- named arguments.

Simple commands SHOULD remain easy to invoke.

For example:

/test

or:

/component Button

More complex commands MAY support named values.

The command system SHOULD avoid turning every command into a complex
programming language.

-------------------------------------------------------------------------------

## 6.12 Command Discovery

Typing the command prefix SHOULD provide discoverability.

The interface SHOULD show:

- command name,
- description,
- optional arguments,
- current Mode compatibility.

The system SHOULD support fuzzy search.

This reduces the need for users to memorize every command.

-------------------------------------------------------------------------------

## 6.13 File and Repository References

OpenCode allows `@` file references in its TUI and automatically includes
referenced content in the conversation. ([OpenCode TUI])

ClaireCoder SHOULD investigate an equivalent reference mechanism.

Potential syntax:

@src/main.py
@src/components/
@README.md

The final syntax SHALL be determined during interface design.

-------------------------------------------------------------------------------

## 6.14 Shell Shortcuts

OpenCode allows messages beginning with `!` to execute shell commands and
place the output into the conversation. ([OpenCode TUI])

ClaireCoder SHOULD investigate a similar shortcut.

However, shell shortcuts SHALL respect the same permission model as normal
terminal execution.

A shortcut SHALL not bypass Tool security.

-------------------------------------------------------------------------------

## 6.15 Model Selection

Model selection SHALL be accessible during a session.

The user SHOULD be able to:

- view available models,
- switch models,
- inspect provider,
- inspect capability information,
- select a Model Profile.

The current session SHOULD make the active model visible.

Hermes provides a model picker in its TUI and supports provider/model
selection through both CLI options and interactive controls.
([Hermes CLI Commands], [Hermes TUI])

ClaireCoder SHALL investigate a similar interaction model.

-------------------------------------------------------------------------------

## 6.16 Skill Selection

Users SHOULD be able to inspect installed Skills.

Potential operations include:

- list,
- enable,
- disable,
- inspect,
- install,
- remove,
- update.

Skill activation SHOULD remain separate from Mode switching.

A Skill MAY be automatically activated when relevant, but the user SHOULD
retain control over explicitly enabled or disabled Skills.

-------------------------------------------------------------------------------

## 6.17 Session Commands

The interaction layer SHALL provide direct session controls.

Potential operations include:

- create session,
- list sessions,
- switch session,
- resume session,
- rename session,
- fork session,
- archive session,
- delete session.

OpenCode supports continuing and forking sessions from the CLI, while Hermes
supports session continuation and session selection from both CLI and TUI.
([OpenCode CLI], [Hermes CLI Commands], [Hermes TUI])

ClaireCoder SHALL investigate both continuation and forking.

-------------------------------------------------------------------------------

## 6.18 Approval Interface

Approval is an important boundary between the agent and the user.

Approval requests SHOULD clearly show:

- what action is requested,
- which Tool is requesting it,
- affected files or command,
- relevant risk,
- available choices.

Potential choices include:

- allow once,
- allow for session,
- allow for Mode,
- deny,
- deny and continue,
- cancel workflow.

The interface SHOULD make dangerous actions visually distinguishable.

-------------------------------------------------------------------------------

## 6.19 Autonomy Controls

ClaireCoder SHOULD support different autonomy levels.

Potential conceptual levels are:

ASSISTED

The user approves sensitive actions.

BALANCED

The agent executes routine operations automatically and requests approval for
higher-risk operations.

AUTONOMOUS

The agent can perform most operations within configured boundaries.

YOLO

All applicable approval prompts are bypassed.

The final naming and behavior SHALL be determined during permission and
autonomy ADR work.

Hermes currently exposes a `--yolo` option that bypasses dangerous-command
approval prompts and visibly marks YOLO mode in its TUI. ([Hermes CLI
Commands], [Hermes TUI])

ClaireCoder SHALL preserve clear visibility whenever approval bypass is
enabled.

-------------------------------------------------------------------------------

## 6.20 Interruption

The user SHALL be able to interrupt active execution.

Interruption SHOULD:

- stop or cancel the current model operation,
- stop interruptible Tool execution,
- preserve useful session state,
- allow the user to continue,
- avoid corrupting partially completed operations where possible.

An interrupted task SHALL not automatically be considered failed.

-------------------------------------------------------------------------------

## 6.21 Progress

Long-running tasks require visible progress.

The interface SHOULD show:

- current Mode,
- current task,
- active Tool,
- elapsed time,
- session state,
- subagent activity,
- context compression where relevant.

Hermes exposes live status, elapsed time, context compression count,
background-task count, and subagent observability in its TUI.
([Hermes TUI])

ClaireCoder SHALL investigate similar visibility while keeping the display
compact.

-------------------------------------------------------------------------------

## 6.22 Tool Visibility

Tool activity SHOULD be visible without overwhelming the user.

The interface SHOULD distinguish:

- Tool started,
- Tool completed,
- Tool failed,
- Tool output available,
- approval required.

Detailed Tool output SHOULD be collapsible or retrievable.

The user should be able to inspect what ClaireCoder did without being forced
to read every low-level output line.

-------------------------------------------------------------------------------

## 6.23 Subagent Visibility

If ClaireCoder supports subagents, users SHOULD be able to determine:

- which subagents are active,
- their purpose,
- current state,
- progress,
- completion,
- failure.

Hermes provides a live subagent tree with controls and per-branch information
in its TUI. ([Hermes TUI])

ClaireCoder SHALL investigate a similar observability model.

-------------------------------------------------------------------------------

## 6.24 Context Controls

The interface SHOULD provide commands for:

- context usage,
- compaction,
- session summary,
- active Skills,
- active Mode,
- active model.

A context-compaction command SHOULD not destroy the Engineering Session.

It should trigger the Context Engine behavior established in CC-RES-006.

-------------------------------------------------------------------------------

## 6.25 Status Header

ClaireCoder SHALL have a persistent visual identity in the interactive
interface.

The requested direction is for the Claire image to occupy the primary
identity/header position in the same conceptual role that a product logo or
agent identity occupies in other coding-agent interfaces.

The header SHOULD communicate:

- Claire identity,
- active Mode,
- active model,
- provider,
- session status.

The header SHOULD remain compact.

The Claire image SHOULD not consume excessive terminal space.

The exact artwork, dimensions, rendering method, and fallback behavior SHALL
be decided during UI design.

-------------------------------------------------------------------------------

## 6.26 Non-TTY Operation

ClaireCoder SHALL not depend exclusively on an interactive TUI.

A non-interactive CLI mode is important for:

- scripts,
- CI,
- automation,
- pipelines,
- IDE integrations,
- external orchestrators.

OpenCode supports a programmatic `run` workflow in addition to its interactive
TUI. ([OpenCode CLI])

ClaireCoder SHOULD therefore expose equivalent non-interactive execution.

-------------------------------------------------------------------------------

## 6.27 CLI and TUI Relationship

The CLI and TUI SHOULD share the same underlying Agent and Session systems.

The conceptual architecture is:

CLI / TUI
    ↓
Interaction Layer
    ↓
Command System
    ↓
Engineering Engine
    ↓
Session / Context / Tools / Models

The TUI SHALL not become a second implementation of the agent.

This is consistent with Hermes, where the classic CLI and TUI share the same
agent runtime, sessions, slash commands, and configuration. ([Hermes TUI])

-------------------------------------------------------------------------------

# 7. Interaction Classification

The initial interaction classification SHALL be:

User Input:

- natural-language prompt,
- command,
- file reference,
- shell shortcut.

Control Layer:

- Mode,
- Model,
- Skill,
- Profile,
- Autonomy.

Execution Layer:

- Tool activity,
- approvals,
- subagents,
- progress,
- interruption.

Session Layer:

- sessions,
- resume,
- fork,
- compact,
- history.

Information Layer:

- status,
- context,
- usage,
- diagnostics,
- Tool details.

This classification is provisional.

-------------------------------------------------------------------------------

# 8. Analysis

The research indicates that ClaireCoder should not make commands, Modes,
Skills, and Tools interchangeable.

Their responsibilities should remain distinct.

Commands:

Direct user controls.

Modes:

Operational behavior.

Skills:

Reusable expertise and methodology.

Tools:

Executable capabilities.

Workflows:

Structured engineering processes.

The interaction layer should expose these systems without merging them.

A user should be able to control the system without needing to understand
its internal architecture.

-------------------------------------------------------------------------------

# 9. Recommendations

Based on the current research, ClaireCoder SHOULD:

1. Provide both an interactive TUI and a non-interactive CLI.
2. Make both surfaces use the same underlying Agent and Session systems.
3. Support operational Modes.
4. Keep Modes separate from Skills.
5. Keep Modes separate from Workflows.
6. Provide built-in slash commands.
7. Support custom commands.
8. Support command arguments.
9. Support command discovery and autocomplete.
10. Support file references.
11. Investigate shell shortcuts.
12. Ensure shell shortcuts respect Tool permissions.
13. Provide interactive model selection.
14. Provide Skill management.
15. Provide session management.
16. Support session continuation.
17. Investigate session forking.
18. Provide explicit approval interfaces.
19. Provide configurable autonomy levels.
20. Make approval bypass visibly obvious.
21. Provide interruption and cancellation.
22. Provide compact progress information.
23. Provide Tool activity visibility.
24. Provide subagent observability when subagents are enabled.
25. Provide context controls.
26. Display active Mode and model information.
27. Establish Claire as the visual identity of the interface.
28. Keep the Claire header compact and professional.
29. Preserve non-interactive execution for automation.
30. Avoid exposing unnecessary implementation complexity to normal users.

These recommendations SHALL guide subsequent architecture work but SHALL NOT
become final implementation requirements until the appropriate ADRs are
completed.

-------------------------------------------------------------------------------

# 10. Expected Outcomes

Successful completion of this research SHALL establish:

- the conceptual Mode system,
- the candidate V1 Mode roster,
- the Command System direction,
- custom command requirements,
- CLI/TUI relationship,
- model-selection interaction,
- Skill-management interaction,
- session-control interaction,
- approval interaction,
- autonomy interaction,
- interruption behavior,
- progress visibility,
- Tool observability,
- Claire header requirements.

-------------------------------------------------------------------------------

# 11. Risks

Potential risks include:

- command proliferation,
- Mode proliferation,
- confusing overlap between Modes and Skills,
- excessive UI complexity,
- excessive Tool output,
- unclear approval states,
- hidden autonomy changes,
- inconsistent CLI and TUI behavior,
- excessive visual branding,
- TUI dependency for automation,
- command configuration becoming overly complex.

ClaireCoder SHALL prioritize clarity and speed over feature-heavy interface
design.

-------------------------------------------------------------------------------

# 12. Success Criteria

This research succeeds when:

- Modes have a clear responsibility,
- Commands have a clear responsibility,
- Skills remain separate,
- Tools remain separate,
- Workflows remain separate,
- CLI and TUI responsibilities are clear,
- session controls are defined conceptually,
- approval behavior is defined conceptually,
- autonomy controls are defined conceptually,
- Tool visibility requirements are established,
- Claire's visual identity requirements are established,
- the interaction architecture can proceed to ADR without repeating this
  research.

-------------------------------------------------------------------------------

# 13. Future Work

The next research document SHALL be:

CC-RES-008 — Permissions, Autonomy & Security Research

It SHALL investigate:

- Tool permissions,
- filesystem permissions,
- terminal permissions,
- network permissions,
- Skill permissions,
- MCP permissions,
- approval scopes,
- trusted and untrusted sources,
- autonomous execution,
- YOLO-style operation,
- sandboxing,
- worktrees,
- destructive operations,
- credential boundaries,
- secret handling,
- command restrictions,
- third-party extension security,
- recovery after interrupted operations.

The research SHALL establish the security foundation required before
ClaireCoder architecture is finalized.

-------------------------------------------------------------------------------

# 14. AI Instructions

When continuing ClaireCoder Modes, Commands, and User Interaction research:

1. Keep Modes separate from Skills.
2. Keep Modes separate from Workflows.
3. Keep Commands separate from Tools.
4. Keep the CLI and TUI on the same underlying agent runtime.
5. Preserve non-interactive operation.
6. Prefer discoverable commands over memorization.
7. Keep command configuration simple.
8. Preserve user visibility of active Mode and model.
9. Make autonomy changes visible.
10. Make approval requests understandable.
11. Preserve interruption and cancellation.
12. Keep Tool output inspectable but compact.
13. Preserve subagent observability.
14. Keep Claire branding professional and compact.
15. Do not make the TUI a separate agent implementation.
16. Do not finalize command names or UI layouts before the appropriate ADR.
17. Preserve ClaireCoder's architectural simplicity.

###############################################################################

END OF CC-RES-007

###############################################################################