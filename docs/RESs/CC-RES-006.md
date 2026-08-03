###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Research Document
#
# Document Number : CC-RES-006
# Title           : Context, Memory & Engineering Session Research
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document researches the Context, Memory, and Engineering Session systems
required by ClaireCoder.

The objective is to determine how ClaireCoder SHALL maintain enough relevant
information for reliable software engineering without continuously placing
the entire repository, conversation history, Skill library, Tool output, and
previous execution state into the model context.

The research covers:

- conversation context,
- repository context,
- repository intelligence,
- context prioritization,
- context compression,
- persistent memory,
- Engineering Sessions,
- plan persistence,
- execution history,
- session resumption,
- stale context,
- context limits,
- context retrieval.

A fundamental requirement established by previous research is that ClaireCoder
must remain useful across different models with different context capacities.

The Context System SHALL therefore adapt to the selected model instead of
assuming unlimited context.

Memory SHALL also remain distinct from Context.

Context represents information required for the current task.

Memory represents information worth preserving beyond the immediate task.

An Engineering Session represents the persistent state of an ongoing
engineering workflow.

-------------------------------------------------------------------------------

# 2. Background

Coding agents operate on information from several sources simultaneously.

A typical engineering task may involve:

- the user's request,
- previous conversation,
- repository files,
- repository structure,
- project instructions,
- Skill instructions,
- Tool results,
- terminal output,
- test failures,
- planning state,
- previous implementation decisions,
- Git state,
- external research,
- session history.

Sending all available information to every model invocation is inefficient
and can become impossible as repositories and sessions grow.

Modern agent systems therefore use different strategies for context selection,
compression, repository mapping, memory, and session persistence.

