###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Research Document
#
# Document Number : CC-RES-002
# Title           : Tool Architecture Research
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document researches the Tool Ecosystem required by ClaireCoder.

The objective is to determine which capabilities SHALL form the ClaireCoder
core Toolset, which capabilities SHOULD remain optional, and which capabilities
SHALL be provided through external systems such as MCP, Skills, or future
extensions.

The research examines Tools used by major coding agents and evaluates them
according to engineering usefulness, reliability, composability, security,
model compatibility, and implementation complexity.

This document SHALL establish the research foundation for the future
ClaireCoder Tool Architecture.

-------------------------------------------------------------------------------

# 2. Background

A coding agent cannot perform software engineering through language-model
reasoning alone.

It requires capabilities that allow it to:

- inspect repositories,
- locate relevant files,
- understand source structure,
- modify code,
- execute commands,
- run tests,
- inspect diagnostics,
- interact with version control,
- access external information,
- communicate with external services,
- delegate work,
- operate within controlled permissions.

Current coding agents expose many of these capabilities through built-in
Tools, external Tool providers, MCP, repository intelligence systems, and
other extension mechanisms.

The competitive research indicates that the Tool layer has become a
fundamental part of agent architecture.

ClaireCoder SHALL therefore treat Tools as a first-class architectural
capability while avoiding unnecessary Tool proliferation.

-------------------------------------------------------------------------------

# 3. Purpose

This research SHALL determine:

- the minimum ClaireCoder V1 Toolset,
- the responsibilities of each core Tool,
- the separation between Tools and other agent components,
- which capabilities should be built into ClaireCoder,
- which capabilities should remain optional,
- which capabilities are appropriate for MCP,
- which capabilities are better implemented as Skills,
- how repository intelligence should interact with Tools,
- how Tool permissions should operate,
- how Tools can remain model independent.

-------------------------------------------------------------------------------

# 4. Scope

## In Scope

- Filesystem Tools.
- File discovery.
- Code search.
- Repository search.
- Code editing.
- Patch application.
- Terminal execution.
- Process management.
- Git operations.
- Testing.
- Diagnostics.
- LSP.
- Repository intelligence.
- Repository mapping.
- Web search.
- Web fetching.
- Browser interaction.
- MCP.
- External Tools.
- Subagent and delegation capabilities.
- Image and screenshot understanding.
- Tool discovery.
- Tool permissions.
- Tool results.
- Tool composition.
- Tool extensibility.

## Out of Scope

- Final Tool implementation.
- Final Tool API.
- Final permission implementation.
- Final MCP implementation.
- Skill implementation.
- Workflow implementation.
- Model Gateway implementation.
- Final repository-indexing implementation.
- Complete V1 Tool specification.

-------------------------------------------------------------------------------

# 5. Research Questions

### RQ-015

Which Tools are essential for the minimum viable ClaireCoder engineering
environment?

---

### RQ-016

Which Tool capabilities should be built directly into ClaireCoder?

---

### RQ-017

Which capabilities should instead be provided through MCP, Skills, or
external extensions?

---

### RQ-018

What common abstraction can support built-in Tools, MCP Tools, and community
Tools?

---

### RQ-019

What editing mechanism provides the best balance between precision,
reliability, reversibility, and model compatibility?

---

### RQ-020

How should repository search and repository intelligence interact with the
Context Engine?

---

### RQ-021

How should terminal execution support foreground and background processes,
interactive commands, and long-running development processes?

---

### RQ-022

How should Git operations be represented as Tools while protecting
destructive operations?

---

### RQ-023

How should LSP capabilities such as definitions, references, symbols, and
call relationships be exposed to the Engineering Engine?

---

### RQ-024

How should web search and web retrieval operate without making external
internet access mandatory?

---

### RQ-025

How should browser and computer-use capabilities be separated from normal web
retrieval?

---

### RQ-026

How should Tool results be represented so that the Engineering Engine can
reason over them without excessive context consumption?

---

### RQ-027

How should Tool failures be represented so that ClaireCoder can recover or
replan?

---

### RQ-028

How should Tools declare their capabilities, requirements, permissions, and
dependencies?

---

### RQ-029

How should third-party Tools be validated before being made available to the
agent?

-------------------------------------------------------------------------------

# 6. Research

## 6.1 Filesystem

Filesystem access is a foundational capability for software engineering.

The research SHALL investigate:

- file reading,
- file creation,
- file modification,
- file deletion,
- file renaming,
- directory listing,
- metadata inspection,
- binary-file handling,
- workspace boundaries.

