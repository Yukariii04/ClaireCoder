###############################################################################
#
#                           THE CLAIRE PROJECT
#
#                         Research Document
#
# Document Number : CC-RES-008
# Title           : Permissions, Autonomy & Security Research
# Version         : 1.0.0
# Status          : Final
#
###############################################################################

# 1. Executive Summary

This document researches the Permissions, Autonomy, and Security architecture
required by ClaireCoder.

ClaireCoder is intended to operate as a capable coding agent with access to
the filesystem, terminal, Git, repository information, external services,
Skills, MCP servers, and potentially autonomous execution.

These capabilities provide significant power but also introduce significant
risk.

The objective of this research is to determine how ClaireCoder SHALL control
what the agent is allowed to do, when approval is required, how trusted and
untrusted extensions are handled, and how autonomous execution can remain
useful without becoming unnecessarily restrictive.

The research covers:

- Tool permissions,
- filesystem permissions,
- terminal permissions,
- network permissions,
- Git permissions,
- Skill permissions,
- MCP permissions,
- approval scopes,
- autonomy levels,
- destructive operations,
- third-party extensions,
- sandboxing,
- worktrees,
- credentials,
- secrets,
- command restrictions,
- interruption,
- recovery.

A central principle established by this research is:

ClaireCoder SHOULD maximize useful autonomy while preserving explicit
boundaries around high-risk operations.

Permissions SHALL therefore be treated as a core architectural system rather
than as UI-only confirmation prompts.

-------------------------------------------------------------------------------

# 2. Background

A coding agent differs from a conventional conversational assistant because
it can directly affect the user's environment.

For example, ClaireCoder may eventually be able to:

- create files,
- modify source code,
- delete files,
- execute shell commands,
- install packages,
- modify Git state,
- access the network,
- interact with external services,
- invoke MCP Tools,
- execute third-party Skill scripts.

Not every operation has the same risk.

Reading a source file is generally different from deleting an entire
directory.

Running a unit test is different from executing an arbitrary network command.

Creating a local file is different from modifying credentials.

A useful permission architecture must therefore operate at a finer level than
a simple:

ALLOW EVERYTHING
or
DENY EVERYTHING

model.

Modern agent systems demonstrate several approaches.

OpenCode provides configurable permissions for actions such as file editing,
shell execution, web access, and external directories. It supports rules such
as allow, deny, and ask, together with wildcard matching. This provides a
useful reference for policy-driven permissions.

Hermes provides approval behavior for dangerous commands and an explicit YOLO
mode that bypasses approval prompts. Its interface visibly indicates when
YOLO mode is active.

These approaches demonstrate that autonomy and permissions should be
configurable rather than permanently fixed.

ClaireCoder SHALL research a similar capability while preserving its own
architecture.

-------------------------------------------------------------------------------

# 3. Purpose

This research SHALL determine:

- what operations require permissions,
- how permissions should be represented,
- how approval should work,
- what autonomy levels should exist,
- how permission scopes should operate,
- how dangerous commands should be handled,
- how third-party Skills should be trusted,
- how MCP permissions should operate,
- how credentials should be protected,
- how sandboxing should be used,
- how worktrees can reduce repository risk,
- how permissions interact with Modes,
- how permissions interact with Tools,
- how permissions interact with Skills,
- how permissions interact with autonomous execution.

-------------------------------------------------------------------------------

# 4. Scope

## In Scope

- Tool permissions.
- Filesystem permissions.
- Terminal permissions.
- Git permissions.
- Network permissions.
- Browser permissions.
- MCP permissions.
- Skill permissions.
- External Tool permissions.
- Approval policies.
- Autonomy levels.
- Destructive operations.
- Command restrictions.
- Path restrictions.
- Workspace restrictions.
- Credential handling.
- Secret handling.
- Sandboxing.
- Worktrees.
- Temporary environments.
- Permission inheritance.
- Permission precedence.
- Permission auditing.
- User approval.
- Session-level permissions.
- Mode-level permissions.
- Tool-level permissions.
- Recovery.

