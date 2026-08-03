###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Research Document
#
# Document Number : CC-RES-004
# Title           : Workflow & Planning Research
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document researches the planning and workflow behavior required by
ClaireCoder.

The objective is to determine how ClaireCoder SHALL transform a user
objective into a reliable engineering process involving planning, context
retrieval, Tool execution, validation, correction, and completion.

The research examines planning and execution approaches used by modern coding
agents, including Claude Code, Codex, OpenCode, Hermes Agent, and related
systems.

A major objective is to determine how ClaireCoder can provide the high-quality
planning and execution behavior expected from advanced coding agents while
remaining independent of any particular model provider.

ClaireCoder SHALL support different levels of planning depth rather than
forcing every task through the same planning process.

The planning system SHALL also remain practical for users who only have
access to a single affordable or local model.

-------------------------------------------------------------------------------

# 2. Background

Software engineering is inherently iterative.

A useful coding agent must generally:

- understand the objective,
- inspect the relevant repository context,
- identify constraints,
- determine an implementation strategy,
- perform changes,
- validate the result,
- react to failures,
- revise the plan when necessary,
- determine whether the objective has actually been completed.

Modern coding agents implement these concepts in different ways.

OpenCode provides explicit Plan and Build agents. Its Plan agent is designed
for analysis without making changes, while Build provides the normal
development workflow. OpenCode also supports specialized subagents such as
General, Explore, and Scout.

OpenCode also allows agent-specific configuration such as model selection,
temperature, maximum steps, permissions, and prompts. Its documentation
describes temperature as controlling response randomness and steps as limiting
the number of agentic iterations.

Hermes provides another reference for autonomous execution, including
sequential or concurrent Tool execution, context compression, persistent
sessions, memory, and Skills. Its optional Codex runtime also demonstrates an
explicit planning Tool through `update_plan` together with sandboxed execution.


These approaches indicate that planning is not merely a prompt placed before
code generation.

Planning is part of the agent's engineering control loop.

-------------------------------------------------------------------------------

# 3. Purpose

This research SHALL determine:

- what planning means within ClaireCoder,
- when planning should occur,
- how deeply different tasks should be planned,
- how planning and execution should interact,
- how plans should be represented,
- how plans should evolve,
- how validation should affect planning,
- how failures should trigger recovery or replanning,
- how autonomous execution should be controlled,
- how different Modes should influence planning,
- how model capabilities should influence planning,
- how ClaireCoder can provide strong planning without requiring multiple
  expensive models.

-------------------------------------------------------------------------------

# 4. Scope

## In Scope

- Planning.
- Task decomposition.
- Goal analysis.
- Context gathering.
- Plan generation.
- Plan refinement.
- Execution.
- Validation.
- Review.
- Recovery.
- Replanning.
- Completion evaluation.
- Planning depth.
- Planning strategies.
- Modes.
- Subagents.
- Model participation.
- Planning temperature.
- Agentic iteration limits.
- User approval.
- Autonomous execution.
- Workflow state.
- Failure handling.
- Parallel work.
- Sequential work.
- Plan persistence.

## Out of Scope

- Final Workflow implementation.
- Final Planning Engine implementation.
- Final Tool implementation.
- Final Model Gateway implementation.
- Final Skill implementation.
- Final CLI/TUI implementation.
- Final autonomy permission model.
- Model training or fine-tuning.

-------------------------------------------------------------------------------

# 5. Research Questions

### RQ-049

What should constitute a plan in ClaireCoder?

---

### RQ-050

When should ClaireCoder plan before execution?

---

### RQ-051

When should ClaireCoder execute immediately without producing a detailed
plan?

---

### RQ-052

How should planning depth adapt to task complexity?

---

### RQ-053

How should ClaireCoder distinguish simple, moderate, and complex engineering
tasks?

---

### RQ-054

How should a plan represent dependencies between tasks?

---

### RQ-055

How should plans change when execution produces unexpected information?

---

### RQ-056

