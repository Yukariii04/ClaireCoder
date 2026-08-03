###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Research Document
#
# Document Number : CC-RES-001
# Title           : Competitive Deep Dive
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document provides a detailed competitive study of modern software
engineering agents relevant to ClaireCoder.

The research examines Claude Code, Codex, OpenCode, Hermes Agent, OpenHands,
Aider, Cline, Roo Code, Gemini CLI, and other relevant coding agents.

The objective is not to reproduce existing products.

The objective is to identify capabilities, architectural patterns, engineering
practices, interaction models, extension mechanisms, and areas of
differentiation that ClaireCoder may adopt, improve, combine, or intentionally
reject.

This document SHALL serve as the detailed competitive research foundation for
subsequent ClaireCoder Tool, Skill, Workflow, Model, Context, Autonomy, and
CLI/TUI research.

-------------------------------------------------------------------------------

# 2. Background

Modern coding agents have evolved from code-completion systems into
software-engineering agents capable of understanding repositories, planning
tasks, modifying files, executing commands, running tests, using external
tools, and performing multi-step engineering work.

Different systems approach these capabilities through different architectural
and operational models.

Claude Code provides a strong reference for terminal-based agentic software
engineering.

Codex provides a strong reference for repository-oriented autonomous task
execution.

OpenCode provides a strong reference for provider independence, configurable
agents, permissions, Tools, Skills, commands, and extensibility.

Hermes Agent provides a broader reference for multiple model providers, Tools,
Skills, memory, delegation, MCP, plugins, and sessions.

Aider provides an important reference for repository intelligence and compact
repository mapping.

OpenHands, Cline, Roo Code, and Gemini CLI provide additional approaches to
autonomous execution, interactive approval, specialized modes, extensions,
and CLI-based engineering.

ClaireCoder SHALL use these systems as research references rather than
attempting to reproduce any single system.

-------------------------------------------------------------------------------

# 3. Purpose

This research SHALL establish:

- the current competitive capability baseline,
- common capabilities across major coding agents,
- meaningful differences between existing systems,
- useful architectural patterns,
- useful engineering workflows,
- extension mechanisms,
- user interaction patterns,
- potential weaknesses and limitations,
- opportunities for ClaireCoder differentiation.

The findings SHALL be used as inputs for subsequent ClaireCoder research,
architecture decisions, and product requirements.

-------------------------------------------------------------------------------

# 4. Scope

## In Scope

- Agent architecture.
- Engineering workflows.
- Planning.
- Execution.
- Repository understanding.
- Repository intelligence.
- File editing.
- Search.
- Terminal execution.
- Git.
- Testing.
- Diagnostics.
- Modes.
- Commands.
- Tools.
- Skills.
- Skill Collections.
- Extensions.
- MCP.
- Subagents.
- Model providers.
- Local models.
- Model routing.
- Context management.
- Memory.
- Engineering Sessions.
- Permissions.
- Autonomy.
- CLI/TUI.
- Configuration.
- Setup experience.
- User experience.
- Competitive differentiation.

## Out of Scope

- Reproducing proprietary implementations.
- Copying proprietary source code.
- Final ClaireCoder architecture.
- Final Tool implementation.
- Final Skill implementation.
- Final Model Gateway implementation.
- Final Workflow implementation.
- Final CLI/TUI implementation.
- Production implementation.
- Performance benchmarking as a primary objective.

-------------------------------------------------------------------------------

# 5. Research Questions

### RQ-001

What capabilities are currently provided by major software engineering agents?

---

### RQ-002

Which capabilities are common across Claude Code, Codex, OpenCode, Hermes
Agent, OpenHands, Aider, Cline, Roo Code, Gemini CLI, and other relevant
systems?

---

### RQ-003

Which capabilities provide genuine engineering value rather than simply
increasing feature count?

---

### RQ-004

How do existing agents approach planning, execution, validation, and
recovery?

---

### RQ-005

How do existing agents implement Modes and specialized agent behavior?

---

### RQ-006

How do existing agents implement Tools, Skills, MCP, plugins, and other
extension mechanisms?

---

### RQ-007

How do existing agents support multiple model providers, model routing, and
local models?

---

### RQ-008

How do existing agents understand repositories and large codebases?

---

### RQ-009

How do existing agents manage context, memory, sessions, and resumable work?

---

### RQ-010

How do existing agents handle permissions and different levels of autonomy?