## Out of Scope

- Final permission implementation.
- Final sandbox implementation.
- Final security infrastructure.
- Operating-system-specific security implementation.
- Enterprise security architecture.
- Full remote execution infrastructure.
- Final authentication system.
- Final credential manager implementation.

-------------------------------------------------------------------------------

# 5. Research Questions

### RQ-135

What operations require explicit permission?

---

### RQ-136

Which operations can safely execute automatically?

---

### RQ-137

How should filesystem permissions be represented?

---

### RQ-138

How should terminal permissions be represented?

---

### RQ-139

How should destructive shell commands be identified?

---

### RQ-140

How should Git operations be classified by risk?

---

### RQ-141

How should network access be controlled?

---

### RQ-142

How should MCP Tool permissions be controlled?

---

### RQ-143

How should third-party Skills receive Tool access?

---

### RQ-144

How should permissions interact with Modes?

---

### RQ-145

How should permissions interact with autonomy levels?

---

### RQ-146

How should a user grant permission for one action versus an entire session?

---

### RQ-147

Should permissions support path-specific and command-specific rules?

---

### RQ-148

How should permission conflicts be resolved?

---

### RQ-149

How should permission policies be persisted?

---

### RQ-150

How should permission changes be displayed to the user?

---

### RQ-151

How should credentials and secrets be protected from model context?

---

### RQ-152

How should ClaireCoder prevent Skills from silently obtaining credentials?

---

### RQ-153

How should ClaireCoder handle untrusted repositories?

---

### RQ-154

How should sandboxing interact with normal development workflows?

---

### RQ-155

How should worktrees reduce repository risk?

---

### RQ-156

How should ClaireCoder recover from interrupted or partially completed
operations?

---

# 6. Research

## 6.1 Permission Model

ClaireCoder SHALL investigate a policy-based permission system.

A conceptual model is:

Operation
    ↓
Permission Policy
    ↓
ALLOW / ASK / DENY

This is preferable to hardcoding approval behavior independently inside every
Tool.

The Tool reports what it wants to do.

The Permission Engine determines whether the action is allowed.

-------------------------------------------------------------------------------

## 6.2 Permission Scope

Permissions SHOULD be capable of operating at multiple scopes.

Potential scopes include:

- operation,
- Tool,
- path,
- command,
- Skill,
- Mode,
- session,
- project,
- global configuration.

For example:

A user may allow:

- reading the repository,

while requiring approval for:

- modifying files.

The user may allow:

- running tests,

while requiring approval for:

- installing packages.

-------------------------------------------------------------------------------

## 6.3 Allow / Ask / Deny

The core policy model SHOULD investigate three fundamental states.

ALLOW

The action may execute automatically.

ASK

The user must approve the action.

DENY

The action cannot execute.

This simple model can represent many permission policies without requiring
large numbers of custom states.

-------------------------------------------------------------------------------

## 6.4 Permission Precedence

Permission conflicts require deterministic resolution.

ClaireCoder SHALL investigate a precedence model such as:

Explicit Deny
    ↓
Explicit Allow
    ↓
Explicit Ask
    ↓
Default Policy

However, the exact precedence SHALL be determined during ADR work.

The most important requirement is that permission behavior be deterministic
and understandable.

-------------------------------------------------------------------------------

## 6.5 Filesystem Permissions

Filesystem operations SHOULD distinguish:

Read:

- read file,
- list directory,
- inspect metadata.

Write:

- create,
- modify,
- rename.

Destructive:

- delete,
- recursive delete,
- overwrite,
- move outside workspace.

ClaireCoder SHOULD support workspace boundaries.

By default, the agent SHOULD operate within the selected project workspace.

Access outside the workspace SHOULD require explicit authorization.

-------------------------------------------------------------------------------

## 6.6 Terminal Permissions

Terminal execution is inherently broad.