How should Tool results influence subsequent planning?

---

### RQ-057

How should test failures influence the workflow?

---

### RQ-058

How should ClaireCoder detect that its current plan is no longer valid?

---

### RQ-059

When should ClaireCoder replan instead of continuing execution?

---

### RQ-060

How should ClaireCoder determine whether an engineering objective has been
completed?

---

### RQ-061

How should user approval interact with planning and execution?

---

### RQ-062

How should planning behave when the selected model has weak reasoning or
limited context?

---

### RQ-063

How should planning behave when the selected model provides stronger
reasoning capabilities?

---

### RQ-064

How should ClaireCoder expose planning depth without forcing users to
understand internal model parameters?

---

### RQ-065

Should temperature be exposed as a planning control, or should ClaireCoder
abstract model-specific generation parameters behind higher-level planning
profiles?

---

### RQ-066

How should ClaireCoder handle long-running workflows that exceed a single
model context?

---

### RQ-067

How should independent tasks be executed in parallel?

---

### RQ-068

How should dependent tasks remain sequential?

---

### RQ-069

When should ClaireCoder delegate a task to a subagent?

---

### RQ-070

How should subagent results be incorporated into the main workflow?

-------------------------------------------------------------------------------

# 6. Research

## 6.1 Planning as an Engineering Control Loop

The research indicates that planning should not be treated as a single event.

A more useful conceptual model is:

Objective
    ↓
Understand
    ↓
Plan
    ↓
Execute
    ↓
Observe
    ↓
Validate
    ↓
Complete?
    ├── YES → Finish
    └── NO
          ↓
       Replan
          ↓
       Execute

This means that ClaireCoder planning SHALL remain adaptive.

A plan created before repository inspection may need to change after the
agent discovers an unexpected architecture, failing tests, missing
dependencies, or contradictory project requirements.

-------------------------------------------------------------------------------

## 6.2 Plan Mode

OpenCode provides a dedicated Plan agent that restricts modifications while
allowing analysis and planning. Users can then switch back to Build mode to
execute the resulting plan.

This establishes a useful pattern:

Plan
    ↓
Review
    ↓
Build

ClaireCoder SHALL investigate this separation.

However, ClaireCoder SHOULD NOT require every task to enter an explicit Plan
mode.

Small changes may not justify a separate planning stage.

-------------------------------------------------------------------------------

## 6.3 Adaptive Planning Depth

ClaireCoder SHALL investigate planning depth as an adaptive property.

A conceptual model is:

Level 0 — Direct

Used for:

- trivial edits,
- simple questions,
- obvious one-file changes,
- straightforward commands.

Level 1 — Lightweight

Used for:

- small features,
- localized fixes,
- simple refactors,
- small configuration changes.

Level 2 — Structured

Used for:

- multi-file changes,
- debugging,
- feature implementation,
- moderate refactoring,
- dependency changes.

Level 3 — Deep

Used for:

- architectural changes,
- large features,
- migrations,
- complex debugging,
- repository-wide refactoring,
- tasks with substantial uncertainty.

These levels are research concepts, not final user-facing names.

-------------------------------------------------------------------------------

## 6.4 High Planning Versus High Verbosity

ClaireCoder SHALL distinguish planning quality from visible verbosity.

A highly capable planning system does not necessarily need to display every
internal reasoning step to the user.

The system SHOULD produce useful engineering artifacts such as:

- objective,
- assumptions,
- affected areas,
- implementation steps,
- validation strategy,
- unresolved questions.

The internal planning process SHALL remain separate from the amount of text
shown in the CLI.

-------------------------------------------------------------------------------

## 6.5 Planning Temperature

OpenCode currently exposes agent temperature configuration and documents
lower values as more focused and deterministic and higher values as more
creative and variable.

ClaireCoder SHALL investigate temperature as a provider-specific generation
parameter rather than assuming it is a universal measure of planning quality.

The architecture SHOULD instead expose higher-level concepts such as:

- planning depth,
- planning strictness,
- exploration level,
- execution aggressiveness.

The Model Gateway MAY translate these concepts into model-specific
parameters when supported.

This avoids coupling ClaireCoder's planning philosophy to the semantics of
one generation parameter.

-------------------------------------------------------------------------------

## 6.6 Agentic Iteration

OpenCode allows a configurable maximum number of agentic steps. If the limit
is reached, the agent is instructed to summarize its work and identify
remaining tasks.

This provides an important control mechanism.

ClaireCoder SHALL investigate limits based on:

- task complexity,
- autonomy level,
- model capability,
- user configuration,
- estimated cost,
- workflow state.

A fixed global iteration limit SHOULD be avoided.

-------------------------------------------------------------------------------

## 6.7 Execution and Validation

Planning without validation is insufficient for software engineering.

ClaireCoder SHOULD treat validation as part of the workflow rather than as an
optional final step.

Validation may include:

- tests,
- builds,
- linting,
- type checking,
- static analysis,
- runtime checks,
- repository state,
- expected file changes,
- user-defined acceptance criteria.

The validation result SHOULD become structured input to the workflow.

-------------------------------------------------------------------------------

## 6.8 Failure Recovery

A failed Tool execution SHALL NOT automatically mean that the entire workflow
has failed.

ClaireCoder SHALL distinguish between:

- recoverable failure,
- information-producing failure,
- configuration failure,
- permission failure,
- environmental failure,
- implementation failure,
- unrecoverable failure.

The Engineering Engine SHOULD determine whether to:

- retry,
- modify the approach,
- gather additional context,
- request user input,
- replan,
- terminate.

-------------------------------------------------------------------------------

## 6.9 Replanning

Replanning SHALL be triggered when the existing plan no longer represents
the known state of the repository or environment.

Possible triggers include:

- unexpected code structure,
- failed tests,
- missing dependency,
- changed requirements,
- Tool failure,
- contradictory project instructions,
- newly discovered architecture,
- permission restrictions,
- external information changing the approach.

ClaireCoder SHALL avoid blindly continuing a stale plan.

-------------------------------------------------------------------------------

## 6.10 Parallel Execution

Independent work MAY be executed in parallel when doing so is safe.

Potential examples include:

- researching separate files,
- inspecting unrelated modules,
- running independent analysis tasks,
- delegating independent code review tasks.

Dependent changes SHOULD remain sequential.

The workflow system SHALL understand task dependencies before allowing
parallel execution.

-------------------------------------------------------------------------------

## 6.11 Subagents

Subagents can provide specialized or parallel execution.

OpenCode currently distinguishes primary agents from subagents and provides
specialized subagents such as General, Explore, and Scout.

ClaireCoder SHALL investigate subagents as part of workflow orchestration.

Potential roles include:

- explorer,
- researcher,
- reviewer,
- debugger,
- tester,
- documentation agent,
- security auditor.

A subagent SHOULD have a bounded objective rather than becoming an
unrestricted second primary agent.

-------------------------------------------------------------------------------

## 6.12 Mode-Specific Planning

Modes SHOULD influence planning behavior.

For example:

Plan Mode:

- emphasize analysis,
- restrict modifications,
- produce a structured plan.

Build Mode:

- execute approved work,
- modify files,
- run validation.

Review Mode:

- inspect implementation,
- identify issues,
- avoid modifications unless explicitly authorized.

Research Mode:

- gather external and repository information,
- compare alternatives,
- minimize implementation.

Debug Mode:

- prioritize diagnosis,
- reproduce failures,
- gather evidence,
- make targeted corrections.

These are conceptual examples.

The final ClaireCoder Mode roster SHALL be determined in later research.

-------------------------------------------------------------------------------

## 6.13 Model Capability Awareness

Not all models provide equivalent reasoning, context length, Tool calling,
vision, structured output, or instruction-following capabilities.

ClaireCoder SHALL therefore make planning capability-aware.

