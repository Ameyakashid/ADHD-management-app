# Task 03 — Task Management

## What

Manual CRUD operations for tasks via the Telegram bot interface. The user creates, lists, updates, and completes tasks through bot commands or natural language. Tasks persist across bot restarts.

## Depends On

Task 01 (bot interface and infrastructure).

## Produces

- Task creation, reading, updating, and deletion via bot
- Persistent task storage that survives restarts
- Task data model accessible to downstream features (scheduling, buffers)

## User Constraints

- Manual CRUD only. The assistant does NOT auto-create or auto-complete tasks.
- Dynamic scheduling (Task 05) will build on this task store.
- The buffer system (Task 06) will extend the concept of recurring obligations.

## Supervisor Focus

- How nanobot-ai handles bot commands or natural language parsing
- What persistent storage options work within the framework
- How to structure task data for extensibility (scheduling, buffers will need it)
- How to keep the interface natural — ADHD users won't memorize slash commands
