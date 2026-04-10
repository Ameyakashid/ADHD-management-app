## Links
- Read: `_build/index.md`, `_build/plan.md`, `_build/code-rules.md`, `_build/tasks/05-scheduling/spec.md`, `_build/tasks/02-personality/gate-report.md`, `_build/tasks/04-memory/sub-03/04-03x.md`, `_build/tasks/03-task-crud/sub-03/03-03x.md`, `task_store.py`, `memory_store.py`, `state_detection.py`, `state_response_integration.py`, `memory_context.py`, `workspace/SOUL.md`, `workspace/HEARTBEAT.md`, `workspace/USER.md`, `workspace/config.json.template`
- Feeds: Task 05 research/implement/verify agents, orchestrator subtask planning
- Tag: `scheduling-readiness`

## Task 05 Readiness Index

### Project State Summary

Tasks 01-04 complete. 328 tests collected (325 passing, 3 collection errors from nanobot-ai not being installed locally — expected). Gate reports exist for tasks 01 (CAUTION) and 02 (GO). Tasks 03 and 04 lack gate reports but their verify/index reports show no blocking issues.

### Upstream API Surface for Task 05

Task 05 depends on tasks 02, 03, and 04. Here is the complete interface catalog.

#### From Task 02 — State Detection (`state_detection.py`, `state_response_integration.py`)

| Export | Signature | Purpose |
|---|---|---|
| `StateName` | `Literal["baseline","focus","hyperfocus","avoidance","overwhelm","rsd"]` | Type for all 6 cognitive states |
| `ALL_STATES` | `frozenset[str]` | Set of valid state names |
| `StateConfig` | Pydantic model | Loaded from `workspace/states.yaml` — transitions, response styles |
| `detect_state` | `(message, config, llm_callable, previous_state) -> DetectionResult` | LLM-based state classification with Markov transition enforcement |
| `DetectionResult` | Pydantic model | Fields: `state: StateName`, `confidence: float`, `raw_response: str` |
| `LLMCallable` | `Protocol` | `async (prompt: str) -> str` — abstraction over LLM provider |
| `StateResponseHook` | Class | `before_iteration(context)` injects `[Current cognitive state: X]` into system prompt |
| `STATE_INDICATOR_PREFIX` | `str` | `"[Current cognitive state: "` — for parsing current state from prompt |

**Key for Task 05**: Scheduling needs to read the current cognitive state to defer/adjust check-ins. Two approaches: (1) parse `STATE_INDICATOR_PREFIX` from system prompt after `StateResponseHook` runs, or (2) call `detect_state` directly. Option 1 avoids a duplicate LLM call and uses the already-detected state.

#### From Task 03 — Task Store (`task_store.py`)

| Export | Signature | Purpose |
|---|---|---|
| `Task` | Pydantic model | Fields: `id, title, description, status, priority, created_at, updated_at, due_date, tags` |
| `TaskStatus` | `Literal["pending","in_progress","done"]` | |
| `TaskPriority` | `Literal["low","medium","high"]` | |
| `TaskUpdate` | Pydantic model | Partial update fields (exclude_unset semantics) |
| `TaskStore(storage_path)` | Class | JSON-persisted CRUD with atomic writes |
| `.create_task(title, priority, description, due_date, tags)` | `-> Task` | |
| `.get_task(task_id)` | `-> Task` | Raises `KeyError` on miss |
| `.list_tasks()` | `-> list[Task]` | All tasks |
| `.list_tasks_by_status(status)` | `-> list[Task]` | Filtered by status |
| `.update_task(task_id, updates)` | `-> Task` | Partial update |
| `.mark_complete(task_id)` | `-> Task` | Sets status="done" |
| `.delete_task(task_id)` | `-> Task` | Raises `KeyError` on miss |
| `.reload()` | `-> None` | Re-read from disk |

**Key for Task 05**: Morning plan check-in needs `list_tasks_by_status("pending")` to show priorities. Evening review needs `list_tasks_by_status("done")` filtered by today's `updated_at`. The `due_date` field enables deadline-aware scheduling.