---

### RQ-011

Which commands and CLI/TUI capabilities are essential for a professional
coding-agent workflow?

---

### RQ-012

Which competitive features should ClaireCoder adopt?

---

### RQ-013

Which competitive features should ClaireCoder deliberately reject?

---

### RQ-014

What capabilities can meaningfully differentiate ClaireCoder from existing
coding agents?

-------------------------------------------------------------------------------

# 6. Research

## 6.1 Claude Code

Claude Code SHALL be studied as a primary reference for terminal-based
software engineering.

Research areas:

- terminal interaction,
- repository operations,
- planning,
- execution,
- permissions,
- Skills,
- MCP,
- sessions,
- subagents,
- commands,
- non-interactive execution,
- model selection,
- developer interaction.

The research SHALL determine which aspects of its engineering workflow are
general architectural patterns and which are specific to its model ecosystem.

-------------------------------------------------------------------------------

## 6.2 Codex

Codex SHALL be studied as a primary reference for autonomous repository
engineering.

Research areas:

- task planning,
- repository modification,
- command execution,
- testing,
- sandboxing,
- approval behavior,
- autonomous execution,
- CLI interaction,
- task completion,
- execution recovery.

The research SHALL determine which execution patterns improve engineering
reliability and which introduce unnecessary complexity.

-------------------------------------------------------------------------------

## 6.3 OpenCode

OpenCode SHALL be studied extensively because its architecture overlaps with
several ClaireCoder objectives.

Research areas:

- provider independence,
- model selection,
- configurable agents,
- primary agents,
- subagents,
- Plan and Build behavior,
- permissions,
- Tools,
- Skills,
- commands,
- MCP,
- CLI/TUI,
- configuration.

The research SHALL specifically examine how OpenCode separates operational
behavior from the underlying model.

-------------------------------------------------------------------------------

## 6.4 Hermes Agent

Hermes Agent SHALL be studied as a reference for extensible autonomous agents.

Research areas:

- multiple model providers,
- local model support,
- Tools and toolsets,
- Skills,
- memory,
- delegation,
- MCP,
- plugins,
- sessions,
- TUI,
- web capabilities,
- community extensions.

Particular attention SHALL be given to the distinction between Skills and
Tools and how external capabilities are incorporated without modifying the
core agent.

-------------------------------------------------------------------------------

## 6.5 Aider

Aider SHALL be studied primarily for repository intelligence.

Research areas:

- repository maps,
- symbol discovery,
- file ranking,
- context selection,
- repository-scale reasoning,
- code editing,
- Git integration,
- model interaction.

The research SHALL determine which repository-intelligence concepts can
improve ClaireCoder's Context Engine.

-------------------------------------------------------------------------------

## 6.6 OpenHands

OpenHands SHALL be studied as a reference for broader autonomous
software-development systems.

Research areas:

- agent execution,
- runtime isolation,
- Tool interaction,
- repository modification,
- task completion,
- extensibility,
- autonomous workflows,
- environment management.

-------------------------------------------------------------------------------

## 6.7 Cline

Cline SHALL be studied for interactive autonomous coding.

Research areas:

- file editing,
- terminal execution,
- browser interaction,
- approval flows,
- MCP,
- autonomous execution,
- user visibility.

The research SHALL examine how developer approval can coexist with efficient
autonomous execution.

-------------------------------------------------------------------------------

## 6.8 Roo Code

Roo Code SHALL be studied primarily for specialized operational Modes.

Research areas:

- Modes,
- custom agent behavior,
- Tool permissions,
- MCP,
- custom instructions,
- workflow-oriented development,
- mode-specific configuration.

The research SHALL determine whether specialized Modes provide genuine
engineering value or merely create prompt-level variations.

-------------------------------------------------------------------------------

## 6.9 Gemini CLI

Gemini CLI SHALL be studied as a provider-native coding-agent reference.

Research areas:

- CLI interaction,
- repository context,
- Tool execution,
- extensions,
- model integration,
- permissions,
- engineering workflows,
- configuration.

The research SHALL distinguish provider-specific capabilities from
general-purpose coding-agent architecture.

-------------------------------------------------------------------------------

# 7. Comparative Capability Analysis

The initial competitive baseline is:

Capability                  Competitive Presence       ClaireCoder Direction
──────────────────────────────────────────────────────────────────────────────
Terminal Agent              Common                     REQUIRED
File Editing                Common                     REQUIRED
Repository Search           Common                     REQUIRED
Repository Intelligence     Increasingly common       REQUIRED
Planning                    Common                     REQUIRED
Execution                   Common                     REQUIRED
Testing                     Common                     REQUIRED
Modes                       Increasingly common       REQUIRED
Skills                      Increasingly common       REQUIRED
Skill Collections           Less standardized         DIFFERENTIATOR
Third-party Skills          Supported by several     REQUIRED
MCP                         Common                    REQUIRED
Subagents                   Common                    REQUIRED
Multiple Providers          Increasingly common       REQUIRED
Local Models                Supported by several     REQUIRED
Model Routing               Supported by several     REQUIRED
Persistent Memory           Varies                    RESEARCH
Engineering Sessions        Varies                    REQUIRED
Fine-grained Permissions    Increasingly common       REQUIRED
CLI/TUI                     Common                    REQUIRED

This table SHALL be treated as a research baseline.

It SHALL NOT be interpreted as a final ClaireCoder product requirement list.

-------------------------------------------------------------------------------

# 8. Findings

## Finding 001 — Model Independence

Modern coding agents increasingly support multiple model providers, model
routers, custom endpoints, and local inference.

ClaireCoder SHALL therefore treat model independence as a foundational
architectural requirement.

-------------------------------------------------------------------------------

## Finding 002 — Skills Are an Important Extension Layer

Skills provide a mechanism for adding specialized knowledge, behavior,
methodology, or engineering standards without modifying the core agent.

This strongly supports ClaireCoder's planned:

- built-in Skills,
- local Skills,
- GitHub Skills,
- third-party Skills,
- Skill Collections.

-------------------------------------------------------------------------------

## Finding 003 — Skills and Tools Should Remain Separate

A Tool represents an executable capability.

A Skill represents reusable knowledge, instructions, methodology, or behavior
that can make use of existing capabilities.

ClaireCoder SHALL preserve this conceptual distinction.

-------------------------------------------------------------------------------

## Finding 004 — Skill Collections Are a Potential Differentiator

Existing systems demonstrate individual Skill installation and community
extension mechanisms.

ClaireCoder can extend this concept through curated Skill Collections.

A Collection can allow users to select a group of compatible Skills during
setup instead of installing them individually.

This SHALL remain subject to detailed Skill architecture research.

-------------------------------------------------------------------------------

## Finding 005 — Permissions Require Granularity

Modern coding agents increasingly distinguish between safe, sensitive, and
destructive operations.

ClaireCoder SHALL investigate permissions at appropriate Tool, Skill,
filesystem, command, workflow, and network levels.

-------------------------------------------------------------------------------

## Finding 006 — Modes Have Real Engineering Value

Different operational Modes can alter how an agent plans, executes, reviews,
explores, researches, or modifies a repository.

ClaireCoder SHALL investigate Modes as behavioral configurations rather than
simple personality presets.

-------------------------------------------------------------------------------

## Finding 007 — Repository Intelligence Is Fundamental

Efficient coding agents require more than arbitrary file retrieval.

Repository maps, symbol information, search, dependency awareness, and
structured context SHALL be investigated as first-class capabilities.

-------------------------------------------------------------------------------

## Finding 008 — More Tools Do Not Automatically Produce a Better Agent

A larger Tool ecosystem can increase capability but can also increase:

- complexity,
- context consumption,
- maintenance,
- failure modes,
- permission complexity.

ClaireCoder SHALL prioritize reliable and composable Tools rather than
competing purely on Tool count.

-------------------------------------------------------------------------------

## Finding 009 — Local Models Matter

A provider-independent architecture is only useful if users who cannot afford
multiple premium model subscriptions can still operate ClaireCoder
effectively.

ClaireCoder SHALL therefore investigate local models and compatible local
inference servers as first-class model sources.

-------------------------------------------------------------------------------

## Finding 010 — Model Profiles Should Not Become Provider Lock-In

Different tasks may benefit from different models.

However, users SHALL NOT be required to own multiple expensive model
subscriptions simply to use ClaireCoder's capabilities.

Model configuration SHALL therefore remain flexible enough to operate with
one available model when necessary.

-------------------------------------------------------------------------------

# 9. Analysis

The competitive landscape suggests that the strongest coding agents are not
defined by a single feature.

Their effectiveness comes from the interaction between:

