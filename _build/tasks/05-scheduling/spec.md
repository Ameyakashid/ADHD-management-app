# Task 05 — Scheduling & Check-Ins

## What

Dynamic scheduling that adapts to the user's cognitive state, plus proactive check-ins that reach out on configurable schedules. The bot initiates conversations rather than just responding.

## Depends On

Task 02 (state detection), Task 03 (task store), Task 04 (memory).

## Produces

- Dynamic scheduling engine that adjusts based on user state
- Morning motivation check-in (the Volition quote)
- Morning plan check-in ("What's the one thing?")
- Afternoon check-in ("How's it going?")
- Evening review check-in ("What went well?")
- User-configurable check-in times and frequencies

## User Constraints

- Scheduling adapts to state, not rigid cron-style.
- Check-in times and frequency must be user-configurable.
- nanobot-ai has built-in cron scheduling — evaluate it first.

## Supervisor Focus

- How nanobot-ai's cron scheduling works
- How to make scheduling state-aware (defer check-ins during hyperfocus, increase during avoidance)
- How to structure check-in templates for personality consistency
- How configurable scheduling interacts with the bot interface
