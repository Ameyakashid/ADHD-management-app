"""Voice trigger hook for nanobot-ai heartbeat sessions.

Scans the system prompt for active check-in and buffer alert blocks
injected by earlier hooks, then appends a Voice Delivery instruction
block telling the LLM to use SpeakTool for those items.

Hook ordering: runs AFTER BufferHook (5th position). The system prompt
already contains cognitive state, check-in, and buffer alert context.
"""

import logging
import os
from typing import Callable

from hook_context import HookContext
from state_detection import StateName

log = logging.getLogger(__name__)

CHECKIN_HEADING = "## Active Check-In:"
BUFFER_ALERT_HEADING = "## Buffer Alerts"


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def is_voice_enabled() -> bool:
    """Check whether auto-voice is enabled via environment variable."""
    return os.environ.get("VOICE_AUTO_ENABLED", "").lower() in ("true", "1", "yes")


def should_auto_voice(state: StateName, trigger_type: str) -> bool:
    """Decide whether auto-voice is allowed for the given state and trigger.

    trigger_type must be "checkin" or "buffer_alert".
    """
    allowed: dict[str, frozenset[str]] = {
        "checkin": frozenset({"baseline", "avoidance"}),
        "buffer_alert": frozenset({"baseline"}),
    }
    permitted_states = allowed.get(trigger_type)
    if permitted_states is None:
        raise ValueError(
            f"Unknown trigger_type '{trigger_type}'. "
            f"Expected 'checkin' or 'buffer_alert'."
        )
    return state in permitted_states


def detect_checkin_trigger(system_content: str) -> bool:
    """Return True if the system prompt contains an active check-in block."""
    return CHECKIN_HEADING in system_content


def detect_buffer_alert_trigger(system_content: str) -> bool:
    """Return True if the system prompt contains a buffer alerts block."""
    return BUFFER_ALERT_HEADING in system_content


def build_voice_delivery_block(voice_checkin: bool, voice_buffer: bool) -> str:
    """Build the Voice Delivery instruction block for the system prompt.

    Returns empty string if neither trigger is active.
    """
    if not voice_checkin and not voice_buffer:
        return ""

    items: list[str] = []
    if voice_checkin:
        items.append("- The Active Check-In message")
    if voice_buffer:
        items.append("- The Buffer Alert summary")

    lines = [
        "## Voice Delivery",
        "",
        "Auto-voice is enabled. Deliver the following as voice messages "
        "using the speak tool:",
    ]
    lines.extend(items)
    lines.append("")
    lines.append(
        "Speak in short, conversational sentences. "
        "No markdown, no emoji, no formatting in spoken text. "
        "Keep each voice message under 500 characters."
    )
    return "\n".join(lines)


def inject_voice_block_into_prompt(
    system_content: str,
    voice_block: str,
) -> str:
    """Append the voice delivery block to the system prompt."""
    if not voice_block:
        return system_content
    return system_content + "\n\n" + voice_block


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------

class VoiceHook:
    """Hook that injects voice delivery instructions into heartbeat sessions.

    Designed for nanobot-ai's AgentHook lifecycle. On before_iteration(),
    detects scheduled sessions, checks for auto-voice triggers from
    earlier hooks (check-in blocks, buffer alerts), evaluates the
    cognitive state, and injects voice delivery instructions.

    Constructor callables decouple the hook from runtime concerns:
    - is_scheduled_session: returns True in heartbeat/cron sessions
    - get_cognitive_state: returns last-known state (baseline if unknown)
    """

    def __init__(
        self,
        is_scheduled_session: Callable[[], bool],
        get_cognitive_state: Callable[[], StateName],
    ) -> None:
        self._is_scheduled_session = is_scheduled_session
        self._get_cognitive_state = get_cognitive_state

    async def before_iteration(self, context: HookContext) -> None:
        """Evaluate voice triggers and inject delivery instructions."""
        try:
            self._process(context)
        except Exception as exc:
            log.warning("Voice hook failed: %s", exc)

    def _process(self, context: HookContext) -> None:
        """Core voice trigger logic, separated for testability."""
        messages = context.messages
        if not messages:
            return

        if not self._is_scheduled_session():
            return

        if messages[0].get("role") != "system":
            return

        if not is_voice_enabled():
            return

        system_content = messages[0]["content"]
        state = self._get_cognitive_state()

        has_checkin = detect_checkin_trigger(system_content)
        has_buffer_alert = detect_buffer_alert_trigger(system_content)

        voice_checkin = has_checkin and should_auto_voice(state, "checkin")
        voice_buffer = has_buffer_alert and should_auto_voice(state, "buffer_alert")

        voice_block = build_voice_delivery_block(voice_checkin, voice_buffer)
        if not voice_block:
            return

        messages[0] = {
            **messages[0],
            "content": inject_voice_block_into_prompt(
                system_content, voice_block
            ),
        }
        log.info(
            "Injected voice delivery (checkin=%s, buffer=%s, state=%s)",
            voice_checkin, voice_buffer, state,
        )