Filesystem operations SHALL remain distinct from terminal execution.

-------------------------------------------------------------------------------

## 6.2 File Discovery

File discovery SHALL be investigated as a dedicated capability.

The Tool SHOULD support:

- glob patterns,
- directory traversal,
- ignored-file handling,
- workspace restrictions,
- efficient discovery across large repositories.

File discovery SHALL avoid unnecessarily loading file contents.

-------------------------------------------------------------------------------

## 6.3 Code Search

Code search SHALL be treated as a core engineering capability.

The research SHALL investigate:

- literal search,
- regular-expression search,
- filename search,
- language-aware search,
- symbol search,
- structural search,
- repository-wide search.

Search results SHOULD provide enough location information for the Engineering
Engine to retrieve only the relevant context.

-------------------------------------------------------------------------------

## 6.4 Code Editing

Code editing SHALL be investigated as one of the most critical Tool
categories.

The research SHALL compare:

- direct replacement,
- patch-based editing,
- unified diffs,
- structured editing,
- AST-aware editing,
- multi-file editing.

The preferred mechanism SHALL prioritize:

- precision,
- reversibility,
- validation,
- understandable diffs,
- compatibility across models.

-------------------------------------------------------------------------------

## 6.5 Terminal

Terminal execution SHALL be treated as a core Tool.

The research SHALL investigate:

- shell execution,
- working-directory selection,
- environment variables,
- standard output,
- standard error,
- exit codes,
- interactive processes,
- background processes,
- process termination,
- long-running development servers,
- command restrictions.

Terminal execution SHALL remain subject to the ClaireCoder permission model.

-------------------------------------------------------------------------------

## 6.6 Git

Git SHALL be treated as a core engineering capability for repositories using
Git.

The research SHALL investigate:

- status,
- diff,
- log,
- branch information,
- branch creation,
- checkout,
- staging,
- commit,
- stash,
- restore,
- merge,
- rebase,
- remote operations.

Destructive operations SHALL receive separate permission treatment.

ClaireCoder SHALL not assume that every Git operation is equally safe.

-------------------------------------------------------------------------------

## 6.7 Testing and Diagnostics

Testing SHALL be integrated into the Tool ecosystem rather than treated as
merely terminal output.

The research SHALL investigate:

- test discovery,
- test execution,
- test result parsing,
- compiler output,
- lint results,
- static-analysis results,
- runtime errors,
- build failures,
- structured diagnostics.

Diagnostics SHOULD be usable as inputs for subsequent planning and recovery.

-------------------------------------------------------------------------------

## 6.8 LSP

Language Server Protocol capabilities SHALL be investigated as an optional
but potentially high-value repository-intelligence layer.

The research SHALL examine:

- go to definition,
- find references,
- hover information,
- document symbols,
- workspace symbols,
- implementations,
- call hierarchy,
- diagnostics.

LSP SHALL not replace normal search.

It SHOULD complement textual and structural repository analysis.

-------------------------------------------------------------------------------

## 6.9 Repository Intelligence

Repository intelligence SHALL be treated as a major ClaireCoder capability.

The research SHALL investigate:

- repository maps,
- symbol indexes,
- dependency graphs,
- import relationships,
- call relationships,
- AST information,
- language-server information,
- semantic indexes,
- relevance ranking.

The research SHALL specifically investigate approaches that allow ClaireCoder
to understand large repositories without loading the entire repository into
the active model context.

-------------------------------------------------------------------------------

## 6.10 Repository Mapping

Repository mapping SHALL be researched independently from ordinary search.

A repository map MAY provide:

- important files,
- important symbols,
- relationships,
- definitions,
- signatures,
- structural information.

The research SHALL determine whether ClaireCoder should maintain:

- a static repository map,
- a dynamically ranked repository map,
- a symbol graph,
- a hybrid representation.

-------------------------------------------------------------------------------

## 6.11 Web Search

Web search SHALL be investigated as an optional external-information Tool.

Potential uses include:

- current documentation,
- recent package information,
- issue investigation,
- security information,
- troubleshooting,
- technology research.

Web search SHALL remain separate from repository-local search.

-------------------------------------------------------------------------------

## 6.12 Web Retrieval

Web retrieval SHALL be investigated separately from search.

The Tool SHOULD be capable of retrieving relevant page content after a
search result or direct URL has been identified.

The research SHALL examine:

- page extraction,
- content filtering,
- source attribution,
- large-page handling,
- failure handling,
- authentication boundaries.

-------------------------------------------------------------------------------

## 6.13 Browser Interaction

