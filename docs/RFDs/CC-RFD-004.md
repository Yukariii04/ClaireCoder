###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                  Research Foundation Document
#
# Document Number : CC-RFD-004
# Title           : Skill System & Extension Model
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document defines the foundational Skill System of ClaireCoder.

Skills provide reusable domain expertise, behavioral guidance, engineering
procedures, quality standards, and optional supporting resources that can be
loaded by ClaireCoder when required.

The Skill System SHALL allow users to select skills individually, install
curated Skill Collections, or add skills from third-party sources.

The system SHALL remain independent from any specific language model or
provider.

-------------------------------------------------------------------------------

# 2. Background

Modern coding agents increasingly use reusable instruction packages to extend
their capabilities beyond their core behavior.

OpenCode provides on-demand `SKILL.md` based skills that can be discovered
from project and user locations. Hermes similarly uses on-demand skills with
support for bundled, optional, and community-provided skills.

Projects such as Stop Slop and Impeccable demonstrate another important
possibility: specialized skills can provide focused expertise that would be
difficult or undesirable to hard-code into an agent's core behavior. Stop Slop
is distributed as a `SKILL.md` with supporting reference material, while
Impeccable provides a larger design skill with commands and supporting
resources.

ClaireCoder SHALL build upon these ideas while maintaining its own extension
model.

-------------------------------------------------------------------------------

# 3. Purpose

The Skill System SHALL:

- provide reusable engineering expertise,
- allow skills to be added without modifying ClaireCoder's core,
- support built-in skills,
- support locally created skills,
- support third-party skills,
- support curated Skill Collections,
- allow skills to be loaded when relevant,
- provide a foundation for future community extensions.

-------------------------------------------------------------------------------

# 4. Design Philosophy

A Skill is **not**:

- a language model,
- a Tool,
- a Workflow,
- a replacement for the Engineering Engine,
- a permanent modification of ClaireCoder's core behavior.

A Skill represents specialized knowledge, rules, procedures, standards, or
behavior that can be made available to the Engineering Engine when required.

Skills SHALL remain modular so that users can add, remove, replace, or update
their engineering capabilities without modifying ClaireCoder itself.

-------------------------------------------------------------------------------

# 5. Responsibilities

The Skill System SHALL:

- discover available skills,
- provide skill metadata,
- make relevant skills available to the Engineering Engine,
- support progressive skill loading,
- support local and external skill sources,
- support Skill Collections,
- preserve skill provenance,
- respect skill permissions,
- support skill validation and compatibility.

-------------------------------------------------------------------------------

# 6. Scope

## In Scope

- Built-in skills.
- Optional skills.
- Local skills.
- Third-party skills.
- Git-based skills.
- Skill Collections.
- Skill discovery.
- Skill loading.
- Skill metadata.
- Skill compatibility.
- Skill validation.
- Skill permissions.

## Out of Scope

- Language-model implementation.
- Core Tool implementation.
- Workflow execution.
- Provider-specific behavior.
- Centralized marketplace requirements.
- Mandatory third-party services.

-------------------------------------------------------------------------------

# 7. Design Principles

The Skill System SHALL:

- remain model independent,
- remain provider independent,
- remain modular,
- support progressive disclosure,
- support multiple sources,
- preserve user control,
- preserve skill provenance,
- allow skills to evolve independently,
- avoid unnecessary context consumption.

-------------------------------------------------------------------------------

# 8. Research Questions

### RQ-017

What is the minimum structure required for a ClaireCoder Skill?

---

### RQ-018

How should ClaireCoder distinguish between Skills, Tools, and Workflows?

---

### RQ-019

How should skills be discovered and selected without loading every skill into
the model context?

---

### RQ-020

How should built-in, local, and third-party skills coexist?

---

### RQ-021

How should Skill Collections be represented and resolved?

---

### RQ-022

How should ClaireCoder validate the safety, compatibility, provenance, and
integrity of third-party skills?

---

### RQ-023

How should skills declare required tools, dependencies, platforms, or
configuration?

-------------------------------------------------------------------------------

# 9. Expected Outcomes

Successful completion establishes:

- one canonical Skill philosophy,
- a model-independent extension mechanism,
- support for individual skills,
- support for Skill Collections,
- support for third-party skills,
- a foundation for community-driven extension.

-------------------------------------------------------------------------------

# 10. Risks

Potential risks include:

- malicious third-party skills,
- prompt injection through skill content,
- excessive context consumption,
- conflicting skills,
- skill shadowing,
- incompatible dependencies,
- uncontrolled skill permissions,
- excessive complexity.

The Skill System SHALL prioritize safety, transparency, and predictable
behavior over unrestricted extensibility.

-------------------------------------------------------------------------------

# 11. Success Criteria

This document succeeds when:

- Skills are clearly distinguished from Tools and Workflows,
- individual skill installation is supported conceptually,
- Skill Collections are established conceptually,
- third-party extensions are supported conceptually,
- progressive loading is established,
- skill safety and provenance are recognized,
- future skill architecture can evolve independently of the Engineering
  Engine.

-------------------------------------------------------------------------------

# 12. Future Work

Future documents SHALL determine:

- the canonical Skill specification,
- Skill manifest structure,
- Skill directory structure,
- installation and update mechanisms,
- Skill Collection format,
- discovery mechanisms,
- validation and security,
- dependency handling,
- skill-to-tool interaction,
- skill-to-workflow interaction.

-------------------------------------------------------------------------------

# 13. AI Instructions

When producing ClaireCoder Skill architecture:

1. Treat Skills as modular extensions rather than core agent behavior.
2. Preserve separation between Skills, Tools, Workflows, and the Engineering
   Engine.
3. Preserve model and provider independence.
4. Support individual skills and Skill Collections.
5. Preserve support for local and third-party skills.
6. Load skill content only when relevant whenever practical.
7. Treat third-party skills as untrusted until validated.
8. Preserve skill provenance and user visibility.
9. Do not allow skills to silently bypass ClaireCoder permissions.
10. Preserve architectural simplicity.

###############################################################################

END OF CC-RFD-004

###############################################################################