# Subtask 01-02 — nanobot-ai Workspace Setup

## What This Subtask Accomplishes

Sets up a working nanobot-ai v0.1.5 workspace with Telegram bot connectivity and multi-provider LLM configuration. The bot should start, connect to Telegram, receive a message, and respond. Proof of life.

## Depends On

- Subtask 01-01 (build scaffolding — plan, index, code-rules exist)
- `PROJECT_BRIEF.md` — framework choice, constraints

## Produces

- nanobot-ai v0.1.5 installed and pinned
- Workspace configuration files (personality, memory settings)
- Telegram bot token configuration (securely, not in source)
- Multi-provider LLM configuration (primary + budget fallback)
- A runnable entry point
- Basic test that the bot connects and responds

## Acceptance Criteria

1. `pip install nanobot-ai==0.1.5` succeeds (or equivalent pinning)
2. Bot starts without errors
3. Bot connects to Telegram (requires bot token — can be tested with mock/stub if token unavailable)
4. Bot responds to a test message
5. LLM provider configuration supports at least 2 providers with fallback
6. Workspace is portable between Windows and Mac (no hardcoded OS-specific paths)
7. No secrets in source code — credentials loaded from environment or config outside repo
