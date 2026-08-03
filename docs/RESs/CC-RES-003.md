###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Research Document
#
# Document Number : CC-RES-003
# Title           : Skill Architecture Research
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document researches the Skill System required by ClaireCoder.

The objective is to determine how ClaireCoder SHALL discover, install, store,
load, validate, manage, and execute Skills while keeping Skills independent
from the core agent implementation.

The research examines current Skill systems used by modern coding agents,
including OpenCode and Hermes Agent, together with community Skill projects
such as Stop Slop, Ponytail, and Caveman.

ClaireCoder SHALL support multiple Skill sources and SHALL provide a simple
way for users to select the Skills they want during setup.

The initial Skill source model SHALL support three primary paths:

1. Manual selection.
2. Curated Skill Collections.
3. Third-party Skills from external sources.

The purpose of this document is not to finalize the Skill manifest or
implementation.

It SHALL establish the research foundation for the ClaireCoder Skill
Architecture and the later Skill roster and Collection decisions.

-------------------------------------------------------------------------------

# 2. Background

Modern coding agents increasingly use Skills as a reusable extension layer.

OpenCode describes Skills as Markdown instructions discovered from project or
user locations and loaded on demand through a native Skill mechanism.
Supporting scripts, references, and other files can exist alongside the main
SKILL.md.

Hermes Agent similarly uses Skills as on-demand knowledge documents.
Hermes provides bundled Skills, optional Skills, Skill discovery, a Skills
Hub, installation, configuration, and progressive disclosure so that the
agent does not load every Skill's full content into context.

Hermes also explicitly distinguishes Skills from Tools. Skills are suitable
when behavior can be expressed through instructions and existing capabilities,
while Tools are more appropriate when custom execution logic, authentication,
streaming, binary processing, or precise integration is required.


Community projects demonstrate another important direction.

Stop Slop is a reusable Skill focused on removing predictable AI-writing
patterns and contains a main SKILL.md plus reference material.

Ponytail demonstrates a portable Skill distribution that can be used across
multiple agent hosts and can include multiple related Skills and commands.
It specifically targets unnecessary engineering complexity and supports
different intensity levels.

Caveman demonstrates a more specialized behavioral Skill intended to reduce
agent output verbosity and token usage.

These examples demonstrate that a Skill does not have to represent a
technical capability alone.

A Skill can provide:

- domain expertise,
- engineering methodology,
- quality standards,
- behavioral constraints,
- workflow knowledge,
- communication rules,
- design expertise,
- token-efficiency strategies,
- specialized procedures.

ClaireCoder SHALL therefore treat Skills as a broad but controlled extension
mechanism.

-------------------------------------------------------------------------------

# 3. Purpose

This research SHALL determine:

- what constitutes a ClaireCoder Skill,
- how Skills differ from Tools,
- how Skills differ from Workflows,
- how Skills are discovered,
- how Skills are loaded,
- how Skills are installed,
- how Skills are removed or updated,
- how Skills are grouped into Collections,
- how third-party Skills are handled,
- how Skill dependencies are represented,
- how Skill permissions operate,
- how Skill provenance is preserved,
- how Skill conflicts are handled,
- how Skill context consumption is controlled,
- how the initial ClaireCoder Skill roster should be developed.

-------------------------------------------------------------------------------

# 4. Scope

## In Scope

- Skill definition.
- Skill structure.
- Skill metadata.
- SKILL.md-style systems.
- Progressive disclosure.
- Skill discovery.
- Skill installation.
- Skill removal.
- Skill updates.
- Local Skills.
- Built-in Skills.
- Third-party Skills.
- GitHub Skills.
- External Skill sources.
- Skill Collections.
- Skill dependencies.
- Tool requirements.
- Model requirements.
- Platform compatibility.
- Skill permissions.
- Skill provenance.
- Skill validation.
- Skill versioning.
- Skill conflicts.
- Skill activation.
- Skill invocation.
- Skill configuration.
- Skill references.
- Skill scripts.
- Skill templates.
- Skill security.
- Skill roster design.

## Out of Scope

