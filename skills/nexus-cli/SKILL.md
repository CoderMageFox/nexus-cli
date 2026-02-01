---
name: nexus-cli
description: Intelligent Task Router for Claude Code and OpenCode - Automatically route development tasks to the most suitable AI executor (Claude, Gemini, or Codex) based on task characteristics.
---

# Nexus CLI - Intelligent Task Router (v1.0.0)

Execute task: {{prompt}}

## Mandatory Constraints (MANDATORY) - Highest Priority

**The following constraints are absolute, no exceptions:**

| Constraint ID | Rule | Violation |
|---------------|------|-----------|
| `FORCE_PAL_CHECK` | **Must** check PAL MCP availability before starting, ask user about degradation if unavailable | Assigning Gemini/Codex tasks without checking PAL |
| `FORCE_SPEC_FIRST` | **Must** complete Spec flow before execution (unless using --skip-spec) | Starting task execution without generating spec documents |
| `FORCE_SPEC_USER_APPROVAL` | **Must** use AskUserQuestion to get user confirmation at each Spec phase | Proceeding to next phase without asking user |
| `FORCE_ATOMIC_TASKS` | **Must** split tasks into atomic operations (<=5 minutes) | Creating coarse-grained large tasks |
| `FORCE_BATCH_GROUPING` | **Must** group tasks into execution batches by dependencies | Executing all tasks at once without batching |
| `FORCE_BATCH_TODOWRITE` | **Must** update TodoWrite immediately after each batch completes | Waiting for all batches to complete before updating |
| `FORCE_USER_CONFIRMATION` | **Must** use AskUserQuestion to get user confirmation before execution | Selecting executor without asking user |
| `FORCE_CORRECT_TOOL` | Gemini/Codex tasks **must** use `mcp__pal__clink`, **forbidden** to use Task tool | Selecting Gemini/Codex but using Task tool |

### Violation Detection Self-Check

Before executing any operation, must self-check:
0. Have I checked PAL MCP availability? (If not, **immediately execute Phase 0**)
1. Have I completed Spec flow or did user use --skip-spec? (If not, **immediately start Spec flow**)
2. Have I called TodoWrite tool? (If not, **immediately call**)
3. Have I used AskUserQuestion to get user confirmation on executor? (If not, **forbidden to execute tasks**)
4. Are tasks split into atomic operations (<=5 minutes)?
5. Are tasks grouped into batches by dependencies?
6. Are Gemini/Codex tasks using `mcp__pal__clink`? (If using Task tool, **immediately stop and switch to clink**)

---

## Phase 0: Environment Detection and Mode Selection (Highest Priority)

**This phase must be executed before any other operations!**

### Step 0.1: Detect Ralph Orchestrator

Check if Ralph is installed:

```bash
which ralph || command -v ralph
```

**If Ralph is available**, ask user whether to enable Ralph mode:

```
AskUserQuestion({
  questions: [{
    header: "Execution Mode Selection",
    question: "Ralph Orchestrator detected. Ralph mode enables autonomous iteration until task completion. Select execution mode:",
    options: [
      {label: "Normal Mode", description: "Use standard Nexus flow with manual control at each phase"},
      {label: "Ralph Mode", description: "Enable autonomous iteration loop, AI continues until completion (higher estimated cost)"}
    ],
    multiSelect: false
  }]
})
```

**Processing logic**:
- If user selects "Ralph Mode" -> Set `RALPH_MODE = true`, jump to Ralph execution flow
- If user selects "Normal Mode" -> Set `RALPH_MODE = false`, continue to Step 0.2

### Step 0.2: Detect PAL MCP

Detect PAL MCP availability by attempting to call `mcp__pal__listmodels`:

```
Attempt call: mcp__pal__listmodels({})

If successful -> PAL MCP available, set PAL_AVAILABLE = true
If failed/timeout/tool not found -> PAL MCP unavailable, set PAL_AVAILABLE = false
```

### Step 0.3: Handle PAL Unavailable Situation

**If PAL MCP is unavailable**, **must** use AskUserQuestion to ask user:

```
AskUserQuestion({
  questions: [{
    header: "PAL MCP Detection",
    question: "PAL MCP is unavailable, cannot call Gemini/Codex CLI. Please choose how to proceed:",
    options: [
      {label: "Degrade to Claude mode", description: "All tasks handled by Claude Code subagent (full functionality but without Gemini/Codex advantages)"},
      {label: "Cancel execution", description: "Abort Nexus flow, configure PAL MCP first"}
    ],
    multiSelect: false
  }]
})
```

