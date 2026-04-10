# Project Index

> This file is the LLM-readable registry of everything built in this project. It follows the llms.txt standard. An LLM should read THIS FILE FIRST to understand what exists, then follow links to detail files for specifics.

## How To Use This Index

If you are an LLM agent in any IDE (Antigravity, Cursor, Claude Code, etc.) and you need to understand this project:
1. Read this file to find the component you need
2. Each entry has a semantic tag, a one-line summary, and a link to the full index report
3. Read the linked `x.md` file for file paths, exports, dependencies, and decisions
4. Read the linked source files if you need actual code

## Component Registry

(Entries appended by Verify agents after each subtask)

### Entry Format

```
### [semantic-tag]
> One-line description
- Status: DONE | DONE-WITH-ISSUES
- Task: NN/sub-NN
- Files: file1.py, file2.py, ...
- Depends on: [other-semantic-tag], [another-tag]
- Detail: _build/tasks/TASK_ID/sub-NN/NN-NNx.md
```

---

### [foundation-complete]
> Working nanobot-ai v0.1.5 workspace: build pipeline, Telegram bot config, multi-provider LLM (OpenRouter+Ollama), portable deployment, 39 passing tests
- Status: DONE-WITH-ISSUES
- Task: 01 (01-foundation)
- Subtasks: [build-scaffolding], [nanobot-workspace-setup], [bot-smoke-tests]
- Produces: Configured nanobot-ai workspace deployable to ~/.nanobot/, Telegram bot entry point, multi-provider LLM config (OpenRouter primary, Ollama fallback), build pipeline scaffolding (_build/ with plan, index, code-rules, 8 task specs). Downstream tasks 02-08 can now build on a running bot.
- Issues: (1) task-verify.md was not generated — no task-level cross-subtask verification exists. (2) code-rules.md has contradictory default parameter rule (lines 12 vs 58). (3) No mypy/pyright enforcement in dev dependencies. All LOW severity.
- Detail: _build/tasks/01-foundation/sub-03/01-03x.md (latest subtask; no task-verify.md)

### [build-scaffolding]
> Pipeline scaffolding: plan.md, index.md, code-rules.md, all 8 task specs, subtask descriptions — bootstrapped from PROJECT_BRIEF.md
- Status: DONE
- Task: 01/sub-01
- Files: _build/plan.md, _build/index.md, _build/code-rules.md, _build/tasks/01-foundation/spec.md, _build/tasks/01-foundation/sub-01/description.md, _build/tasks/01-foundation/sub-02/description.md, _build/tasks/02-personality/spec.md, _build/tasks/03-task-crud/spec.md, _build/tasks/04-memory/spec.md, _build/tasks/05-scheduling/spec.md, _build/tasks/06-buffer/spec.md, _build/tasks/07-voice/spec.md, _build/tasks/08-dashboard/spec.md
- Depends on: none
- Detail: _build/tasks/01-foundation/sub-01/01-01x.md

### [nanobot-workspace-setup]
> nanobot-ai v0.1.5 workspace with Telegram bot config, OpenRouter+Ollama multi-provider LLM, and portable deployment script
- Status: DONE
- Task: 01/sub-02
- Files: requirements.txt, setup_workspace.py, .env.example, .gitignore, workspace/SOUL.md, workspace/USER.md, workspace/HEARTBEAT.md, workspace/config.json.template, tests/test_setup_workspace.py
- Depends on: [build-scaffolding]
- Detail: _build/tasks/01-foundation/sub-02/01-02x.md

### [bot-smoke-tests]
> 18 smoke tests proving nanobot-ai config loads, provider resolves, and bot can start — validates sub-02 workspace setup
- Status: DONE
- Task: 01/sub-03
- Files: tests/test_bot_smoke.py
- Depends on: [nanobot-workspace-setup]
- Detail: _build/tasks/01-foundation/sub-03/01-03x.md

### [personality-core-complete]
> ADHD-native personality system: neuroaffirming SOUL.md, 6-state cognitive model (Baseline/Focus/Hyperfocus/Avoidance/Overwhelm/RSD) with Markov transitions, and nanobot-ai hook wiring state detection into per-message response adaptation — 212 tests passing
- Status: DONE-WITH-ISSUES
- Task: 02 (02-personality)
- Subtasks: [neuroaffirming-personality], [cognitive-state-detection], [state-response-integration]
- Produces: Complete personality layer for downstream tasks 03-08. SOUL.md loaded by nanobot-ai runtime with state-aware adaptation rules. StateResponseHook detects cognitive state per message and injects indicator into system prompt. States defined in editable YAML config. ICNU motivation framework and banned-phrase guardrails active. Disco Elysium personality voice stub ready for future milestone.
- Issues: (1) MEDIUM: normalize_llm_response substring fallback matches "focus" before "hyperfocus" — fix by sorting by length descending (state_detection.py:200-202). (2) task-verify.md was not generated — no task-level cross-subtask verification exists.
- Detail: _build/tasks/02-personality/sub-03/02-03x.md (latest subtask; no task-verify.md)