Model
  │
  ▼
Planning
  │
  ▼
Context
  │
  ▼
Tools
  │
  ▼
Execution
  │
  ▼
Validation
  │
  └──────────────► Recovery / Replanning

ClaireCoder SHALL therefore avoid designing isolated feature systems.

The Engineering Engine SHALL eventually coordinate these capabilities while
keeping the individual components replaceable.

The research also indicates that ClaireCoder's differentiation should not be
based on simply having more commands, Tools, or Modes than competitors.

Instead, differentiation should come from the ease with which users can
construct and customize their own engineering environment.

-------------------------------------------------------------------------------

# 10. Recommendations

Based on the current research, ClaireCoder SHOULD:

1. Maintain strict model and provider independence.
2. Support local and hosted models through the same Model Gateway concept.
3. Treat Skills as a first-class extension mechanism.
4. Support individual Skills and curated Skill Collections.
5. Support local and third-party Skills.
6. Keep Tools separate from Skills.
7. Keep Workflows separate from Tools and Skills.
8. Provide configurable operational Modes.
9. Provide granular permissions.
10. Treat repository intelligence as a core capability.
11. Support resumable Engineering Sessions.
12. Avoid competing through raw Tool or feature count.
13. Preserve a focused CLI/TUI experience.
14. Allow users with access to only one model provider to use ClaireCoder
    effectively.
15. Keep all extension mechanisms optional and replaceable.

These recommendations SHALL guide subsequent research but SHALL NOT become
final architecture decisions until the appropriate ADRs are completed.

-------------------------------------------------------------------------------

# 11. Expected Outcomes

Successful completion of this research SHALL establish:

- a verified competitive capability baseline,
- a detailed understanding of major coding-agent approaches,
- capabilities ClaireCoder should investigate,
- capabilities ClaireCoder should potentially adopt,
- capabilities ClaireCoder should potentially reject,
- ClaireCoder differentiation opportunities,
- research requirements for the Tool architecture,
- research requirements for the Skill architecture,
- research requirements for the Model Gateway,
- research requirements for Planning and Execution,
- research requirements for Context and Sessions,
- research requirements for Autonomy and Permissions.

-------------------------------------------------------------------------------

# 12. Risks

Potential risks include:

- copying existing agents instead of developing ClaireCoder's own identity,
- competing through feature count,
- premature architectural decisions,
- relying on outdated competitive information,
- confusing marketing claims with actual capabilities,
- excessive scope,
- unnecessary Tool proliferation,
- unnecessary Mode proliferation,
- excessive dependency on premium model providers.

Competitive research SHALL inform ClaireCoder rather than dictate its
architecture.

-------------------------------------------------------------------------------

# 13. Success Criteria

This research succeeds when:

- major coding-agent capabilities have been studied,
- important architectural patterns have been identified,
- competitive strengths and weaknesses have been documented,
- ClaireCoder differentiation is clear,
- unnecessary feature imitation has been identified,
- remaining research areas are clearly defined,
- no implementation decision has been prematurely locked.

-------------------------------------------------------------------------------

# 14. Future Work

The next research document SHALL be:

CC-RES-002 — Tool Architecture Research

It SHALL investigate:

- filesystem Tools,
- search Tools,
- code editing and patching,
- terminal execution,
- Git,
- LSP,
- diagnostics,
- repository mapping,
- browser and web Tools,
- MCP,
- subagents,
- computer-use capabilities,
- image and screenshot understanding,
- Tool extensibility,
- Tool permissions.

Subsequent research SHALL use the findings from this document as input rather
than repeating the same competitive analysis.

-------------------------------------------------------------------------------

# 15. AI Instructions

When continuing ClaireCoder research:

1. Treat competitive products as research references.
2. Verify current capabilities before claiming support.
3. Do not copy proprietary implementations.
4. Preserve ClaireCoder model independence.
5. Preserve separation between Tools, Skills, Workflows, and Models.
6. Prefer engineering value over feature-count parity.
7. Preserve local-model accessibility.
8. Preserve third-party extensibility.
9. Treat research findings as inputs rather than final requirements.
10. Do not lock implementation decisions before the appropriate research or
    ADR.
11. Do not assume users have access to multiple paid model providers.
12. Preserve ClaireCoder's independence from the wider Claire Ecosystem.

###############################################################################

END OF CC-RES-001

###############################################################################