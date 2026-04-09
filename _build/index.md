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

### [build-scaffolding]
> Pipeline scaffolding: plan.md, index.md, code-rules.md, all 8 task specs, subtask descriptions — bootstrapped from PROJECT_BRIEF.md
- Status: DONE
- Task: 01/sub-01
- Files: _build/plan.md, _build/index.md, _build/code-rules.md, _build/tasks/01-foundation/spec.md, _build/tasks/01-foundation/sub-01/description.md, _build/tasks/01-foundation/sub-02/description.md, _build/tasks/02-personality/spec.md, _build/tasks/03-task-crud/spec.md, _build/tasks/04-memory/spec.md, _build/tasks/05-scheduling/spec.md, _build/tasks/06-buffer/spec.md, _build/tasks/07-voice/spec.md, _build/tasks/08-dashboard/spec.md
- Depends on: none
- Detail: _build/tasks/01-foundation/sub-01/01-01x.md