OpenCode documents context compaction and automatic continuation when the
context window becomes full. Its architecture also supports project and global
instructions that can influence agent behavior without being part of every
individual user request. ([opencode.ai](https://opencode.ai/docs/agents/?utm_source=chatgpt.com))

Hermes Agent provides persistent sessions, session management, context
compression, memory, and resumable conversations. Its documentation also
describes memory as a separate mechanism from ordinary conversation context.
([github.com](https://github.com/NousResearch/hermes-agent?utm_source=chatgpt.com))

Aider provides repository mapping as a mechanism for giving the model a
compact representation of important repository structure instead of sending
the complete codebase. This is an important reference for ClaireCoder's
Repository Intelligence layer.

These systems demonstrate that Context, Memory, and Session state should be
treated as related but distinct architectural concepts.

-------------------------------------------------------------------------------

# 3. Purpose

This research SHALL determine:

- what information belongs in active context,
- how context should be selected,
- how repository context should be represented,
- how Tool results should enter context,
- how Skills should enter context,
- how context should be compressed,
- how memory differs from context,
- what should be stored in Engineering Sessions,
- how sessions should resume,
- how stale information should be handled,
- how context should adapt to different model limits,
- how plans and execution state should persist,
- how context should remain efficient during long-running tasks.

-------------------------------------------------------------------------------

# 4. Scope

## In Scope

- Active context.
- Conversation context.
- Repository context.
- Repository maps.
- Repository intelligence.
- Project instructions.
- Skill context.
- Tool-result context.
- Planning context.
- Validation context.
- Context prioritization.
- Context budgets.
- Context compression.
- Context summarization.
- Context retrieval.
- Context invalidation.
- Persistent memory.
- Engineering Sessions.
- Session state.
- Session persistence.
- Session resumption.
- Plan persistence.
- Execution history.
- Git state.
- Model context limits.
- Context-aware model selection.
- Long-running workflows.

## Out of Scope

- Final database implementation.
- Final vector database implementation.
- Final repository index implementation.
- Final memory storage implementation.
- Final session file format.
- Final Context Engine implementation.
- Final model context-window implementation.
- User-facing memory-management UI.
- Long-term personal assistant memory unrelated to software engineering.

-------------------------------------------------------------------------------

# 5. Research Questions

### RQ-089

What is the difference between Context, Memory, and Engineering Session state?

---

### RQ-090

What information should always be present in active engineering context?

---

### RQ-091

What information should only be retrieved when relevant?

---

### RQ-092

How should ClaireCoder prioritize context when the model context window is
limited?

---

### RQ-093

How should repository maps interact with direct file retrieval?

---

### RQ-094

How should Skills be loaded into context?

---

### RQ-095

How should Tool results be summarized, truncated, or persisted?

---

### RQ-096

How should terminal output be handled when commands produce large results?

---

### RQ-097

How should context compression work during long-running sessions?

---

### RQ-098

How should ClaireCoder determine what information is safe to discard?

---

### RQ-099

How should persistent Memory differ from Engineering Session state?

---

### RQ-100

What information should survive a session restart?

---

### RQ-101

How should ClaireCoder resume an interrupted engineering task?

---

### RQ-102

How should stale repository information be detected?

---

### RQ-103

How should Git changes affect cached repository information?

---

### RQ-104

How should plans survive context compression?

---

### RQ-105

How should validation results survive context compression?

---

### RQ-106

How should ClaireCoder operate when the selected model has a small context
window?

---

### RQ-107

How should ClaireCoder exploit large-context models without assuming they are
always available?

---

### RQ-108

How should context be shared between the primary agent and subagents?

---

### RQ-109

How should context isolation prevent unnecessary information from leaking
between subagent tasks?

-------------------------------------------------------------------------------

# 6. Research

## 6.1 Context

Context SHALL be defined as information actively provided to the model for
the current reasoning or execution step.

Potential context sources include:

- current user request,
- relevant conversation history,
- repository structure,
- selected files,
- relevant symbols,
- project instructions,
- active Skills,
- Tool results,
- current plan,
- validation results,
- relevant session state.

Context SHALL be dynamic.

Not every available piece of information should be included in every model
call.

-------------------------------------------------------------------------------

## 6.2 Memory

Memory SHALL be treated separately from active context.

Memory represents information that may be useful beyond the immediate
interaction.

Potential engineering memory includes:

- repository conventions,
- recurring project decisions,
- architecture decisions,
- user-defined engineering preferences,
- known project constraints,
- previously established workflow decisions.

Memory SHOULD NOT automatically enter every model request.

Relevant memory SHOULD be retrieved when required.

-------------------------------------------------------------------------------

## 6.3 Engineering Session

An Engineering Session SHALL represent the persistent state of an ongoing
ClaireCoder engineering task.

A session MAY contain:

- user objective,
- current plan,
- completed tasks,
- pending tasks,
- discovered constraints,
- important Tool results,
- validation results,
- decisions,
- changed files,
- Git state,
- unresolved issues,
- current workflow state,
- relevant memory references.

The session SHALL provide enough state to resume work without replaying the
entire original conversation.

-------------------------------------------------------------------------------

## 6.4 Context Hierarchy

ClaireCoder SHOULD investigate a layered context hierarchy.

A conceptual hierarchy is:

Layer 0 — Immediate Objective

- current user request,
- current command,
- current action.

Layer 1 — Active Workflow

- current plan,
- current task,
- current validation state,
- current Mode.

Layer 2 — Repository Context

- relevant files,
- symbols,
- dependencies,
- project instructions,
- repository map.

Layer 3 — Tool Context

- recent Tool results,
- errors,
- test output,
- command results.

Layer 4 — Session Context

- previous decisions,
- completed work,
- unresolved work,
- session history.

Layer 5 — Memory

- durable project information,
- long-term preferences,
- architecture decisions.

The system SHOULD retrieve higher layers only when relevant.

-------------------------------------------------------------------------------

## 6.5 Context Priority

When the context budget is limited, information SHALL be prioritized.

A conceptual priority order is:

1. Current objective.
2. Current task.
3. Relevant instructions.
4. Relevant code.
5. Current plan.
6. Current validation state.
7. Recent Tool results.
8. Relevant repository structure.
9. Relevant session history.
10. Optional historical information.

This ordering SHALL remain configurable.

The Context Engine SHOULD prefer relevance over recency alone.

-------------------------------------------------------------------------------

## 6.6 Repository Context

Repository context is one of the most important context sources for
ClaireCoder.

The Context Engine SHOULD combine:

- repository map,
- file search,
- symbol search,
- dependency information,
- direct file retrieval,
- Git state,
- project instructions.

The repository map SHOULD help identify relevant areas.

Direct file retrieval SHOULD provide the detailed source required for actual
implementation.

Repository mapping SHALL therefore complement, not replace, file retrieval.

-------------------------------------------------------------------------------

## 6.7 Repository Map

A Repository Map MAY contain:

- important files,
- directories,
- symbols,
- classes,
- functions,
- interfaces,
- imports,
- dependencies,
- relationships,
- signatures,
- language information.

The map SHOULD remain compact enough to be useful as context.

It SHOULD be updated when repository structure changes materially.

-------------------------------------------------------------------------------

## 6.8 Context Retrieval

ClaireCoder SHALL investigate relevance-based retrieval.

A retrieval request MAY consider:

- current task,
- file relationships,
- symbols,
- imports,
- previous Tool results,
- Git changes,
- Skills,
- user requirements.

The system SHOULD avoid retrieving large unrelated files merely because they
exist in the repository.

-------------------------------------------------------------------------------

## 6.9 Skill Context

Skills SHALL follow the progressive-disclosure principles established in
CC-RES-003.

The initial context SHOULD contain only compact Skill metadata when possible.

The full Skill instructions SHOULD be loaded when the Skill becomes relevant.

Supporting references SHOULD be loaded only when required.

This prevents a large installed Skill roster from consuming the active context
window.

-------------------------------------------------------------------------------

## 6.10 Tool Results

Tool results can become a major source of context growth.

Examples include:

- terminal output,
- search results,
- file contents,
- test logs,
- compiler errors,
- web pages,
- Git history.

ClaireCoder SHALL investigate Tool-result normalization.

Large Tool results SHOULD be:

- truncated,
- filtered,
- summarized,
- persisted,
- or made retrievable by reference.

The system SHOULD preserve important information while avoiding unnecessary
repetition.

-------------------------------------------------------------------------------

## 6.11 Terminal Output

Terminal output requires special handling because commands can produce
extremely large results.

ClaireCoder SHOULD investigate:

- output limits,
- error prioritization,
- line truncation,
- pagination,
- persistent command logs,
- structured test output,
- retrieval of previous command output.

The most relevant portion of a failed command SHOULD remain readily
available.

-------------------------------------------------------------------------------

## 6.12 Context Compression

Context compression SHALL be considered necessary for long-running sessions.

Compression MAY include:

- conversation summarization,
- Tool-result summarization,
- completed-task compression,
- historical message removal,
- plan preservation,
- important-decision preservation.

Compression SHALL preserve information required for continued engineering.

It SHALL NOT simply truncate the oldest messages without considering their
engineering importance.

-------------------------------------------------------------------------------

## 6.13 Compaction

A useful compaction process MAY be:

Active Context
    ↓
Identify Durable Information
    ↓
Preserve Plan / Decisions / Constraints
    ↓
Summarize Historical Activity
    ↓
Discard Redundant Detail
    ↓
Construct New Context

The exact implementation SHALL be determined later.

-------------------------------------------------------------------------------

## 6.14 Plan Persistence

The active plan SHALL not depend entirely on conversation history.

The Engineering Session SHOULD persist:

- objective,
- plan,
- task state,
- completed work,
- pending work,
- dependencies,
- validation requirements,
- discovered constraints.

This allows the plan to survive context compression and session restart.

-------------------------------------------------------------------------------

## 6.15 Validation Persistence

Validation results SHOULD be represented separately from ordinary conversation
history.

Important information includes:

- tests executed,
- tests passed,
- tests failed,
- compiler errors,
- lint failures,
- known unresolved issues.

The system SHOULD avoid rerunning expensive validation solely because previous
results were lost during context compression.

-------------------------------------------------------------------------------

## 6.16 Stale Context

Repository information can become stale after:

- file edits,
- Git operations,
- branch changes,
- external modifications,
- generated files changing,
- dependency updates.

ClaireCoder SHALL investigate invalidation strategies.

Cached repository information SHOULD include enough metadata to determine when
it must be refreshed.

-------------------------------------------------------------------------------

## 6.17 Git State

Git state can provide valuable context.

The Context Engine SHOULD be able to determine:

- current branch,
- modified files,
- staged files,
- untracked files,
- recent commits,
- relevant diffs.

Git state SHOULD help the agent understand what has already changed during a
session.

-------------------------------------------------------------------------------

## 6.18 Session Resumption

A resumed session SHOULD reconstruct:

- current objective,
- active plan,
- workflow state,
- relevant repository state,
- important decisions,
- unresolved issues,
- validation state.

It SHOULD NOT require replaying every historical Tool result.

The Context Engine SHOULD retrieve historical details only when necessary.

-------------------------------------------------------------------------------

## 6.19 Subagent Context

Subagents SHOULD receive only the context required for their assigned task.

A subagent MAY receive:

- objective,
- relevant files,
- relevant Skills,
- task-specific instructions,
- required repository context.

The subagent SHOULD NOT automatically inherit the entire primary-agent
conversation.

This reduces context usage and prevents unnecessary information leakage
between tasks.

-------------------------------------------------------------------------------

## 6.20 Model Context Limits

ClaireCoder SHALL treat context capacity as a model capability.

The Context Engine SHOULD know:

- maximum context capacity,
- current context usage,
- expected output reservation,
- Tool-result budget,
- Skill context usage.

When capacity becomes constrained, ClaireCoder SHOULD reduce context before
the model request fails.

-------------------------------------------------------------------------------

## 6.21 Small-Context Models

ClaireCoder SHALL remain usable with smaller-context local models.

The Context Engine SHOULD respond by:

- retrieving fewer files,
- using stronger repository mapping,
- summarizing Tool output,
- reducing historical conversation,
- loading Skills progressively,
- compressing session state.

Small-context models SHALL not automatically be treated as unsupported.

-------------------------------------------------------------------------------

## 6.22 Large-Context Models

Large-context models MAY allow:

- more repository files,
- longer conversation history,
- larger Tool results,
- richer planning context.

However, ClaireCoder SHOULD still prefer relevant context over indiscriminate
context inclusion.

A large context window SHALL not be treated as a reason to send everything.

-------------------------------------------------------------------------------

# 7. Context Classification

The initial conceptual classification SHALL be:

Ephemeral Context:

- current Tool result,
- temporary search result,
- intermediate reasoning artifact.

Active Context:

- current objective,
- current task,
- relevant files,
- current plan,
- validation state.

Session State:

- completed work,
- pending work,
- decisions,
- unresolved issues,
- execution state.

Repository State:

- repository map,
- Git state,
- project instructions,
- structural information.

Persistent Memory:

- durable project knowledge,
- stable engineering decisions,
- long-term preferences.

This classification is provisional.

-------------------------------------------------------------------------------

# 8. Engineering Session Lifecycle

The conceptual Engineering Session lifecycle SHALL be:

CREATE
  ↓
UNDERSTAND
  ↓
PLAN
  ↓
EXECUTE
  ↓
VALIDATE
  ↓
PERSIST
  ↓
RESUME
  ↓
CONTINUE
  ↓
COMPLETE
  ↓
ARCHIVE

A session SHOULD remain resumable until the user explicitly completes,
archives, or removes it.

-------------------------------------------------------------------------------

# 9. Analysis

Context, Memory, and Engineering Sessions should not become one large storage
system.

Their responsibilities are different.

Context answers:

"What does the model need right now?"

Memory answers:

"What information is worth preserving for future work?"

Engineering Session answers:

"What is the current state of this engineering task?"

Repository Intelligence answers:

"What does the repository look like and what parts are relevant?"

This separation is essential for scalability.

The Context Engine SHALL coordinate these sources rather than permanently
merging them.

-------------------------------------------------------------------------------

# 10. Recommendations

Based on the current research, ClaireCoder SHOULD:

1. Separate Context, Memory, and Engineering Sessions.
2. Build a dedicated Context Engine.
3. Treat repository intelligence as a major context source.
4. Use progressive Skill loading.
5. Normalize large Tool results.
6. Preserve important Tool results outside active context when necessary.
7. Persist plans independently from conversation history.
8. Persist validation state.
9. Track Git state.
10. Detect stale repository information.
11. Support context compression.
12. Preserve durable information during compaction.
13. Adapt context to model limits.
14. Support small-context local models.
15. Exploit large-context models without depending on them.
16. Give subagents task-specific context.
17. Avoid replaying entire conversations during session resumption.
18. Prioritize relevance over raw recency.
19. Keep persistent Memory out of active context unless relevant.
20. Keep Engineering Sessions focused on engineering state.
21. Preserve user control over durable Memory.
22. Keep Context implementation replaceable.
23. Avoid making a vector database mandatory for V1.
24. Avoid overengineering Memory before the actual use cases are established.

These recommendations SHALL guide later architecture research but SHALL NOT
become final implementation requirements until the appropriate ADRs are
completed.

-------------------------------------------------------------------------------

# 11. Expected Outcomes

Successful completion of this research SHALL establish:

- the Context, Memory, and Session boundaries,
- context-priority requirements,
- repository-context requirements,
- context-retrieval requirements,
- Tool-result handling requirements,
- compression requirements,
- session persistence requirements,
- session-resumption requirements,
- stale-context requirements,
- model-context adaptation requirements,
- subagent-context requirements.

-------------------------------------------------------------------------------

# 12. Risks

Potential risks include:

- context overload,
- excessive context compression,
- loss of important engineering information,
- stale repository indexes,
- stale Tool results,
- accidental persistence of sensitive information,
- unnecessary long-term memory,
- excessive session storage,
- context leakage between subagents,
- excessive dependence on vector retrieval,
- poor relevance ranking.

ClaireCoder SHALL prioritize deterministic and understandable context
management over unnecessary retrieval complexity.

-------------------------------------------------------------------------------

# 13. Success Criteria

This research succeeds when:

- Context, Memory, and Engineering Sessions are clearly separated,
- repository context has a defined role,
- Tool results have a defined lifecycle,
- context compression requirements are established,
- session persistence requirements are established,
- session resumption is established conceptually,
- stale context handling is established,
- small-context models remain viable,
- large-context models can be exploited,
- the Context architecture can proceed to ADR without repeating the research.

-------------------------------------------------------------------------------

# 14. Future Work

The next research document SHALL be:

CC-RES-007 — Modes, Commands & User Interaction Research

It SHALL investigate:

- ClaireCoder Modes,
- command system,
- command hierarchy,
- interactive CLI/TUI behavior,
- Plan mode,
- Build mode,
- Review mode,
- Research mode,
- Debug mode,
- permissions interaction,
- session commands,
- Skill commands,
- model commands,
- Tool visibility,
- user approvals,
- interruption,
- cancellation,
- status display,
- progress display,
- ClaireCoder header and visual identity.

The research SHALL also investigate how the Claire image/header requested for
ClaireCoder should coexist with a professional coding-agent CLI without
reducing usability.

-------------------------------------------------------------------------------

# 15. AI Instructions

When continuing ClaireCoder Context, Memory, and Session research:

1. Keep Context separate from Memory.
2. Keep Memory separate from Engineering Session state.
3. Keep Repository Intelligence separate from generic Memory.
4. Prefer relevance over indiscriminate context inclusion.
5. Preserve plans during context compression.
6. Preserve important validation results.
7. Detect stale repository information.
8. Adapt to model context limits.
9. Keep small-context local models viable.
10. Do not assume large-context models.
11. Avoid loading every Skill into context.
12. Normalize large Tool results.
13. Keep subagent context bounded.
14. Preserve session resumability.
15. Avoid storing unnecessary information permanently.
16. Preserve user control over durable Memory.
17. Avoid making complex retrieval infrastructure mandatory without evidence.
18. Do not finalize implementation details before the appropriate ADR.
19. Preserve ClaireCoder's architectural simplicity.

###############################################################################

END OF CC-RES-006

###############################################################################