Browser interaction SHALL be treated as a distinct capability from web
search and web retrieval.

Potential uses include:

- interacting with web applications,
- testing frontend applications,
- inspecting rendered pages,
- reproducing browser-specific issues,
- validating user interfaces.

The research SHALL determine whether browser automation belongs in the
ClaireCoder core or should remain an optional extension.

-------------------------------------------------------------------------------

## 6.14 MCP

MCP SHALL be investigated as a major external Tool integration mechanism.

The research SHALL determine:

- how MCP Tools are discovered,
- how MCP servers are configured,
- how permissions apply,
- how external Tool failures are handled,
- how Tool schemas are normalized,
- how MCP Tools interact with Skills and Workflows.

ClaireCoder SHALL avoid making MCP a mandatory dependency for core operation.

-------------------------------------------------------------------------------

## 6.15 Subagents and Delegation

Subagent capabilities SHALL be investigated as an orchestration capability
rather than a normal Tool.

Potential use cases include:

- repository exploration,
- parallel research,
- testing,
- code review,
- specialized implementation,
- independent verification.

The research SHALL determine whether subagents belong within the Workflow
System, Engineering Engine, or Tool layer.

-------------------------------------------------------------------------------

## 6.16 Image and Screenshot Understanding

Image and screenshot understanding SHALL be investigated for engineering
tasks involving:

- UI implementation,
- visual regression,
- screenshots,
- diagrams,
- error messages,
- design references.

This capability SHALL remain model-capability dependent.

ClaireCoder SHALL therefore expose it through capability detection rather than
assuming that every model supports vision.

-------------------------------------------------------------------------------

# 7. Comparative Tool Findings

## Finding 001 — Filesystem, Search, and Shell Form the Minimum Core

Across modern coding agents, repository access, file discovery, editing, and
command execution form the foundation of practical engineering work.

ClaireCoder SHALL treat these capabilities as core V1 requirements.

-------------------------------------------------------------------------------

## Finding 002 — Search Should Not Be One Tool

Search is better represented as a family of related capabilities:

- file discovery,
- text search,
- symbol search,
- structural search,
- repository intelligence.

ClaireCoder SHOULD keep these capabilities composable rather than forcing
every search operation through one mechanism.

-------------------------------------------------------------------------------

## Finding 003 — Editing Requires Strong Reliability

Editing is more sensitive than ordinary information retrieval.

An incorrect edit can directly damage a repository.

ClaireCoder SHALL therefore prioritize precise, reviewable, and reversible
editing mechanisms.

-------------------------------------------------------------------------------

## Finding 004 — Terminal Is Powerful but High Risk

Terminal execution provides enormous engineering capability but also provides
access to potentially destructive operations.

Terminal permissions SHALL therefore be more granular than simply allowing
or denying the entire terminal.

-------------------------------------------------------------------------------

## Finding 005 — Repository Intelligence Should Be a Distinct Context Capability

Repository intelligence cannot be reduced to filesystem search.

ClaireCoder SHALL investigate Repository Intelligence as a distinct capability
layer within the Context architecture, capable of combining multiple sources
of structural information.

-------------------------------------------------------------------------------

## Finding 006 — MCP Should Extend the Tool Ecosystem

MCP is valuable for extending capabilities beyond the built-in Toolset.

ClaireCoder SHALL treat MCP as an extension mechanism rather than allowing
the core architecture to depend on it.

-------------------------------------------------------------------------------

## Finding 007 — Web Capabilities Should Be Modular

Web search, web retrieval, and browser interaction serve different purposes.

ClaireCoder SHOULD keep them separately controllable.

-------------------------------------------------------------------------------

## Finding 008 — Tool Results Are Part of the Context Problem

A Tool can technically succeed while still producing excessive or poorly
structured output.

ClaireCoder SHALL therefore research Tool-result normalization and context
compression alongside Tool execution.

-------------------------------------------------------------------------------

# 8. Tool Classification

The initial research classification SHALL be:

Core Tools:

- Filesystem.
- File discovery.
- Code search.
- Code editing.
- Terminal.
- Git.
- Testing.
- Diagnostics.

Core Intelligence:

- Repository mapping.
- Symbol intelligence.
- Context retrieval.

Optional Engineering Tools:

- LSP.
- Browser.
- Web search.
- Web retrieval.
- Image understanding.

External Extension Layer:

- MCP Tools.
- Community Tools.
- Provider-specific Tools.
- Future Tool protocols.

This classification is provisional and SHALL be finalized after architecture
research.

-------------------------------------------------------------------------------