ClaireCoder SHALL investigate command-level permission policies.

Potential categories include:

Low Risk:

- tests,
- formatters,
- linters,
- read-only Git commands.

Moderate Risk:

- package installation,
- build commands,
- generated-file operations.

High Risk:

- deleting files,
- changing permissions,
- modifying system configuration,
- destructive Git commands,
- network downloads,
- arbitrary scripts.

The exact command classification SHALL remain configurable.

-------------------------------------------------------------------------------

## 6.7 Command Matching

ClaireCoder SHOULD investigate command-aware policies.

A policy MAY match:

- exact command,
- command prefix,
- executable,
- arguments,
- working directory.

This allows policies such as:

Allow:
    pytest

Ask:
    npm install

Deny:
    rm -rf /

These examples are conceptual only.

The actual policy language SHALL be determined during ADR work.

-------------------------------------------------------------------------------

## 6.8 Git Permissions

Git operations SHOULD be classified by risk.

Generally lower-risk operations may include:

- status,
- diff,
- log,
- branch inspection.

Potentially higher-risk operations include:

- reset,
- restore,
- clean,
- checkout with destructive changes,
- rebase,
- merge,
- force push,
- branch deletion.

ClaireCoder SHALL not assume that all Git operations are equally safe.

-------------------------------------------------------------------------------

## 6.9 Network Permissions

Network access SHALL be treated separately from filesystem and terminal
permissions.

Potential network capabilities include:

- web search,
- web retrieval,
- package downloads,
- Git remotes,
- API requests,
- MCP servers,
- browser access.

ClaireCoder SHOULD investigate separate network policies.

A Skill requiring network access SHOULD declare the requirement.

-------------------------------------------------------------------------------

## 6.10 MCP Permissions

MCP servers may expose powerful external capabilities.

ClaireCoder SHALL therefore treat MCP permissions independently.

Potential controls include:

- server trust,
- Tool trust,
- filesystem scope,
- network scope,
- credentials,
- Tool-specific permissions.

Installing an MCP server SHOULD NOT automatically grant unlimited access.

-------------------------------------------------------------------------------

## 6.11 Skill Permissions

Skills should not automatically inherit unrestricted permissions.

A Skill MAY request access to:

- specific Tools,
- specific paths,
- network,
- external commands.

The Permission Engine SHALL determine whether those capabilities are
available.

Third-party Skills SHALL remain subject to the same permission system as
built-in Skills.

-------------------------------------------------------------------------------

## 6.12 Third-party Trust

ClaireCoder SHALL distinguish between:

Built-in Skills

Official ClaireCoder-controlled content.

Trusted Community Skills

Reviewed or explicitly trusted external content.

Unverified Third-party Skills

External content that has not been reviewed.

The system SHOULD communicate the source and trust state to the user.

Trust SHALL not automatically imply unrestricted Tool access.

-------------------------------------------------------------------------------

## 6.13 Autonomy Levels

ClaireCoder SHOULD investigate configurable autonomy levels.

A conceptual model is:

ASSISTED

The user approves many actions.

BALANCED

Routine actions are automatic while higher-risk actions require approval.

AUTONOMOUS

Most operations inside configured boundaries execute automatically.

UNRESTRICTED / YOLO

Approval prompts are bypassed within the capabilities granted by the
environment.

The final terminology SHALL be determined later.

-------------------------------------------------------------------------------

## 6.14 YOLO Mode

YOLO-style execution can be useful for experienced users and controlled
environments.

However, it SHALL be explicit.

When enabled, ClaireCoder SHOULD clearly indicate:

- YOLO state,
- affected permission scope,
- active workspace,
- active model,
- active Mode.

The user SHALL never need to guess whether approval protection has been
disabled.

-------------------------------------------------------------------------------

## 6.15 Mode Permissions

Modes MAY provide different default permission policies.

For example:

PLAN

Prefer read-only access.

REVIEW