**Processing logic**:
- If user selects "Degrade to Claude mode" -> Set `CLAUDE_ONLY_MODE = true`, continue execution
- If user selects "Cancel execution" -> Output configuration guide and terminate

### Step 0.4: Claude-Only Mode Impact

When `CLAUDE_ONLY_MODE = true`:

| Original Executor | After Degradation | Tool Used |
|-------------------|-------------------|-----------|
| Claude | Claude | Task tool (subagent) |
| Gemini | Claude | Task tool (subagent) |
| Codex | Claude | Task tool (subagent) |
| OpenCode | Claude | Task tool (subagent) |

**Subagent type mapping**:
- Original Gemini (frontend) -> `frontend-architect` or `general-purpose`
- Original Codex (backend) -> `backend-architect` or `general-purpose`

---

## Ralph Mode Execution Flow

**When `RALPH_MODE = true`, skip standard Nexus flow and use Ralph Orchestrator.**

### Ralph Backend Auto-Selection

| Priority | Backend | Command |
|----------|---------|---------|
| 1 | Claude | `claude --dangerously-skip-permissions` |
| 2 | OpenCode | `opencode` |
| 3 | Gemini | `gemini --yolo` |
| 4 | Codex | `codex exec --full-auto` |

### Ralph Mode Execution

```bash
ralph run -p "{{prompt}}" --max-iterations 30
```

**Ralph Mode Features**:
- Autonomous iteration until task completion or limits reached
- Automatic backend selection
- Built-in safety mechanisms (iteration, cost, time limits)
- Best for well-defined tasks

---

### Tool Call Mandatory Mapping

**Absolutely forbidden to mix tools! Executor to tool mapping:**

| Executor | Must Use Tool | Forbidden Tool |
|----------|---------------|----------------|
| Claude | `Task` tool (subagent) | - |
| Gemini | `mcp__pal__clink` (`cli_name: "gemini"`) | Task tool |
| Codex | `mcp__pal__clink` (`cli_name: "codex"`) | Task tool |
| OpenCode | `Task` tool (subagent) | - |

---

## Complete Execution Flow

```
+-------------------------------------------------------------+
|              Phase 0: PAL MCP Availability Check             |
|         Available -> Normal Mode / Unavailable -> Ask        |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|                    SPEC Flow (Phase 1-3)                     |
|  Phase 1: Requirements -> requirements.md -> User confirm    |
|  Phase 2: Design Document -> design.md -> User confirm       |
|  Phase 3: Implementation Plan -> tasks.md -> User confirm    |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|                 NEXUS Execution Flow (Phase 4-5)             |
|  Phase 4: TodoWrite Init + User Confirm Executor             |
|  Phase 5: Batch Execution Loop                               |
|           - Execute tasks in parallel per batch              |
|           - Claude -> Task tool                              |
|           - Gemini/Codex -> PAL clink                        |
|           - Update TodoWrite immediately after each batch    |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|              Quality Gates (Phase 6 - Configurable)          |
|                     AI Code Review                           |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|              Completion Options (Phase 7 - Optional)         |
|         Acceptance Confirmation -> Documentation             |
+-------------------------------------------------------------+
```

---

# Part 1: SPEC Flow

## Phase 1: Requirements Gathering

**Goal**: Generate EARS format requirements document based on user's task description

### Step 1.1: Initialize Spec Directory

First, generate feature name (kebab-case) based on task description, create spec directory:

```bash
FEATURE_NAME="[feature-name-from-task-description]"
SPEC_DIR=".claude/specs/$FEATURE_NAME"
mkdir -p "$SPEC_DIR"
```

### Step 1.2: Generate requirements.md

**Must** generate initial version of requirements document based on user's rough idea.

### Step 1.3: User Confirmation

**Must** use AskUserQuestion tool to get user confirmation before proceeding to Phase 2.

---

## Phase 2: Design Document Creation

**Prerequisite**: User has explicitly approved requirements document

**Goal**: Create detailed design document based on requirements

### Step 2.1: Generate design.md

### Step 2.2: User Confirmation

**Must** use AskUserQuestion tool to get user confirmation before proceeding to Phase 3.

---

## Phase 3: Implementation Planning

**Prerequisite**: User has explicitly approved design document

**Goal**: Create atomized task list, grouped by batches

### Step 3.1: Generate tasks.md (Batch Format)

**Atomic task requirements**:
- Each task <= 5 minutes
- Each task must be independently verifiable
- Each task must have clear output files

