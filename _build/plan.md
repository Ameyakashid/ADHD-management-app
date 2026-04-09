# ADHD Assistant — Master Plan

## Project Overview

A personal AI assistant for someone with AUDHD that runs 24/7 on a Mac Air M2, communicates via Telegram, adapts its tone and approach to the user's cognitive/emotional state, and eventually speaks with Disco Elysium-inspired personalities. Built on nanobot-ai v0.1.5. Development happens on Windows PC, deployment on Mac.

## Constraints (User-Decided)

- Incremental standalone pieces — each task produces something usable on its own
- Easiest-first build order
- Stitch existing tools, don't build from scratch
- nanobot-ai v0.1.5 (never earlier — supply chain risk)
- Manual task CRUD only — assistant does not auto-create/complete tasks
- Dynamic scheduling — adapts to user state, not rigid
- Monthly LLM budget ceiling ~$7
- Primary interface: Telegram
- Always-on host: Mac Air M2
- Secondary compute: Windows PC (GTX 1080 Ti) for local inference
- Voice output via Kokoro TTS
- Fire Tablet as always-on display

## Task Breakdown

### Task 01 — Foundation
**What:** A working nanobot-ai workspace with a bot that responds to messages via Telegram. The bot runs, connects, and replies. Nothing fancy — just proof of life.
**Depends on:** Nothing.
**Produces:** A runnable bot that downstream tasks build features on top of.

### Task 02 — Personality Core
**What:** The bot's personality definition (SOUL.md), 6-state cognitive model for tone adaptation, and neuroaffirming language patterns. The bot should feel like talking to something designed for ADHD, not a generic chatbot.
**Depends on:** Task 01 (running bot).
**Produces:** Personality configuration that all future features use for tone. State detection that scheduling and check-ins depend on.

### Task 03 — Task Management
**What:** Manual CRUD for tasks via the bot interface. The user creates, lists, updates, and completes tasks. Persistent storage survives restarts.
**Depends on:** Task 01 (bot interface).
**Produces:** A task store that scheduling, buffer system, and check-ins query.

### Task 04 — Memory
**What:** Short-term conversation buffer and long-term memory consolidation. The bot remembers context within a conversation and persists important information across restarts.
**Depends on:** Task 01 (bot infrastructure).
**Produces:** Memory system that personality, scheduling, and all future features use for context.

### Task 05 — Scheduling & Check-Ins
**What:** Dynamic scheduling that adapts to user state. Proactive check-ins (morning motivation, morning plan, afternoon check, evening review) on configurable schedules.
**Depends on:** Task 02 (state detection), Task 03 (task store), Task 04 (memory).
**Produces:** A proactive assistant that reaches out rather than just responding.

### Task 06 — Buffer System
**What:** The buffer pattern for recurring obligations. Pre-load N units, auto-decrement on due dates, refill asynchronously. Persistent structured storage for buffer states.
**Depends on:** Task 03 (task/obligation storage), Task 05 (scheduling for reminders).
**Produces:** Buffer tracking that eliminates deadline pressure for recurring obligations.

### Task 07 — Voice Output
**What:** Text-to-speech via Kokoro TTS so the bot can speak responses aloud. Triggered by the bot, played on the user's devices.
**Depends on:** Task 01 (bot infrastructure).
**Produces:** Spoken responses for check-ins and important messages.

### Task 08 — Dashboard
**What:** An always-on display on the Fire Tablet showing current state, upcoming tasks, buffer levels, and recent activity.
**Depends on:** Task 03 (tasks), Task 05 (schedule), Task 06 (buffers).
**Produces:** A passive awareness surface — the user glances at it without interacting.

## Build Order Rationale

Tasks 01-04 can be built somewhat in parallel (01 first, then 02/03/04 in any order since they all depend only on 01). Task 05 is the first integration point — it needs state detection, tasks, and memory. Tasks 06-08 extend the system with specialized features.

The order is easiest-first: getting a bot running (01) is the simplest. Personality (02) and task CRUD (03) are medium complexity. Memory (04) is moderate. Scheduling (05) is the first complex integration. Buffer (06), voice (07), and dashboard (08) are independent extensions.
