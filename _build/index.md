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

### [neuroaffirming-personality]
> SOUL.md personality definition with neuroaffirming rules, ICNU motivation framework, banned-phrase list, and AUDHD USER.md profile — plus 40 validation tests
- Status: DONE
- Task: 02/sub-01
- Files: workspace/SOUL.md, workspace/USER.md, tests/test_personality.py
- Depends on: [nanobot-workspace-setup], [bot-smoke-tests]
- Detail: _build/tasks/02-personality/sub-01/02-01x.md

### [cognitive-state-detection]
> 6-state cognitive model (Baseline/Focus/Hyperfocus/Avoidance/Overwhelm/RSD) with YAML config, LLM classification prompt, Markov transition enforcement, and StateName-typed DetectionResult — 132 tests across 3 files
- Status: DONE
- Task: 02/sub-02
- Files: workspace/states.yaml, state_detection.py, tests/test_state_config.py, tests/test_state_detection.py
- Depends on: [nanobot-workspace-setup], [neuroaffirming-personality]
- Detail: _build/tasks/02-personality/sub-02/02-02x.md

### [state-response-integration]
> Hook connecting cognitive state detection to SOUL.md response rules — injects state indicator into system prompt, per-state behavior for all 6 states, graceful baseline fallback
- Status: DONE
- Task: 02/sub-03
- Files: state_response_integration.py, workspace/SOUL.md, tests/test_state_response_integration.py
- Depends on: [neuroaffirming-personality], [cognitive-state-detection]
- Detail: _build/tasks/02-personality/sub-03/02-03x.md
