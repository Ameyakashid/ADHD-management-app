# Task 01 — Foundation

## What

A working nanobot-ai v0.1.5 workspace with a Telegram bot that connects, receives messages, and responds. The bot runs on the Mac Air M2 and is developed on the Windows PC. This is proof-of-life: the framework works, the bot is reachable, and downstream tasks have a running system to build on.

## Depends On

Nothing. This is the first task.

## Produces

- A configured nanobot-ai workspace (`~/.nanobot/` structure)
- A bot that connects to Telegram and responds to messages
- Multi-provider LLM configuration (primary + budget fallback)
- A runnable entry point that can be started with a single command
- The build pipeline scaffolding (`_build/` with plan, index, code-rules, specs)

## User Constraints

- nanobot-ai v0.1.5 exactly. Never earlier versions (supply chain risk in v0.1.4.post5 and below).
- Prototype on Windows, deploy on Mac — workspace must be portable.
- Monthly LLM budget ceiling ~$7. Provider configuration must support budget fallback.
- Telegram is the primary interface.
- Keep it simple — no over-engineering.

## Supervisor Focus

- How nanobot-ai workspaces are structured and configured
- How to set up Telegram bot credentials securely (not in source code)
- How multi-provider LLM fallback works in nanobot-ai
- What the minimal viable configuration looks like
- How to make the workspace portable between Windows and Mac