- Final Skill manifest.
- Final Skill directory structure.
- Final Skill installer implementation.
- Final Skill marketplace implementation.
- Final Skill execution engine.
- Final Tool implementation.
- Final Workflow implementation.
- Final model architecture.
- Final CLI implementation.
- Final Skill roster.
- Final Skill Collection roster.

-------------------------------------------------------------------------------

# 5. Research Questions

### RQ-030

What is the minimum structure required for a ClaireCoder Skill?

---

### RQ-031

What information should Skill metadata contain?

---

### RQ-032

How should ClaireCoder distinguish Skills from Tools?

---

### RQ-033

How should ClaireCoder distinguish Skills from Workflows?

---

### RQ-034

How should Skills be discovered without loading every Skill into model
context?

---

### RQ-035

How should ClaireCoder support built-in, local, GitHub, and third-party
Skills through a common model?

---

### RQ-036

How should users manually select Skills during ClaireCoder setup?

---

### RQ-037

How should curated Skill Collections be represented and installed?

---

### RQ-038

How should a user install an additional Skill from another source after
initial setup?

---

### RQ-039

How should Skill dependencies be represented?

---

### RQ-040

How should Skills declare required Tools, models, platforms, or external
configuration?

---

### RQ-041

How should third-party Skills be validated before activation?

---

### RQ-042

How should ClaireCoder preserve Skill provenance and source information?

---

### RQ-043

How should conflicting Skills be detected and resolved?

---

### RQ-044

How should Skills be versioned and updated?

---

### RQ-045

How should Skill permissions interact with Tool permissions and autonomy
levels?

---

### RQ-046

How should Skills provide configuration requirements without embedding
secrets directly into Skill files?

---

### RQ-047

How should ClaireCoder handle Skills that become incompatible with newer
agent versions?

---

### RQ-048

How should Skills created by the user or agent itself be managed?

-------------------------------------------------------------------------------

# 6. Research

## 6.1 OpenCode Skill Model

OpenCode provides a useful reference for progressive Skill discovery.

Skills can exist at project and global locations, including compatible
directories used by other agent ecosystems. OpenCode also supports explicit
Skill source configuration and HTTP Skill catalogs.

OpenCode exposes compact Skill metadata to the model rather than injecting
every Skill's complete instructions into the context.

The full Skill is loaded only when selected.

This provides an important architectural principle for ClaireCoder:

Skill discovery SHOULD be cheap.

Skill loading SHOULD be deliberate.

Supporting files SHOULD be loaded only when necessary.

-------------------------------------------------------------------------------

## 6.2 Hermes Skill Model

Hermes provides another strong reference.

Its Skill system includes:

- bundled Skills,
- optional Skills,
- Skill search,
- Skill installation,
- a Skills Hub,
- Skill configuration,
- Skill creation,
- progressive disclosure,
- per-platform management.

Hermes loads a compact Skill list first and retrieves the complete Skill only
when required.

This confirms that a large Skill library can remain practical if the Skill
system separates discovery from full loading.

ClaireCoder SHALL investigate the same principle.

-------------------------------------------------------------------------------

## 6.3 Skill Structure

Current Skill systems commonly use a directory containing a primary
SKILL.md file and optional supporting material.

Supporting material can include:

- references,
- examples,
- scripts,
- templates,
- configuration information.

OpenCode and Hermes both use this general directory-oriented approach.


ClaireCoder SHALL investigate a similar structure because it allows Skills to
remain self-contained and portable.

-------------------------------------------------------------------------------

## 6.4 Progressive Disclosure

Progressive disclosure SHALL be considered a core Skill architecture
principle.

The conceptual loading hierarchy is:

Skill Metadata
    ↓
Skill Instructions
    ↓
Supporting References
    ↓
Scripts / Templates / Resources

Only the information required for the current task SHOULD be loaded.

This prevents a large Skill roster from consuming the entire context window.

-------------------------------------------------------------------------------

## 6.5 Skill Versus Tool

Hermes provides a useful distinction:

A Skill is appropriate when the capability can be expressed through
instructions and existing Tools.

A Tool is appropriate when the capability requires custom execution logic,
authentication, precise processing, binary handling, streaming, or similar
integration.

ClaireCoder SHALL adopt this distinction as a research principle.