The system SHOULD be able to determine whether the selected model supports
the capabilities required by a workflow.

A weaker model SHOULD still be usable for simpler workflows rather than being
automatically excluded.

-------------------------------------------------------------------------------

## 6.14 Single-Model Operation

ClaireCoder SHALL remain useful when a user has access to only one model.

The planning architecture SHALL therefore not require a dedicated expensive
"planning model" plus a separate "coding model."

Where multiple models are available, ClaireCoder MAY use different models for
different stages.

Where only one model is available, the same model SHALL be capable of
performing the workflow subject to its capabilities.

-------------------------------------------------------------------------------

## 6.15 Planning Artifacts

ClaireCoder SHALL investigate a structured plan representation.

A plan MAY contain:

- objective,
- assumptions,
- constraints,
- discovered context,
- tasks,
- dependencies,
- affected files,
- validation criteria,
- current state,
- completed work,
- failed work,
- unresolved issues.

The plan SHOULD be persistent enough to support session resumption.

-------------------------------------------------------------------------------

## 6.16 Context and Planning

Planning quality depends heavily on context quality.

ClaireCoder SHALL avoid creating plans from insufficient repository
information when the task requires repository understanding.

The planning system SHOULD therefore be able to request additional context
before committing to an implementation strategy.

This creates the conceptual relationship:

Planning
    ↕
Context
    ↕
Repository Intelligence

-------------------------------------------------------------------------------

# 7. Planning Strategy Classification

The initial research classification SHALL be:

Direct Execution:

- trivial and highly deterministic tasks.

Light Planning:

- localized changes,
- small features,
- simple fixes.

Structured Planning:

- multi-file changes,
- debugging,
- moderate features,
- refactoring.

Deep Planning:

- architecture,
- migrations,
- large features,
- complex repository changes.

Exploratory Planning:

- uncertain requirements,
- unfamiliar repositories,
- research-heavy tasks.

Review Planning:

- validation,
- audit,
- code review,
- security review.

These categories are conceptual and SHALL be refined later.

-------------------------------------------------------------------------------

# 8. Workflow State

ClaireCoder SHALL investigate explicit workflow state.

A conceptual state model is:

IDLE
  ↓
UNDERSTANDING
  ↓
PLANNING
  ↓
AWAITING_APPROVAL
  ↓
EXECUTING
  ↓
VALIDATING
  ├── PASS → COMPLETED
  └── FAIL
        ↓
      ANALYZING
        ↓
      REPLANNING
        ↓
      EXECUTING

The final state machine SHALL be determined during architecture design.

-------------------------------------------------------------------------------

# 9. Analysis

The research indicates that ClaireCoder should not implement planning as one
large prompt.

Planning should be an interaction between:

- the Engineering Engine,
- the selected Model,
- Context,
- Tools,
- Skills,
- Workflow state,
- Validation.

The Engineering Engine SHALL own the overall workflow state.

The Model SHALL provide reasoning and decision-making capabilities.

Tools SHALL provide observations and actions.

Skills SHALL provide specialized methodology.

Validation SHALL determine whether the current result satisfies the
objective.

This separation allows ClaireCoder to replace individual components without
redesigning the entire workflow.

-------------------------------------------------------------------------------

# 10. Recommendations

Based on the current research, ClaireCoder SHOULD:

1. Support adaptive planning depth.
2. Avoid forcing detailed planning on trivial tasks.
3. Support explicit Plan and Build behavior.
4. Support autonomous planning within execution workflows.
5. Keep planning separate from model-specific generation parameters.
6. Treat temperature as a model parameter rather than a universal planning
   quality metric.