### [neuroaffirming-personality]
> SOUL.md personality definition with neuroaffirming rules, ICNU motivation framework, banned-phrase list, and AUDHD USER.md profile — plus 40 validation tests
- Status: DONE
- Task: 02/sub-01
- Files: workspace/SOUL.md, workspace/USER.md, tests/test_personality.py
- Depends on: [nanobot-workspace-setup], [bot-smoke-tests]
- Detail: _build/tasks/02-personality/sub-01/02-01x.md

### [cognitive-state-detection]
> 6-state cognitive model (Baseline/Focus/Hyperfocus/Avoidance/Overwhelm/RSD) with YAML config, LLM classification prompt, Markov transition enforcement, and StateName-typed function signatures — 132 tests across 4 files
- Status: DONE
- Task: 02/sub-02
- Files: workspace/states.yaml, state_detection.py, tests/test_state_config.py, tests/test_state_detection.py
- Depends on: [nanobot-workspace-setup], [neuroaffirming-personality]
- Issues: (1) MEDIUM: normalize_llm_response substring fallback matches "focus" before "hyperfocus" — fix by sorting by length descending. Low probability due to exact-match fast path.
- Detail: _build/tasks/02-personality/sub-02/02-02x.md

### [state-response-integration]
> Nanobot-ai hook detecting cognitive state per message, injecting indicator into system prompt, activating per-state SOUL.md response rules — 3 pure functions + StateResponseHook class, 40 tests
- Status: DONE
- Task: 02/sub-03
- Files: state_response_integration.py, workspace/SOUL.md, tests/test_state_response_pure.py, tests/test_state_response_hook.py
- Depends on: [neuroaffirming-personality], [cognitive-state-detection]
- Detail: _build/tasks/02-personality/sub-03/02-03x.md

### [task-crud-complete]
> Full task management pipeline: Pydantic data model + JSON-persisted TaskStore, 5 LLM-callable nanobot-ai Tool wrappers (create/list/get/update/complete), ADHD-friendly SOUL.md task guidance with 6-state cognitive awareness — 102 tests passing
- Status: DONE-WITH-ISSUES
- Task: 03 (03-task-crud)
- Subtasks: [task-data-model-store], [nanobot-task-tools], [soul-task-instructions]
- Produces: TaskStore CRUD API (task_store.py) and 5 registered Tool subclasses (task_tools.py) for downstream tasks 04-08. SOUL.md now includes Task Management section with state-aware presentation rules. Scheduling (task-05) and buffer system (task-06) can build on the Task model and store. Tools require programmatic registration via register_task_tools() at nanobot startup — config.json wiring not yet connected.
- Issues: (1) task-verify.md was not generated — no task-level cross-subtask verification exists. (2) LOW: apply_updates mixes JSON-mode and Python-mode dicts (task_store.py:95-98). (3) LOW: No file locking for concurrent TaskStore access (acceptable for single-user). (4) LOW: test helper `run()` missing type annotations (test_task_integration.py:58). (5) Tools not yet wired into nanobot startup — register_task_tools() call deferred to future integration.
- Detail: _build/tasks/03-task-crud/sub-03/03-03x.md (latest subtask; no task-verify.md)

### [task-data-model-store]
> Task Pydantic model + JSON-persisted TaskStore with full CRUD, atomic writes, pure helper functions — 39 tests
- Status: DONE
- Task: 03/sub-01
- Files: task_store.py, tests/test_task_model.py, tests/test_task_store.py
- Depends on: [nanobot-workspace-setup]
- Detail: _build/tasks/03-task-crud/sub-01/03-01x.md

### [nanobot-task-tools]
> Five LLM-callable nanobot-ai Tool subclasses wrapping TaskStore CRUD — create, list, get, update, complete — with JSON parameter schemas, programmatic registry, 34 tests
- Status: DONE
- Task: 03/sub-02
- Files: task_tools.py, tests/test_task_tools.py
- Depends on: [task-data-model-store], [nanobot-workspace-setup]
- Detail: _build/tasks/03-task-crud/sub-02/03-02x.md

### [soul-task-instructions]
> SOUL.md task management guidance (ADHD-friendly presentation, state-aware behavior) + 29 integration tests verifying full CRUD pipeline and persistence
- Status: DONE
- Task: 03/sub-03
- Files: workspace/SOUL.md, tests/test_task_integration.py
- Depends on: [neuroaffirming-personality], [task-data-model-store], [nanobot-task-tools], [cognitive-state-detection]
- Detail: _build/tasks/03-task-crud/sub-03/03-03x.md

### [memory-entry-store]
> JSON-persisted structured memory store — 5 categories (commitment/deadline/blocker/energy_state/context_switch), Pydantic model, soft-delete resolve, atomic writes — 43 tests
- Status: DONE
- Task: 04/sub-01
- Files: memory_store.py, tests/test_memory_model.py, tests/test_memory_store.py
- Depends on: [nanobot-workspace-setup]
- Detail: _build/tasks/04-memory/sub-01/04-01x.md

### [nanobot-memory-tools]
> Three LLM-callable nanobot-ai Tool subclasses wrapping MemoryEntryStore CRUD — save, list, dismiss — with JSON parameter schemas, ToolRegistry registration, 26 tests
- Status: DONE
- Task: 04/sub-02
- Files: memory_tools.py, tests/test_memory_tools.py
- Depends on: [memory-entry-store], [nanobot-workspace-setup]
- Detail: _build/tasks/04-memory/sub-02/04-02x.md