Examples of likely Skills:

- coding methodology,
- UI/UX methodology,
- writing quality,
- repository conventions,
- testing methodology,
- framework-specific procedures.

Examples of likely Tools:

- browser automation,
- filesystem access,
- terminal execution,
- structured API integrations,
- precise binary processing.

The final boundary SHALL be determined during architecture work.

-------------------------------------------------------------------------------

## 6.6 Built-in Skills

ClaireCoder SHOULD provide a curated set of built-in or officially bundled
Skills.

These Skills should focus on capabilities that are broadly useful to
software engineering rather than attempting to cover every possible domain.

Potential categories include:

- engineering quality,
- repository understanding,
- debugging,
- testing,
- frontend development,
- backend development,
- architecture,
- documentation,
- security,
- UI/UX,
- research.

The exact roster SHALL be determined in later research.

-------------------------------------------------------------------------------

## 6.7 Community and Third-party Skills

ClaireCoder SHALL support Skills originating outside the ClaireCoder project.

Potential sources include:

- Git repositories,
- local directories,
- Skill catalogs,
- community collections,
- manually provided Skill files,
- future registries.

Third-party Skills SHALL NOT automatically receive unrestricted trust.

Source provenance and permissions SHALL remain visible to the user.

-------------------------------------------------------------------------------

## 6.8 Three-Path Skill Acquisition Model

The proposed ClaireCoder setup experience SHALL investigate three acquisition
paths.

Path A — Manual Selection

The user browses the available Skill roster and selects individual Skills.

Path B — Skill Collection

The user selects a curated Collection containing a compatible group of Skills.

Path C — Third-party Source

The user provides another Skill source after setup, such as a Git repository,
local directory, or supported external catalog.

The three paths SHOULD coexist rather than replacing one another.

-------------------------------------------------------------------------------

## 6.9 Skill Collections

Skill Collections are a major ClaireCoder opportunity.

A Collection SHOULD represent a curated group of Skills designed to work
together.

Examples could eventually include:

- Frontend Development Collection.
- Backend Development Collection.
- Full-Stack Collection.
- UI/UX Collection.
- Python Collection.
- Game Development Collection.
- Open-Source Maintainer Collection.
- Minimalist Engineering Collection.

Collections SHALL NOT necessarily mean that every contained Skill is always
loaded.

A Collection can primarily define:

- membership,
- compatibility,
- recommended Skills,
- dependencies,
- versions,
- optional Skills.

-------------------------------------------------------------------------------

## 6.10 Stop Slop

Stop Slop is an important example for ClaireCoder because it represents a
behavioral quality Skill rather than a conventional technical capability.

Its purpose is to remove predictable AI-writing patterns from prose and its
repository contains a primary SKILL.md plus supporting references.


ClaireCoder SHALL investigate whether Stop Slop should be:

- bundled,
- optional,
- included in a Writing Collection,
- or offered as an officially recommended third-party Skill.

It SHALL NOT automatically be treated as a mandatory global behavior until
compatibility and interaction with other Skills are researched.

-------------------------------------------------------------------------------

## 6.11 Ponytail

Ponytail provides a particularly relevant example of an engineering-quality
Skill.

It focuses on avoiding unnecessary code and over-engineering, provides
multiple intensity levels, and distributes its behavior across multiple agent
hosts.

This is closely aligned with ClaireCoder's goal of avoiding unnecessary AI
slop in software implementation.

ClaireCoder SHALL investigate Ponytail as a potential:

- built-in recommended Skill,
- engineering-quality Collection member,
- optional third-party Skill,
- reference for designing its own anti-overengineering behavior.

ClaireCoder SHALL not assume that Ponytail's exact rules should become core
agent behavior.

-------------------------------------------------------------------------------

## 6.12 Caveman

Caveman provides a different kind of behavioral Skill.

Its stated purpose is to reduce agent output verbosity and token usage while
maintaining technical accuracy.

This demonstrates that Skills can influence communication efficiency without
changing the underlying model.

However, external evidence also indicates that aggressive output compression
can have quality trade-offs in some settings. Therefore, ClaireCoder SHALL
treat this category as configurable rather than universally enabled.