**Executor selection reference**:
- `Claude`: Architecture design, code review, complex analysis
- `Gemini`: Frontend UI, algorithm implementation, web search
- `Codex`: Backend API, database, server-side logic
- `OpenCode`: General tasks, cross-domain work, open-source alternative

### Step 3.2: User Confirmation

**Must** use AskUserQuestion tool to get user confirmation before proceeding to Phase 4.

---

## --skip-spec Flag

If user uses `--skip-spec` flag, can skip Spec flow and go directly to Nexus execution:

```
/nexus --skip-spec Create user login feature
```

**Even if skipping Spec flow**, must still follow `FORCE_USER_CONFIRMATION` constraint!

---

# Part 2: NEXUS Execution Flow

## Phase 4: Initialization and User Confirmation

### Step 4.1: Call TodoWrite Tool

### Step 4.2: User Confirm Executor

**Must** use AskUserQuestion tool to get user confirmation.

---

## Phase 5: Batch Execution Loop (Core)

**This is the core improvement of v4.0.0: Batch execution + Immediate TodoWrite updates**

### Execution Flow

```python
# Pseudocode: Batch execution loop
for batch in batches:
    # 1. Mark batch start
    update_todowrite(batch, "in_progress")

    # 2. Execute all tasks in batch in parallel
    results = parallel_execute(batch.tasks)
    # - Claude tasks -> Task tool
    # - Gemini/Codex tasks -> PAL MCP clink

    # 3. Wait for batch completion
    wait_for_completion(results)

    # 4. Immediately update TodoWrite
    update_todowrite(batch, "completed")

    # 5. Verify batch completion criteria
    verify_batch_criteria(batch)
```

### PAL MCP clink Call Format

**Gemini task**:
```
mcp__pal__clink({
  "prompt": "Task detailed description...",
  "cli_name": "gemini"
})
```

**Codex task**:
```
mcp__pal__clink({
  "prompt": "Task detailed description...",
  "cli_name": "codex"
})
```

---

## Phase 6: Quality Gates

After all batches complete (or based on policy configuration), run quality gate checks.

### Quality Gate Policies

Based on `.nexus-config.yaml` `quality_gates.policy` configuration:

| Policy | Description | Use Case |
|--------|-------------|----------|
| `per_batch` | Execute after each batch | Large projects, need early problem detection |
| `on_complete` | Execute after all batches (default) | Small/medium projects, reduce interruptions |
| `manual` | Manual trigger only | Fast iteration, user controls |

### Step 6.1: Ask Whether to Run Quality Gates

**Must** use AskUserQuestion tool to ask user.

### Step 6.2: AI Code Review (Review Gate)

If user chooses to run code review, use PAL MCP for intelligent review.

---

## Phase 7: Completion Options (Optional)

After quality gates pass, **separately ask** user if they need the following services:

### Step 7.1: Acceptance Confirmation

### Step 7.2: Documentation Generation

---

## CLI Routing Decision

Automatically select optimal executor based on AI analysis:

**Claude** (Architecture/Analysis priority):
- Architecture design and system planning
- Deep code analysis and review
- Security vulnerability analysis
- Complex reasoning and decision making

**Gemini CLI** (Frontend/Algorithm priority):
- React, Vue, Angular components
- UI/UX implementation
- Algorithms and data structures
- Frontend performance optimization
- Web search and real-time information

**Codex CLI** (Backend/Database priority):
- REST API, GraphQL implementation
- Database schema design
- Backend service logic
- Third-party service integration

**OpenCode** (General/Open-source priority):
- General code generation and modification
- Cross-domain tasks
- Open-source project contributions
- Claude Code open-source alternative

---

## Execution Principles

- **PAL Check Mandatory**: Must check PAL MCP availability first, ask about degradation if unavailable
- **Spec Flow Mandatory**: Must complete Spec flow first (unless --skip-spec)
- **User Confirmation Mandatory**: Each Spec phase and executor selection needs user confirmation
- **Atomic Tasks Mandatory**: Each task must be <= 5 minutes
- **Batch Execution Mandatory**: Group by dependencies, update TodoWrite immediately after batch completion
- **Quality Gates Configurable**: Run quality checks based on policy configuration, ask user by default
- **Parallel Priority**: Execute independent tasks in batch in parallel
- **Result Transparency**: Clearly explain routing decision process
- **Immediate Feedback**: User can see real-time progress
- **Graceful Degradation**: Automatically switch to Claude-Only mode when PAL unavailable

---

**Now start executing the task. Strictly follow mandatory constraints: First check PAL MCP availability (Phase 0), then complete Spec flow, use atomized batch execution for immediate TodoWrite updates, finally run quality gate checks.**