Prefer read-only access with optional targeted commands.

BUILD

Allow normal editing and testing.

DEBUG

Allow diagnostic execution and targeted modifications.

RESEARCH

Allow web and repository retrieval with minimal modification.

These are conceptual examples.

Mode-specific policies SHALL remain subordinate to global security boundaries.

-------------------------------------------------------------------------------

## 6.16 Approval Scope

When the user approves an operation, ClaireCoder SHOULD make the scope clear.

Potential scopes:

ALLOW ONCE

Allow only this operation.

ALLOW FOR TOOL

Allow this Tool during the current context.

ALLOW FOR SESSION

Allow similar operations during this session.

ALLOW FOR PROJECT

Persist the rule for this project.

ALLOW ALWAYS

Persist globally.

The final scope model SHALL be kept small enough to remain understandable.

-------------------------------------------------------------------------------

## 6.17 Approval Context

An approval request SHOULD contain:

- Tool,
- operation,
- target,
- command or action,
- risk explanation,
- affected scope,
- available approval choices.

Example:

Tool:
    Terminal

Action:
    npm install package-name

Workspace:
    project/

Risk:
    Downloads and installs an external package.

The interface SHOULD allow the user to make a decision without reading
internal agent reasoning.

-------------------------------------------------------------------------------

## 6.18 Secrets

Secrets SHALL be treated as a special security category.

ClaireCoder SHALL investigate protection for:

- API keys,
- environment variables,
- access tokens,
- SSH keys,
- cloud credentials,
- Git credentials,
- MCP credentials.

Secrets SHOULD NOT be unnecessarily inserted into model context.

The Model Gateway SHALL obtain credentials through secure configuration
mechanisms rather than requiring the model to know raw credentials.

-------------------------------------------------------------------------------

## 6.19 Environment Variables

Environment variables can contain secrets and sensitive configuration.

Terminal execution SHOULD therefore consider environment exposure.

ClaireCoder SHOULD investigate:

- environment allowlists,
- secret redaction,
- protected variables,
- environment inheritance,
- command-output redaction.

-------------------------------------------------------------------------------

## 6.20 Untrusted Repositories

A repository may contain malicious or misleading instructions.

Examples include:

- malicious project instructions,
- scripts,
- package hooks,
- generated commands,
- prompt-injection content,
- untrusted Skill files.

ClaireCoder SHALL distinguish repository content from trusted agent policy.

Repository instructions SHALL not automatically override:

- system policy,
- ClaireCoder security policy,
- user permissions.

-------------------------------------------------------------------------------

## 6.21 Prompt Injection

Prompt injection SHALL be treated as a security concern for:

- repository files,
- documentation,
- web pages,
- issues,
- Skills,
- MCP results,
- Tool output.

ClaireCoder SHOULD preserve the distinction between:

Instruction source
and
Data source.

External content SHALL not automatically gain authority over the agent.

-------------------------------------------------------------------------------

## 6.22 Sandboxing

Sandboxing MAY reduce the impact of unsafe execution.

Potential sandbox boundaries include:

- filesystem,
- network,
- process,
- environment,
- working directory.

ClaireCoder SHALL investigate sandbox support without making heavyweight
sandbox infrastructure mandatory for every installation.

Local development environments often require legitimate access to compilers,
package managers, Git, browsers, and other system resources.

-------------------------------------------------------------------------------

## 6.23 Worktrees

Git worktrees MAY provide an additional safety mechanism for autonomous
development.

A workflow MAY operate in a dedicated worktree rather than directly modifying
the primary working directory.

Potential advantages include:

- isolation,
- easier review,
- safer experimentation,
- parallel development,
- simpler rollback.

ClaireCoder SHALL investigate worktrees as an optional execution strategy.

-------------------------------------------------------------------------------

## 6.24 Temporary Environments

Some tasks may benefit from temporary execution environments.

Potential use cases include:

- dependency experimentation,
- build validation,
- untrusted code,
- generated projects,
- tests requiring isolation.

