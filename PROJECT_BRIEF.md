# ADHD Assistant — Project Brief

## What This Is

A personal AI assistant for someone with AUDHD that runs 24/7, reaches out proactively, adapts to cognitive and emotional states, and eventually speaks with distinct personalities inspired by Disco Elysium's skill system.

## Why It Exists

The builder has AUDHD and needs to offload executive function — remembering commitments, managing deadlines, switching between tasks, recovering from avoidance spirals. Previous attempts designed the same system 3+ times without shipping. The constraint this time: **build incrementally, each piece works standalone**, use existing tools stitched together rather than building from scratch.

## Hard Constraints

These are non-negotiable decisions the user has made:

- **Incremental standalone pieces** — each task must produce something usable on its own. Builder has ADHD; build order must be easiest-first.
- **Work happens in spare time** — autonomous execution preferred, minimal babysitting.
- **Stitch, don't build** — use existing frameworks and libraries. LLMs are good at connecting things, bad at building from scratch.
- **Foundation framework: nanobot-ai** — the assistant is built on nanobot-ai (by HKUDS). This is a decided framework choice, not up for evaluation. Pin to v0.1.5. It is alpha software — expect breaking changes, git-version the workspace. SECURITY: v0.1.4.post6 removed litellm due to supply chain attack; never use earlier versions.
- **Keep it simple** — previous attempts over-architected (TypeScript monorepo, Docker, Kubernetes, AWS). Do not repeat that.
- **Manual task CRUD** — the user manages their own tasks. The assistant does not auto-create or auto-complete tasks.
- **Dynamic scheduling** — scheduling adapts to the user's state rather than being rigid.
- **Sequential Builder method** — tasks are built one at a time through the planning pipeline.
- **Budget ceiling** — monthly LLM API cost must stay under ~$7 after free tiers.
- **Primary interface: Telegram** — user interacts via Telegram on phone and Fire Tablet.
- **Always-on host: Mac Air M2** — the assistant must be able to run 24/7 on low-power hardware.
- **Secondary compute: Windows PC (Kaby Lake + GTX 1080 Ti)** — available for heavier workloads like local model inference or transcription.
- **Voice output via Kokoro TTS** — text-based interaction alone didn't work in practice for this user. The assistant must be able to speak responses aloud. Kokoro TTS is the chosen engine.
- **Fire Tablet as always-on display** — the Amazon Fire Tablet is not just a Telegram access point. It serves as a dedicated always-on dashboard/display for the assistant.
- **Prototype on Windows, deploy on Mac** — development happens on the Windows PC first, then `~/.nanobot/` is copied to Mac Air M2 for 24/7 production.

## Personality Authoring (SOUL.md)

The bot's personality is not generic. It requires deliberate authoring:

- 6-state tone adaptation — each cognitive state gets a distinct voice and approach
- Neuroaffirming language — no shame, no guilt, no "you should have"
- ICNU motivation framework — the motivational structure the user has designed
- This is the thing that makes the bot actually useful vs a generic chatbot. It deserves dedicated effort, not a footnote inside framework setup.

## The 6-State Model

The core of the assistant's adaptive behavior. Based on ADHD cognitive/emotional states:

| State | Description | Response Style |
|-------|-------------|----------------|
| Baseline | Calm, neutral | Friendly, available, no pressure |
| Focus | Engaged, productive | Clear, structured, maintain momentum |
| Hyperfocus | Locked in, time-blind | Gentle body/time reminders |
| Avoidance | Procrastinating | No shame, micro-steps, body doubling |
| Overwhelm | Emotionally flooded | Validate first, simplify, one thing |
| RSD | Rejection sensitivity | Validate pain, gentle reality-testing |

- State detection is prompt-based (the LLM classifies from message content), not custom ML.
- Transitions follow Markov chain probabilities between states.
- Each state changes how the assistant speaks and what it prioritizes.

## The Buffer System

An original ADHD accommodation pattern designed by the user:

- Pre-load N units of a recurring obligation (e.g., prepay 6 months of a bill).
- Due dates auto-decrement from the buffer invisibly.
- No deadline pressure because the buffer absorbs missed instances.
- Refill happens asynchronously whenever the person notices depletion.
- Bilateral protection: recipient is secured, payer faces zero time pressure.
- Applicable to any recurring obligation, not just financial.
- No formal academic study of this exact pattern exists (as of April 2026).

The assistant needs persistent structured storage to track buffer states.

## Proactive Check-Ins

The assistant should reach out to the user on a configurable schedule, not just respond to messages. Core check-in types:

- **Morning motivation** — a daily gut-punch quote (the Volition quote from Disco Elysium, see Personality Layer below).
- **Morning plan** — "What's the one thing you want to get done today?"
- **Afternoon check** — "Quick check — how's it going? Need a reset?"
- **Evening review** — "What went well today? Even small things count."

Times and frequency should be user-configurable.

## Memory

The assistant needs both short-term and long-term memory:

- **Short-term**: Rolling conversation buffer, auto-managed.
- **Long-term**: Consolidated knowledge from conversations, persisted across restarts.
- **Structured categories**: commitment, deadline, blocker, energy_state, context_switch.
- **Future**: Vector-indexed retrieval for scaling beyond simple text search.

## Disco Elysium Personality Layer (Future Milestone)

The assistant's voice is modeled after Disco Elysium's skill system. This is NOT part of the initial build — it is a future layer added on top of a working base system.

| Personality | Handles | Voice |
|-------------|---------|-------|
| Volition | Avoidance, Overwhelm | Firm compassion, cuts through excuses |
| Empathy | RSD, Distress | Warm, sits with pain, validates |
| Electrochemistry | Hyperfocus, Stimulation-seeking | Playful, redirects energy |
| Logic | Focus, Baseline | Structured, efficient |
| Inland Empire | Creative blocks | Weird, associative, novel |

An orchestrator reads the detected state and routes to the appropriate personality. Each personality has its own voice/prompt and memory context.

### The Volition Quote

From Disco Elysium, the Volition skill speaking as "Rigorous Self Critique":

> "And above all, you let life defeat you. All the gifts your parents gave you, all the love and patience of your friends — you drowned in a neurotoxin. You let misery win. And it will keep winning till you die, or overcome it."

This is the daily morning motivation message.

## Multi-Provider LLM

The assistant must support multiple LLM providers with automatic fallback:

- A primary provider for best reasoning quality (state detection, adaptive responses).
- A budget fallback for lower-cost inference.
- An optional local inference path using the Windows PC's GPU for zero-cost operation.
- Provider selection should be configurable, not hardcoded to specific vendors.

---

## Implementation Context

> **For research agents only.** The following is background from prior conversations. It describes tools and approaches the user has explored. Supervisors and research agents may find this useful when evaluating options, but **nothing below is a requirement or constraint**. The planner should NOT reference any of this in task specs.

### Framework Explored: nanobot-ai

- By HKUDS (University of Hong Kong Data Intelligence Lab)
- Python-based, ~4000 lines, alpha status (v0.1.5 as of April 2026)
- Has built-in: Telegram adapter (pure Python), WhatsApp adapter (Node.js bridge), cron scheduling, dream memory (short-term to long-term consolidation), multi-provider LLM support
- Config lives in `~/.nanobot/` with workspace files for personality, memory, and user context
- SECURITY NOTE: v0.1.4.post6 removed litellm due to supply chain attack. Never use versions before that.

### LLM Providers Explored

- Claude (Anthropic API) — best reasoning
- Gemini 2.5 Flash via OpenRouter — Google's $300 free credits
- Ollama on Windows PC (GTX 1080 Ti) — local zero-cost inference

### Reference Repos

These repos contain patterns relevant to this project and are available in the `references/` directory:

- **ProactiveAgent** — proactive scheduling and outreach patterns
- **google-calendar-mcp** — calendar integration via MCP
- **adha_bot** — ADHD-specific bot patterns
- **TEMM1E** — personality/emotion engine patterns
- **memU** — memory and user modeling

### Development Environment

- Google Antigravity (agent-first IDE)
- Claude Code CLI
- Mac Air M2 + Windows PC dual setup

### Prior Design Patterns

- The Disco Elysium personality layer maps to a pattern the user built before (CommSkills/SUTRA: Coach, Safety, Boundary, Evaluator, Summarizer) with a Disco Elysium skin.
- The buffer system needs a simple persistent store — prior conversations explored SQLite.

### Links to Original Conversations

- Shawn's Project: Full MVP build with Python/Flask, 6-state Markov chain
- disco quote: Volition quote discovery, Disco Elysium personality concept
- ADHD App with Claude API: React/TypeScript/Node implementation
- Prepaid bill payment system for ADHD: Buffer concept deep-dive
- Buffer-based task management for ADHD: Experimental design for testing the buffer pattern
- ADHD management app with persistent memory: Framework selection, cost analysis
- ADHD management apps and tools: Telegram setup, Fire Tablet plan
- Setting up nanobots on Mac and Fire Tablet: Implementation chat