# 9. Analysis

The Tool Ecosystem should not become a flat list of unrelated functions.

ClaireCoder SHOULD organize capabilities according to responsibility.

A conceptual hierarchy is:

Engineering Engine
  │
  ├── Planning
  │
  ├── Workflow
  │
  ├── Context
  │     └── Repository Intelligence
  │
  └── Tool Ecosystem
        │
        ├── Filesystem
        ├── Search
        ├── Edit
        ├── Terminal
        ├── Git
        ├── Testing
        ├── Diagnostics
        ├── Web
        ├── Browser
        ├── LSP
        └── External Tools

Skills SHALL remain above the Tool layer as reusable expertise and
methodology.

This separation SHALL allow the same Tool to be reused by different Skills,
Workflows, and models.

-------------------------------------------------------------------------------

# 10. Recommendations

Based on the current research, ClaireCoder SHOULD:

1. Make filesystem access a core capability.
2. Make file discovery a core capability.
3. Make code search a core capability.
4. Make precise code editing a core capability.
5. Make terminal execution a core capability.
6. Make Git integration a core capability.
7. Make testing and diagnostics first-class engineering capabilities.
8. Build Repository Intelligence as a distinct capability within the Context Engine.
9. Investigate LSP as a complementary intelligence source.
10. Keep web search and web retrieval modular.
11. Keep browser interaction optional.
12. Support MCP without making it mandatory.
13. Treat subagent delegation as orchestration rather than a basic Tool.
14. Support image and screenshot understanding when the selected model permits
    it.
15. Design Tools around structured results and explicit capabilities.
16. Apply permissions at the operation level where practical.
17. Keep third-party Tools isolated from the core.
18. Prefer a small reliable core Toolset over maximum Tool count.

-------------------------------------------------------------------------------

# 11. Expected Outcomes

Successful completion of this research SHALL establish:

- a candidate V1 Tool roster,
- Tool categories,
- Tool responsibility boundaries,
- the relationship between Tools and Repository Intelligence,
- the relationship between Tools and Skills,
- the relationship between Tools and Workflows,
- the role of MCP,
- the role of optional external capabilities,
- the major Tool architecture questions requiring ADR decisions.

-------------------------------------------------------------------------------

# 12. Risks

Potential risks include:

- excessive Tool count,
- overlapping Tool responsibilities,
- unreliable editing,
- unsafe terminal execution,
- excessive Tool output,
- excessive context consumption,
- dependency on external Tool providers,
- insecure third-party Tools,
- unnecessary duplication between search systems,
- excessive complexity in the Tool abstraction.

ClaireCoder SHALL prioritize reliable, composable, and understandable Tools
over maximum capability count.

-------------------------------------------------------------------------------

# 13. Success Criteria

This research succeeds when:

- the essential V1 Tool categories are identified,
- Tool responsibilities are clearly separated,
- repository intelligence has a defined conceptual boundary,
- external Tools have a defined role,
- MCP has a defined architectural position,
- permissions are recognized as part of Tool design,
- the Tool ecosystem can proceed to architecture without repeating the
  competitive research.

-------------------------------------------------------------------------------

# 14. Future Work

The next research document SHALL be:

CC-RES-003 — Skill Architecture Research

It SHALL investigate:

- Skill structure,
- Skill manifests,
- built-in Skills,
- local Skills,
- GitHub Skills,
- third-party Skills,
- Skill Collections,
- Skill discovery,
- progressive loading,
- Skill dependencies,
- Tool requirements,
- security and validation,
- provenance,
- versioning,
- installation and update mechanisms.

The actual initial ClaireCoder Skill roster SHALL be researched there rather
than being prematurely finalized in this document.

-------------------------------------------------------------------------------

# 15. AI Instructions

When continuing ClaireCoder Tool research:

1. Treat Tools as focused engineering capabilities.
2. Keep Tools separate from Skills and Workflows.
3. Preserve model independence.
4. Preserve provider independence.
5. Prefer a small reliable core Toolset.
6. Do not add Tools solely for competitive feature parity.
7. Preserve explicit permission boundaries.
8. Treat third-party Tools as untrusted until validated.
9. Preserve structured and context-efficient Tool results.
10. Keep MCP optional to core operation.
11. Treat Repository Intelligence as a distinct capability within the Context architecture.
12. Preserve compatibility with future Tool protocols.
13. Do not finalize implementation details before the appropriate ADR.
14. Preserve ClaireCoder's architectural simplicity.

###############################################################################

END OF CC-RES-002

###############################################################################