Caveman SHALL be investigated as a possible optional communication or
token-efficiency Skill.

-------------------------------------------------------------------------------

## 6.13 UI/UX and Design Skills

ClaireCoder SHALL investigate specialized design Skills such as Impeccable
and other UI/UX-oriented Skill systems.

These Skills are important because they demonstrate how an agent can gain
specialized design methodology without requiring a separate model.

Research SHALL determine:

- whether design Skills belong in the default roster,
- whether they belong in a UI/UX Collection,
- how visual references are handled,
- how browser and screenshot Tools interact with them,
- whether they require vision-capable models.

-------------------------------------------------------------------------------

## 6.14 Skill Dependencies

Skills may depend on:

- Tools,
- other Skills,
- external commands,
- packages,
- APIs,
- model capabilities,
- operating systems.

ClaireCoder SHALL investigate explicit dependency declarations.

A Skill SHOULD be able to communicate that it cannot operate correctly
without a required capability.

The Skill system SHOULD distinguish:

- required dependency,
- optional dependency,
- recommended dependency,
- fallback capability.

-------------------------------------------------------------------------------

## 6.15 Skill Compatibility

A Skill may be compatible with:

- all models,
- specific model capabilities,
- specific operating systems,
- specific Tools,
- specific ClaireCoder versions.

ClaireCoder SHALL investigate compatibility metadata so that incompatible
Skills can be identified before activation.

-------------------------------------------------------------------------------

## 6.16 Skill Security

Third-party Skills can contain instructions, scripts, references, and
potentially executable components.

ClaireCoder SHALL therefore treat external Skills as untrusted by default.

The research SHALL investigate:

- provenance,
- integrity,
- source visibility,
- permission requirements,
- executable scripts,
- network access,
- Tool access,
- sandboxing,
- user approval,
- update trust.

A Skill SHALL NOT silently bypass ClaireCoder's permission model.

-------------------------------------------------------------------------------

# 7. Skill Classification

The initial conceptual classification SHALL be:

Core Skills:

- engineering methodology,
- repository methodology,
- debugging methodology,
- testing methodology,
- code-quality methodology.

Domain Skills:

- frontend,
- backend,
- databases,
- Python,
- JavaScript/TypeScript,
- mobile,
- game development,
- cloud,
- DevOps.

Specialized Skills:

- UI/UX,
- security,
- accessibility,
- documentation,
- research,
- performance.

Behavioral Skills:

- Stop Slop,
- Ponytail,
- Caveman,
- communication and verbosity controls.

Community Skills:

- GitHub Skills,
- local Skills,
- third-party Skills,
- community Collections.

This classification is provisional.

It SHALL NOT be treated as the final ClaireCoder Skill roster.

-------------------------------------------------------------------------------

# 8. Skill Lifecycle

The research proposes the following conceptual lifecycle:

Discovery
    ↓
Inspection
    ↓
Selection
    ↓
Validation
    ↓
Installation
    ↓
Availability
    ↓
On-demand Loading
    ↓
Execution
    ↓
Update / Disable / Removal

The exact lifecycle SHALL be determined during architecture design.

-------------------------------------------------------------------------------

# 9. Analysis

The competitive research indicates that the most important property of a
Skill system is not the ability to store many Skills.

It is the ability to make a large Skill library practical.

ClaireCoder SHOULD therefore prioritize:

- cheap discovery,
- progressive loading,
- clear descriptions,
- reliable activation,
- source transparency,
- permission control,
- compatibility detection,
- simple installation.

The three acquisition paths are particularly important:

Manual Selection gives users control.

Collections provide convenience.

Third-party Sources provide extensibility.

These paths should complement each other.

The system should also avoid turning every Skill into a permanent system-prompt
instruction.

A Skill should normally remain dormant until relevant.

-------------------------------------------------------------------------------

# 10. Recommendations

Based on the current research, ClaireCoder SHOULD:

1. Use a self-contained Skill format.
2. Investigate SKILL.md-style portability.
3. Support supporting references and resources.
4. Use progressive disclosure.
5. Keep Skill metadata compact.
6. Support built-in Skills.
7. Support local Skills.
8. Support GitHub and third-party Skills.
9. Support curated Skill Collections.
10. Provide manual Skill selection.
11. Allow additional Skills to be installed after setup.
12. Preserve Skill provenance.
13. Validate third-party Skills.
14. Support Skill permissions.
15. Support Skill compatibility metadata.
16. Keep Skills separate from Tools.
17. Keep Skills separate from Workflows.
18. Avoid loading every installed Skill into model context.
19. Investigate Stop Slop as a recommended quality Skill.
20. Investigate Ponytail as an anti-overengineering Skill.
21. Investigate Caveman as an optional token-efficiency Skill.
22. Investigate Impeccable and similar systems for UI/UX capabilities.
23. Keep behavioral Skills configurable rather than universally mandatory.
24. Prefer small, focused Skills over enormous domain-wide Skills.
25. Preserve the ability for the community to create and distribute Skills.

These recommendations SHALL guide subsequent architecture research but SHALL
NOT become final implementation decisions until the appropriate ADRs are
completed.

-------------------------------------------------------------------------------

# 11. Expected Outcomes

Successful completion of this research SHALL establish:

- a canonical conceptual Skill model,
- the Skill versus Tool boundary,
- the Skill versus Workflow boundary,
- progressive disclosure requirements,
- Skill acquisition paths,
- Skill Collection requirements,
- third-party Skill requirements,
- Skill dependency requirements,
- Skill compatibility requirements,
- Skill security requirements,
- the foundation for the ClaireCoder Skill roster.

-------------------------------------------------------------------------------

# 12. Risks

Potential risks include:

- malicious third-party Skills,
- prompt injection through Skill content,
- unsafe Skill scripts,
- excessive context consumption,
- conflicting Skills,
- Skill shadowing,
- incompatible dependencies,
- stale Skills,
- excessive Skill count,
- poor Skill descriptions,
- unnecessary always-on behavior,
- Skill-induced model degradation.

ClaireCoder SHALL prioritize safety, predictability, and context efficiency
over unrestricted Skill extensibility.

-------------------------------------------------------------------------------

# 13. Success Criteria

This research succeeds when:

- the Skill concept is clearly defined,
- Skills and Tools are separated,
- Skills and Workflows are separated,
- the three Skill acquisition paths are established,
- progressive loading is established,
- third-party Skill requirements are established,
- Skill security requirements are established,
- Skill Collections are conceptually defined,
- the initial Skill roster can be researched without changing the underlying
  Skill architecture.

-------------------------------------------------------------------------------

# 14. Future Work

The next research document SHALL be:

CC-RES-004 — Workflow & Planning Research

It SHALL investigate:

- planning strategies,
- planning depth,
- execution loops,
- task decomposition,
- review loops,
- validation,
- recovery,
- replanning,
- autonomous execution,
- mode-specific planning,
- model participation in planning,
- planning temperature and reasoning configuration,
- how ClaireCoder should achieve the desired high-planning behavior without
  coupling the architecture to one model provider.

A later Skill-specific research phase SHALL determine the actual V1 roster and
Collections, including which community Skills should be bundled, recommended,
optional, or excluded.

-------------------------------------------------------------------------------

# 15. AI Instructions

When continuing ClaireCoder Skill research:

1. Treat Skills as modular extensions.
2. Preserve the separation between Skills, Tools, Workflows, and Models.
3. Prefer progressive disclosure.
4. Keep Skill discovery lightweight.
5. Preserve local and third-party Skill support.
6. Preserve the three acquisition paths:
   manual selection, Collections, and third-party sources.
7. Treat third-party Skills as untrusted until validated.
8. Preserve Skill provenance.
9. Preserve Skill permissions.
10. Avoid making every Skill permanently active.
11. Prefer focused Skills over excessively broad Skills.
12. Treat Stop Slop, Ponytail, Caveman, Impeccable, and similar projects as
    research references until the final roster is decided.
13. Do not copy external Skill implementations without appropriate licensing
    and architectural justification.
14. Preserve compatibility with future Skill standards.
15. Do not finalize the Skill manifest before the appropriate ADR.
16. Preserve ClaireCoder's architectural simplicity.

###############################################################################

END OF CC-RES-003

###############################################################################