#### From Task 04 — Memory Store (`memory_store.py`, `memory_context.py`)

| Export | Signature | Purpose |
|---|---|---|
| `MemoryEntry` | Pydantic model | Fields: `id, category, content, created_at, resolved_at, metadata` |
| `MemoryCategory` | `Literal["commitment","deadline","blocker","energy_state","context_switch"]` | |
| `MemoryEntryStore(storage_path)` | Class | JSON-persisted CRUD with soft-delete |
| `.create_entry(category, content, metadata)` | `-> MemoryEntry` | |
| `.list_active_entries()` | `-> list[MemoryEntry]` | Unresolved entries |
| `.list_entries_by_category(category)` | `-> list[MemoryEntry]` | Active entries in category |
| `.resolve_entry(entry_id)` | `-> MemoryEntry` | Soft-delete |
| `MemoryContextHook(store, max_entries)` | Class | Injects active memories into system prompt |

**Key for Task 05**: The `deadline` category holds time-sensitive items not captured as task `due_date`. The `energy_state` category supplements automatic state detection with user-reported energy levels. Scheduling should query both `deadline` entries and `Task.due_date` when deciding what's urgent.

### Nanobot-ai Scheduling Capabilities

#### HEARTBEAT.md (Built-in)

Nanobot-ai reads `workspace/HEARTBEAT.md` on a configurable interval (default 30min per the stub). The current stub defines:
- Morning check-in at 08:00
- Evening review at 20:00

**Limitation**: HEARTBEAT.md is declarative — it tells the bot what to do but has no execution engine. Nanobot-ai's heartbeat loop reads it and generates a message to the user when the time matches. This is cron-like, not state-adaptive.

#### Config Scheduling

`config.json.template` shows:
- `dream.intervalH: 4` — Dream cycle (memory consolidation) runs every 4 hours
- `timezone: "America/New_York"` — Timezone-aware scheduling possible
- No explicit cron fields in the config template

#### Gap: State-Aware Scheduling

HEARTBEAT.md is static. Task 05 requires scheduling that adapts to cognitive state:
- Defer check-ins during hyperfocus
- Increase check-in frequency during avoidance
- Reduce scope during overwhelm
- Suppress task mentions during RSD

This requires a **scheduling layer between HEARTBEAT.md and the hooks** — one that reads the current state before deciding whether to execute a scheduled check-in.

### Existing Hook Pattern

Both `StateResponseHook` and `MemoryContextHook` implement the same pattern:
- `HookContext` protocol with `messages: list[dict[str, str]]`
- `async before_iteration(context)` modifying `messages[0]`
- Error handling: try/except with logging, never crash

Task 05 can follow this pattern for a `SchedulingHook` but the trigger is different — it needs to run on a timer, not on each incoming message. This is the heartbeat mechanism.

### Outstanding Issues (Pre-Task-05)

| # | Severity | Source | Issue | Impact on Task 05 |
|---|---|---|---|---|
| 1 | MEDIUM | 02-02v | `normalize_llm_response` substring match "focus"/"hyperfocus" ordering | State misclassification could cause wrong scheduling behavior. Fix before task 05. |
| 2 | LOW | 04-03v | `HookContext` protocol duplicated in `memory_context.py` and `state_response_integration.py` | Task 05 adds a third hook — extract `HookContext` to shared module or accept duplication. |
| 3 | LOW | 03-03x | Tools not wired into nanobot startup (`register_task_tools()` call deferred) | Scheduling needs task tools registered to query task store. Must be resolved during task 05 integration. |
| 4 | LOW | 01 gate | `code-rules.md` contradictory default parameter rule (lines 12 vs 58) | May confuse task 05 agents. Fix: change line 12 to "No mutable default arguments." |
| 5 | INFO | 04-03v | Double sort in `MemoryContextHook._inject` + `format_memory_entries` | No impact. |

**Recommendation**: Fix issue #1 (substring ordering in `state_detection.py`) before starting task 05. Issues #2-4 can be addressed during task 05 implementation.

