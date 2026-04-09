# Task 07 — Voice Output

## What

Text-to-speech via Kokoro TTS so the bot can speak responses aloud. Critical for this user — text-only interaction didn't work in practice.

## Depends On

Task 01 (bot infrastructure).

## Produces

- TTS generation from bot responses
- Audio delivery to user's devices
- Selective voice output (not every message — configurable triggers)

## User Constraints

- Kokoro TTS is the chosen engine.
- Windows PC (GTX 1080 Ti) available for GPU inference if needed.
- Voice should enhance, not replace, text responses.

## Supervisor Focus

- How Kokoro TTS integrates (API, local inference, or hybrid)
- Audio delivery mechanism (inline Telegram voice messages, or separate channel)
- Which messages warrant voice output vs text-only
- GPU inference on Windows PC vs CPU on Mac tradeoffs