ClaireCoder SHOULD treat this as an optional advanced capability rather than
a mandatory V1 requirement.

-------------------------------------------------------------------------------

## 6.25 Auditing

ClaireCoder SHOULD maintain an execution record containing relevant events.

Potential records include:

- Tool invoked,
- permission requested,
- permission decision,
- command executed,
- files changed,
- validation executed,
- Skill activated,
- MCP Tool invoked,
- model switched.

The audit record SHOULD be useful for:

- debugging,
- transparency,
- session recovery,
- security investigation.

It SHOULD not unnecessarily record secrets.

-------------------------------------------------------------------------------

## 6.26 Interruption and Recovery

An interrupted operation can leave partial changes.

ClaireCoder SHALL investigate recovery mechanisms such as:

- preserving Git state,
- recording changed files,
- saving workflow state,
- reporting incomplete operations,
- allowing rollback where possible.

The agent SHOULD clearly communicate when an operation may have partially
completed.

-------------------------------------------------------------------------------

# 7. Security Classification

The initial conceptual classification SHALL be:

Low Risk:

- repository reading,
- search,
- Git status,
- Git diff,
- static analysis,
- tests.

Moderate Risk:

- file modification,
- package installation,
- build execution,
- network retrieval,
- branch changes.

High Risk:

- destructive file operations,
- destructive Git operations,
- credential access,
- system modification,
- arbitrary external execution,
- unrestricted network access.

Critical:

- operations affecting credentials,
- destructive operations outside the workspace,
- unrestricted remote/system control.

This classification is provisional.

-------------------------------------------------------------------------------

# 8. Analysis

The research establishes that permissions cannot be implemented solely inside
the UI.

The architecture should be:

User / Policy
     ↓
Permission Engine
     ↓
Tool Request
     ↓
ALLOW / ASK / DENY
     ↓
Tool Execution
     ↓
Audit / Session State

This allows every execution path to use the same security model.

A command shortcut, Skill, MCP Tool, subagent, or Workflow SHALL NOT bypass
the Permission Engine.

The same principle applies to autonomy.

Autonomy changes how frequently the user is asked.

It does not remove the underlying security architecture.

-------------------------------------------------------------------------------

# 9. Recommendations

Based on the current research, ClaireCoder SHOULD:

1. Build a centralized Permission Engine.
2. Use ALLOW / ASK / DENY as the fundamental policy states.
3. Support scoped permissions.
4. Keep workspace boundaries by default.
5. Classify filesystem operations by risk.
6. Classify terminal operations by risk.
7. Classify Git operations by risk.
8. Provide network permission controls.
9. Provide MCP permission controls.
10. Apply permissions equally to third-party Skills.
11. Make autonomy levels explicit.
12. Make YOLO-style operation clearly visible.
13. Support approval scopes.
14. Protect credentials from model context.
15. Support secret redaction.
16. Treat repository and web content as potentially untrusted data.
17. Protect trusted policy from prompt injection.
18. Investigate sandboxing.
19. Investigate Git worktrees.
20. Preserve execution audit information.
21. Preserve recovery information after interrupted operations.
22. Keep security boundaries independent of the selected model.
23. Keep security boundaries independent of Skills.
24. Keep security boundaries independent of MCP.
25. Do not make advanced sandbox infrastructure mandatory for V1.
26. Prefer simple, understandable security controls over a huge policy language.

These recommendations SHALL guide architecture decisions but SHALL NOT become
final implementation requirements until the appropriate ADRs are completed.

-------------------------------------------------------------------------------

# 10. Expected Outcomes

Successful completion of this research SHALL establish:

- Permission Engine requirements,
- permission scopes,
- Tool permission requirements,
- filesystem permission requirements,
- terminal permission requirements,
- Git permission requirements,
- network permission requirements,
- Skill permission requirements,
- MCP permission requirements,
- autonomy requirements,
- approval requirements,
- secret-handling requirements,
- untrusted-content requirements,
- sandbox requirements,
- worktree requirements,
- auditing requirements,
- recovery requirements.

