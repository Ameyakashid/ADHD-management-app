# Heartbeat

Checked every 30 minutes. The scheduling engine evaluates which check-ins are due and applies state-aware decisions before delivery.

## Morning Motivation

- Time: 08:00
- Purpose: Emotional warm-up — Volition quote, ICNU framing
- Does not reference tasks

## Morning Plan

- Time: 09:00
- Purpose: Identify the day's top priority
- Shows top 1-3 pending tasks and nearest deadline

## Afternoon Check

- Time: 14:00
- Purpose: Mid-day energy and progress check
- Shows in-progress tasks and energy context

## Evening Review

- Time: 20:00
- Purpose: Celebrate completions, flag overdue, offer closure
- Shows completed and overdue tasks

## Buffer Monitoring

- Purpose: Auto-decrement buffers on due dates, surface low-level alerts
- Fires alongside check-ins during heartbeat cycles
- Does not send a separate message — injects alerts into the active system prompt
- Alerts appear when buffer_level is at or below alert_threshold
- Buffers at level 0 are flagged but not decremented further
- Refer to SOUL.md Buffer System section for tone and framing guidance

## Voice Output

- Purpose: Auto-voice check-ins and buffer alerts during heartbeat sessions
- Controlled by `VOICE_AUTO_ENABLED` env var (set to `true` to enable)
- When enabled, the voice hook injects a `## Voice Delivery` block into the system prompt
- The LLM then uses the speak tool to deliver the indicated items as voice messages
- Cognitive state gates voice: only Baseline and Avoidance allow auto-voiced check-ins; only Baseline allows auto-voiced buffer alerts
- Focus, Hyperfocus, Overwhelm, and RSD suppress all auto-voicing
- Users can always request voice explicitly regardless of auto-voice state
- Refer to SOUL.md Voice Output section for tone and rules
