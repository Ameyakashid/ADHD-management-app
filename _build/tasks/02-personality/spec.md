# Task 02 — Personality Core

## What

The bot's personality definition, 6-state cognitive model for tone adaptation, and neuroaffirming language patterns. State detection is prompt-based (LLM classifies from message content). Each state changes how the bot speaks and what it prioritizes. The bot should feel purpose-built for ADHD, not generic.

## Depends On

Task 01 (running bot with LLM access).

## Produces

- SOUL.md or equivalent personality configuration
- 6-state model: Baseline, Focus, Hyperfocus, Avoidance, Overwhelm, RSD
- State detection from user messages
- State-specific response styles
- Neuroaffirming language patterns (no shame, no guilt, no "you should have")
- ICNU motivation framework integration

## User Constraints

- State detection is prompt-based, not custom ML.
- Transitions follow Markov chain probabilities between states.
- Neuroaffirming language is non-negotiable.
- Disco Elysium personality layer is a FUTURE milestone — do not build it now, but don't block it.

## Supervisor Focus

- How nanobot-ai handles personality/system prompts
- How to structure state detection prompts for reliability
- How to encode state transitions (Markov chain probabilities)
- How to make personality configuration editable without code changes