7. Support configurable agentic iteration limits.
8. Make validation a first-class workflow stage.
9. Support recovery and replanning.
10. Preserve structured workflow state.
11. Support bounded subagents.
12. Support parallel execution for independent work.
13. Preserve sequential execution for dependent work.
14. Make planning capability-aware.
15. Allow effective operation with a single available model.
16. Allow multiple models when users have them without requiring them.
17. Persist useful planning state for session resumption.
18. Keep visible planning concise and useful.
19. Avoid exposing unnecessary internal reasoning.
20. Adapt planning behavior to the active Mode.
21. Allow Skills to influence methodology without owning workflow state.
22. Allow Tools to provide evidence and actions without owning planning.
23. Replan when the current plan becomes invalid.
24. Validate completion instead of assuming successful execution means task
    completion.

These recommendations SHALL guide subsequent architecture research but SHALL
NOT become final implementation decisions until the appropriate ADRs are
completed.

-------------------------------------------------------------------------------

# 11. Expected Outcomes

Successful completion of this research SHALL establish:

- a conceptual ClaireCoder planning model,
- adaptive planning-depth requirements,
- planning and execution boundaries,
- validation requirements,
- recovery and replanning requirements,
- subagent requirements,
- Mode-specific planning requirements,
- model capability requirements,
- planning-state requirements,
- requirements for single-model operation,
- requirements for future Workflow and Planning architecture.

-------------------------------------------------------------------------------

# 12. Risks

Potential risks include:

- over-planning simple tasks,
- under-planning complex tasks,
- stale plans,
- infinite replanning loops,
- excessive model calls,
- excessive Tool execution,
- unnecessary token consumption,
- premature completion,
- over-reliance on one model's reasoning quality,
- excessive subagent delegation,
- unsafe parallel execution,
- exposing unnecessary internal reasoning,
- coupling planning to provider-specific parameters.

ClaireCoder SHALL prioritize reliable engineering outcomes over maximum
planning complexity.

-------------------------------------------------------------------------------

# 13. Success Criteria

This research succeeds when:

- adaptive planning depth is established conceptually,
- planning and execution responsibilities are separated,
- validation is part of the workflow model,
- failure recovery and replanning are established,
- subagent orchestration is defined conceptually,
- model independence is preserved,
- single-model operation remains viable,
- Mode-specific planning is established,
- planning state can support future Engineering Sessions,
- the architecture can proceed to ADR without repeating the research.

-------------------------------------------------------------------------------

# 14. Future Work

The next research document SHALL be:

CC-RES-005 — Model Gateway & Provider Research

It SHALL investigate:

- OpenAI,
- Anthropic,
- Google Gemini,
- OpenRouter,
- DeepSeek,
- Groq,
- local Ollama models,
- LM Studio,
- vLLM,
- OpenAI-compatible endpoints,
- model routing,
- authentication,
- model capability detection,
- context limits,
- tool calling,
- structured output,
- vision,
- reasoning capabilities,
- streaming,
- fallbacks,
- provider-specific parameters,
- single-model operation,
- multi-model profiles.

The research SHALL determine how ClaireCoder can provide strong planning and
execution behavior without requiring users to subscribe to multiple premium
model providers.

-------------------------------------------------------------------------------

# 15. AI Instructions

When continuing ClaireCoder Workflow and Planning research:

1. Treat planning as an engineering control loop.
2. Preserve separation between Planning, Context, Tools, Skills, Models, and
   Workflow state.
3. Adapt planning depth to task complexity.
4. Avoid unnecessary planning for trivial tasks.
5. Validate before declaring completion.
6. Replan when the current plan becomes invalid.
7. Preserve user control over autonomous execution.
8. Support single-model operation.
9. Do not assume multiple premium models are available.
10. Treat temperature as a provider/model parameter rather than a universal
    measure of intelligence.
11. Prefer high-quality planning behavior over visible reasoning verbosity.
12. Bound subagent responsibilities.
13. Do not allow parallel execution to bypass task dependencies.
14. Preserve structured workflow state.
15. Avoid infinite execution or replanning loops.
16. Do not finalize implementation details before the appropriate ADR.
17. Preserve ClaireCoder's model and provider independence.
18. Preserve architectural simplicity.

###############################################################################

END OF CC-RES-004

###############################################################################