-------------------------------------------------------------------------------

# 11. Risks

Potential risks include:

- overly restrictive permissions,
- unsafe autonomous execution,
- permission bypass through Skills,
- permission bypass through MCP,
- malicious repository instructions,
- prompt injection,
- credential exposure,
- destructive commands,
- unclear approval scopes,
- excessive policy complexity,
- false security assumptions around sandboxing,
- incomplete recovery after interrupted operations.

ClaireCoder SHALL prioritize explicit boundaries and understandable behavior.

-------------------------------------------------------------------------------

# 12. Success Criteria

This research succeeds when:

- permissions are recognized as a centralized architectural system,
- ALLOW / ASK / DENY is established conceptually,
- permission scopes are established,
- Tool and extension permissions are covered,
- autonomy is separated from security boundaries,
- third-party content is treated as potentially untrusted,
- credential protection requirements are established,
- sandboxing and worktrees are evaluated,
- audit and recovery requirements are established,
- the architecture can proceed to ADR without repeating the security
  research.

-------------------------------------------------------------------------------

# 13. V1 Research Conclusion

CC-RES-008 completes the planned initial ClaireCoder V1 Research phase.

The eight research documents collectively establish the research foundation
for:

CC-RES-001
ClaireCoder Product / Ecosystem Research

CC-RES-002
Tool Architecture Research

CC-RES-003
Skill Architecture Research

CC-RES-004
Workflow & Planning Research

CC-RES-005
Model Gateway & Provider Research

CC-RES-006
Context, Memory & Engineering Session Research

CC-RES-007
Modes, Commands & User Interaction Research

CC-RES-008
Permissions, Autonomy & Security Research

No further RES documents are required for the currently defined V1 research
scope unless architecture review identifies a genuinely missing research
area.

The next phase SHALL therefore move from Research into Architecture Decision
Records.

-------------------------------------------------------------------------------

# 14. Next Phase

The next phase SHALL be:

ADR

The ADR phase SHALL convert the conclusions of the RES documents into explicit
architectural decisions.

The ADR phase SHOULD cover at minimum:

- core ClaireCoder architecture,
- Engineering Engine,
- Model Gateway,
- Tool architecture,
- Skill architecture,
- Workflow architecture,
- Context architecture,
- Engineering Session architecture,
- Command architecture,
- Mode architecture,
- Permission architecture,
- extension architecture,
- storage,
- configuration,
- CLI/TUI boundary.

ADR documents SHALL resolve decisions rather than repeat research.

After ADR completion, the project SHALL proceed to:

PRD

The PRD phase SHALL convert the accepted architecture into implementable
product requirements.

-------------------------------------------------------------------------------

# 15. AI Instructions

When continuing ClaireCoder after the RES phase:

1. Treat CC-RES-001 through CC-RES-008 as the research foundation.
2. Do not continue creating RES documents without identifying a genuine
   missing research area.
3. Move to ADR after the research phase.
4. ADRs SHALL make explicit architectural decisions.
5. Do not silently convert recommendations into implementation requirements.
6. Preserve unresolved decisions until the appropriate ADR.
7. Do not prematurely implement architecture during ADR.
8. Keep Skills, Tools, Models, Workflows, Context, Modes, and Permissions
   architecturally distinct.
9. Preserve single-model operation.
10. Preserve local-model support.
11. Preserve third-party Skill extensibility.
12. Preserve the three Skill acquisition paths.
13. Preserve adaptive planning.
14. Preserve context efficiency.
15. Preserve centralized permission enforcement.
16. Preserve ClaireCoder's model and provider independence.
17. Keep the implementation practical and avoid over-engineering.
18. Preserve the Claire identity without coupling the architecture to the
    visual interface.

###############################################################################

END OF CC-RES-008

###############################################################################