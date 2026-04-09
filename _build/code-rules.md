# Code Rules — ADHD Assistant (Python on nanobot-ai)

Adapted from `Antigravity-Agent-guided/rules/anti-slop-rules.md` for this project.

---

## Universal Rules

### Pure Functions and Explicit Behavior
- Write pure functions — only modify return values, never input parameters or global state
- Never use default parameter values — make all parameters explicit
- Single-purpose functions — no multi-mode behavior, no flag parameters
- Raise errors explicitly with context: what was attempted, what failed, what to do
- No fallbacks unless explicitly requested — fix root causes
- Check if logic exists before writing new code
- Keep changes minimal and related to the current task

### Naming
- **Functions:** verb-noun pattern — `fetch_user_data`, `validate_email`, `create_task`
- **Variables:** descriptive, no single letters — `user_count` not `n`, `is_active` not `flag`
- **Booleans:** prefix with `is_`, `has_`, `should_`, `can_`
- **Constants:** UPPER_SNAKE_CASE — `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT_MS`
- **Files:** snake_case — `user_service.py`, `auth_middleware.py`
- No abbreviations in public APIs

### Structure
- No file over 300 lines. Split by responsibility.
- No god classes or god functions.
- Imports organized: stdlib → external → internal.
- No circular dependencies.
- Co-locate tests with source or in parallel `tests/` directory.

### Immutability
- Return new objects from functions; don't modify inputs.
- Prefer immutable data structures where possible.

### Error Handling
- Raise specific error types, not generic `Exception`.
- Only catch errors you can meaningfully handle. Let the rest propagate.
- No try/catch around everything.
- Error messages include: what was attempted, what input caused failure, what to do.

### DRY / KISS / YAGNI
- Three concrete implementations before one abstraction.
- The simpler approach wins unless there's a measured reason for complexity.
- Don't build for hypothetical future requirements.

---

## Python-Specific Rules

- **Type hints everywhere.** Every function parameter and return type must be annotated.
- **`dataclasses` or `pydantic` for data structures.** No raw dicts for domain objects.
- **`pathlib` for file paths.** No string concatenation for paths.
- **`logging` module only.** No `print()` in production code.
- **Type-check with `mypy --strict` or `pyright`.**
- **No `Any` type.** If you can't type it, you don't understand it.
- **No mutable default arguments.** Use `None` sentinel + explicit creation inside the function body.

---

## AI-Specific Anti-Slop Rules

1. **No "just in case" code.** If nothing needs it now, don't write it.
2. **No restating comments.** Comments explain WHY, never WHAT. If code needs a WHAT comment, improve the names.
3. **No unnecessary abstractions.** Don't wrap a simple operation in a class unless it's used in 3+ places.
4. **No single-purpose utility files.** If a helper is used in one place, put it in that file.
5. **No `Any` to bypass type safety.**
6. **No bare `except`.** Only catch specific exceptions you can handle.
7. **No `print()` for debugging.** Use `logging` with levels.
8. **No god files.** Max 300 lines per file.
9. **No trivial dependencies.** If writable in 10 lines, write it.
10. **When unsure, pick simpler.**
11. **Every output must be tested.** Write tests. Run tests. Fix the code if tests fail — not the tests.
12. **Write code like a senior engineer is reviewing it.** Because a verification agent will.

---

## Enforcement

- Tests must pass before commit.
- Type checker must pass before commit.
- These rules are loaded by every automated agent. Violations caught in verification will block the pipeline.
