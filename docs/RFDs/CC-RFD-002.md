###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                  Research Foundation Document
#
# Document Number : CC-RFD-002
# Title           : Competitive Capability Analysis
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document establishes the competitive capability baseline for ClaireCoder.

The research examines existing software engineering agents and identifies
capabilities, architectural patterns, and design approaches relevant to
ClaireCoder.

The purpose is not to reproduce existing products.

The purpose is to determine which capabilities ClaireCoder SHALL adopt,
improve, combine, or intentionally avoid.

-------------------------------------------------------------------------------

# 2. Background

Modern coding agents increasingly combine language models with repository
context, filesystem operations, terminal execution, version control,
planning, permissions, extensibility, and persistent sessions.

Claude Code establishes a strong baseline for terminal-based agentic software
development through interactive sessions, model selection, permission
controls, MCP support, tool restrictions, and resumable sessions.

OpenCode extends this model through configurable primary agents and
subagents, explicit permissions, custom commands, model configuration, and
on-demand skills.

Hermes Agent demonstrates a broader extensibility model combining multiple
providers, toolsets, skills, memory, plugins, MCP, and community extensions.

Aider demonstrates the value of compact repository intelligence through its
repository map.

These systems establish the current competitive baseline against which
ClaireCoder SHALL be researched.

-------------------------------------------------------------------------------

# 3. Purpose

The competitive analysis SHALL:

- identify common capabilities across leading coding agents,
- identify capabilities that provide meaningful engineering value,
- identify capabilities that can be improved,
- identify capabilities that should remain optional,
- identify architectural approaches ClaireCoder should avoid,
- establish research direction for subsequent ClaireCoder documents.

-------------------------------------------------------------------------------

# 4. Competitive Landscape

The initial research set SHALL include:

- Claude Code.
- Codex CLI.
- OpenCode.
- Hermes Agent.
- OpenHands.
- Aider.
- Cline.
- Roo Code.
- Gemini CLI.
- Continue.

The research SHALL distinguish between:

- mature production capabilities,
- experimental capabilities,
- extensibility mechanisms,
- provider-specific behavior,
- architectural concepts.

-------------------------------------------------------------------------------

# 5. Capability Areas

The competitive analysis SHALL examine the following areas:

## 5.1 Model Support

Research SHALL examine:

- hosted model providers,
- local models,
- custom endpoints,
- model switching,
- model-specific configuration,
- provider independence.

ClaireCoder SHALL remain model and provider independent.

-------------------------------------------------------------------------------

## 5.2 Repository Intelligence

Research SHALL examine:

- repository mapping,
- file discovery,
- symbol discovery,
- code search,
- dependency understanding,
- context selection,
- large repository handling.

Repository intelligence SHALL be treated as a core capability rather than
simply passing selected files to a language model.

-------------------------------------------------------------------------------

## 5.3 Planning

Research SHALL examine:

- explicit planning modes,
- implicit planning,
- task decomposition,
- multi-step execution,
- planning depth,
- planning versus execution separation.

ClaireCoder SHALL investigate planning as an independent engineering
capability.

-------------------------------------------------------------------------------

## 5.4 Execution

Research SHALL examine:

- filesystem operations,
- terminal execution,
- background processes,
- package management,
- test execution,
- build execution,
- error recovery,
- iterative execution.

Execution SHALL remain controlled by ClaireCoder's operational and permission
model.

-------------------------------------------------------------------------------

## 5.5 Tools

Research SHALL examine:

- filesystem tools,
- search tools,
- terminal tools,
- Git tools,
- diagnostics,
- browser tools,
- documentation retrieval,
- MCP tools,
- external tools.

Tools SHALL be treated as modular capabilities rather than being permanently
bound to a single model provider.

-------------------------------------------------------------------------------

## 5.6 Skills

Research SHALL examine:

- built-in skills,
- local skills,
- repository skills,
- community skills,
- Git-based installation,
- skill discovery,
- progressive loading,
- skill permissions,
- skill validation.

OpenCode and Hermes demonstrate that on-demand skill loading can provide
extensibility without placing every skill's complete instructions into every
model context.

ClaireCoder SHALL investigate a similar principle while retaining its own
skill specification.

-------------------------------------------------------------------------------

## 5.7 Skill Collections

Research SHALL examine whether multiple skills can be distributed as curated
collections.

ClaireCoder SHALL support the concept of collections in its product vision.

Collections SHALL allow users to select a group of related skills during
initial setup rather than installing each skill individually.

-------------------------------------------------------------------------------

## 5.8 Third-Party Extensions

Research SHALL examine:

- GitHub-based extensions,
- local extensions,
- external repositories,
- registries,
- community distribution,
- validation,
- trust levels.

Third-party extensions SHALL remain optional.

ClaireCoder SHALL NOT require users to use a centralized marketplace.

-------------------------------------------------------------------------------

## 5.9 Modes and Commands

Research SHALL examine:

- planning modes,
- build modes,
- review modes,
- analysis modes,
- custom commands,
- slash commands,
- command discoverability,
- command extensibility.

Claude Code provides a mature CLI command and permission surface, while
OpenCode provides configurable agents and custom commands.

ClaireCoder SHALL provide an equivalent command and mode system while
allowing its behavior to evolve independently.

-------------------------------------------------------------------------------

## 5.10 Permissions

Research SHALL examine:

- command approval,
- filesystem permissions,
- terminal permissions,
- Git permissions,
- network permissions,
- tool-specific permissions,
- trust levels.

OpenCode demonstrates fine-grained allow, ask, and deny permissions for
individual tool categories and even command patterns.

ClaireCoder SHALL investigate fine-grained permissions rather than relying
only on a global autonomous mode.

-------------------------------------------------------------------------------

## 5.11 Memory and Sessions

Research SHALL examine:

- conversation history,
- session persistence,
- session resumption,
- project memory,
- engineering decisions,
- persistent knowledge.

Hermes demonstrates persistent memory and resumable sessions as part of its
agent architecture, while Claude Code supports continuing and resuming
sessions.

ClaireCoder SHALL investigate persistent engineering sessions as a distinct
concept from conversation history.

-------------------------------------------------------------------------------

## 5.12 User Experience

Research SHALL examine:

- CLI/TUI design,
- status indicators,
- tool activity,
- progress representation,
- model visibility,
- active mode visibility,
- active skill visibility,
- repository state,
- session state.

ClaireCoder SHALL provide a recognizable Claire identity while preserving a
professional software engineering interface.

-------------------------------------------------------------------------------

# 6. Competitive Findings

The initial research establishes several important observations.

### Finding 1

Model independence is already demonstrated by systems such as Hermes and
OpenCode.

ClaireCoder SHALL therefore treat provider independence as a fundamental
architectural requirement rather than an optional feature.

---

### Finding 2

Skills are becoming an important extension mechanism.

OpenCode uses on-demand `SKILL.md` loading, while Hermes supports community
skills and skill discovery.

ClaireCoder SHALL investigate a similarly lightweight installation and
retrieval model.

---

### Finding 3

Repository intelligence significantly affects coding-agent usefulness.

Aider's repository map demonstrates that a compact representation of files,
symbols, classes, functions, and signatures can provide broad repository
context without transmitting the entire repository.

ClaireCoder SHALL investigate repository mapping as part of its context
architecture.

---

### Finding 4

Permission systems are becoming more granular.

OpenCode provides tool-level and command-pattern permissions rather than only
a single global approval switch.

ClaireCoder SHALL investigate this approach.

---

### Finding 5

Different operating modes are useful for separating analysis from execution.

OpenCode explicitly separates Plan and Build agents and restricts Plan from
making normal edits or executing unrestricted commands.

ClaireCoder SHALL investigate explicit operational modes.

-------------------------------------------------------------------------------

# 7. Design Direction

The competitive research suggests that ClaireCoder SHALL focus on combining
the strongest ideas from existing systems while maintaining a distinct
architecture.

The initial design direction is:

- provider-independent model gateway,
- repository-aware context engine,
- explicit planning,
- structured execution,
- modular tools,
- installable skills,
- curated skill collections,
- third-party skill support,
- configurable modes,
- extensible commands,
- fine-grained permissions,
- persistent engineering sessions,
- professional CLI/TUI experience.

ClaireCoder SHALL NOT become a direct clone of any existing coding agent.

-------------------------------------------------------------------------------

# 8. Research Questions

### RQ-005

Which repository-intelligence techniques provide the best balance between
context quality, latency, and resource consumption?

---

### RQ-006

What common tool interface can support built-in tools, MCP tools, and future
community tools?

---

### RQ-007

What skill specification provides the simplest installation experience while
remaining safe and extensible?

---

### RQ-008

How should skill collections be represented, versioned, and resolved?

---

### RQ-009

How should planning strategies differ from model selection?

---

### RQ-010

What permission model provides high autonomy without sacrificing developer
control?

-------------------------------------------------------------------------------

# 9. Expected Outcomes

Successful completion establishes:

- a competitive capability baseline,
- a list of capabilities ClaireCoder SHALL investigate,
- a list of architectural patterns worth adopting,
- a list of patterns requiring modification,
- a clear separation between inspiration and imitation.

-------------------------------------------------------------------------------

# 10. Risks

Potential risks include:

- copying existing products too closely,
- excessive feature accumulation,
- adopting provider-specific architecture,
- over-reliance on current industry patterns,
- insufficient differentiation,
- excessive complexity.

ClaireCoder SHALL prioritize engineering value over feature-count parity.

-------------------------------------------------------------------------------

# 11. Success Criteria

This document succeeds when:

- major coding-agent capabilities have been identified,
- competitive patterns have been categorized,
- ClaireCoder's design direction is clearer,
- subsequent research questions are established,
- unnecessary feature imitation is avoided.

-------------------------------------------------------------------------------

# 12. Future Work

Future documents SHALL determine:

- repository intelligence architecture,
- tool architecture,
- skill specification,
- skill collections,
- workflow architecture,
- planning architecture,
- model gateway architecture,
- permission architecture.

-------------------------------------------------------------------------------

# 13. AI Instructions

When researching or designing ClaireCoder:

1. Treat existing coding agents as references, not architectural authorities.
2. Do not reproduce provider-specific architecture without justification.
3. Preserve ClaireCoder model independence.
4. Preserve modularity between models, skills, workflows, and tools.
5. Prefer capabilities that provide measurable engineering value.
6. Do not add features solely for competitive feature parity.
7. Preserve developer control over autonomous execution.
8. Treat third-party extensions as untrusted until validated.
9. Preserve compatibility with local and hosted model execution.
10. Maintain ClaireCoder's independent identity.

###############################################################################

END OF CC-RFD-002

###############################################################################