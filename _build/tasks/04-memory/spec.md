# Task 04 — Memory

## What

Short-term conversation buffer and long-term memory consolidation. The bot remembers context within a conversation and persists important information (commitments, deadlines, blockers, energy states, context switches) across restarts.

## Depends On

Task 01 (bot infrastructure).

## Produces

- Short-term rolling conversation buffer
- Long-term memory with structured categories
- Memory consolidation (short-term → long-term)
- Memory retrieval for context in responses

## User Constraints

- Structured memory categories: commitment, deadline, blocker, energy_state, context_switch.
- Future milestone: vector-indexed retrieval. Don't build it now, but don't block it.
- nanobot-ai has built-in "dream memory" — evaluate whether it meets these needs before building custom.

## Supervisor Focus

- What nanobot-ai's built-in memory system provides
- Whether dream memory (short→long consolidation) maps to the requirements
- What gaps exist between built-in memory and the structured categories needed
- How memory interacts with state detection (Task 02) and scheduling (Task 05)