### Proposed Subtask Decomposition

Based on the spec, user constraints, and available interfaces, task 05 breaks into three subtasks:

#### Sub-01: Check-In Schedule Config & Engine (Research + Implement)

**What**: Data model for scheduled check-ins (Pydantic), configurable times/frequencies, persistence. A `CheckInSchedule` that defines the 4 check-in types (morning motivation, morning plan, afternoon check, evening review) with editable time slots.

**Depends on**: `workspace/HEARTBEAT.md` (evaluate if sufficient or needs replacing), `workspace/states.yaml` (state definitions)

**Produces**: `checkin_schedule.py` — models + JSON store for check-in configs. Pure functions to determine "is a check-in due now?" given current time and last-run timestamp.

**Key decisions**:
- Evaluate HEARTBEAT.md: can it be extended with metadata, or do we need a separate `schedules.yaml`/JSON config?
- Time window matching: exact time vs. window (e.g., 08:00-08:15). Window is more forgiving for the heartbeat poll interval.
- Persistence: track last-run timestamps to avoid duplicate firings.

#### Sub-02: State-Aware Scheduling Logic (Research + Implement)

**What**: The decision layer that reads cognitive state and modifies scheduling behavior. Given a pending check-in and the current state, should it fire, defer, modify, or suppress?

**Depends on**: Sub-01 (schedule config), `state_detection.py` [cognitive-state-detection], `task_store.py` [task-data-model-store], `memory_store.py` [memory-entry-store]

**Produces**: `schedule_engine.py` — pure functions mapping (check-in type, cognitive state) -> action. State-aware rules:
- Hyperfocus: suppress non-critical check-ins, allow only hard-deadline alerts
- Avoidance: increase frequency, use ICNU framing
- Overwhelm: simplify check-in to single-item scope
- RSD: suppress task-related check-ins entirely
- Baseline/Focus: normal operation

**Key decisions**:
- How to access current state: parse from system prompt (cheap) vs. call `detect_state` (accurate but costs an LLM call)
- Deferral strategy: skip silently vs. reschedule to later window
- Morning plan needs `TaskStore.list_tasks_by_status("pending")` — inject task summary into check-in prompt

#### Sub-03: Nanobot-ai Integration & SOUL.md (Implement + Verify)

**What**: Wire the scheduling engine into nanobot-ai's heartbeat mechanism. Add SOUL.md section for check-in behavior. Integration tests.

**Depends on**: Sub-01 (config), Sub-02 (engine), [state-response-integration], [memory-context-injection]

**Produces**: Hook/heartbeat handler that fires check-ins, SOUL.md `## Scheduled Check-Ins` section, integration tests proving the full loop.

**Key decisions**:
- Hook registration order: StateResponseHook -> MemoryContextHook -> SchedulingHook? Or does scheduling operate outside the hook chain (via heartbeat)?
- HEARTBEAT.md: extend with state-aware rules or keep static and let the engine override?
- Check-in message format: template strings vs. LLM-generated from SOUL.md guidance?
- How the bot initiates a Telegram message (nanobot-ai proactive messaging API)

### Interface Gaps to Investigate in Research

1. **Nanobot-ai proactive messaging**: All existing hooks respond to incoming messages. Task 05 needs the bot to *initiate* messages. How does nanobot-ai's heartbeat/cron actually send a message? This is the critical unknown.
2. **HEARTBEAT.md format**: Is it just markdown for the LLM to read, or does nanobot-ai parse specific fields (Time, Action)? The format suggests structured parsing.
3. **Dream cycle integration**: `dream.intervalH: 4` runs memory consolidation. Could check-ins piggyback on this mechanism, or is heartbeat separate?
4. **Multiple hooks on same message**: StateResponseHook and MemoryContextHook both modify `messages[0]`. If scheduling also modifies it, ordering and conflict avoidance must be explicit.

### Test Count Baseline

328 tests collected across all existing modules. Task 05 should target ~80-100 additional tests (consistent with tasks 02-04 adding 90-132 each).
