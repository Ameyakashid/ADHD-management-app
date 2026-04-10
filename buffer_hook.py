"""Buffer auto-decrement hook for nanobot-ai heartbeat sessions.

Checks active buffers on each heartbeat tick, auto-decrements those past
their due date, and injects low-level alerts into the system prompt so
the LLM can surface them using SOUL.md's buffer guidance.

Hook ordering: runs AFTER SchedulingHook (4th position). The system prompt
already contains cognitive state and check-in context when this hook reads it.
"""

import logging
from datetime import date
from typing import Callable

from buffer_store import Buffer, BufferStore
from hook_context import HookContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def find_due_buffers(
    buffers: list[Buffer],
    current_date: date,
) -> list[Buffer]:
    """Return active buffers whose next_due_date is on or before current_date."""
    return [b for b in buffers if b.next_due_date <= current_date]


def format_buffer_alert_line(buffer: Buffer) -> str:
    """Format a single buffer into an alert line with factual status."""
    return (
        f"- {buffer.name}: {buffer.buffer_level}/{buffer.buffer_capacity} "
        f"(due {buffer.next_due_date.isoformat()}, "
        f"every {buffer.recurrence_interval_days} days)"
    )


def format_buffer_alerts(alertable_buffers: list[Buffer]) -> str:
    """Format all alertable buffers into a system prompt block.

    Returns empty string if no buffers need alerting.
    """
    if not alertable_buffers:
        return ""
    lines = ["## Buffer Alerts", ""]
    for buffer in alertable_buffers:
        lines.append(format_buffer_alert_line(buffer))
    return "\n".join(lines)


def collect_alertable_buffers(buffers: list[Buffer]) -> list[Buffer]:
    """Return buffers at or below their alert threshold."""
    return [b for b in buffers if b.buffer_level <= b.alert_threshold]


def inject_alerts_into_prompt(
    system_content: str,
    alert_block: str,
) -> str:
    """Append buffer alert block to the system prompt content."""
    if not alert_block:
        return system_content
    return system_content + "\n\n" + alert_block


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------

class BufferHook:
    """Hook that auto-decrements due buffers and injects low-level alerts.

    Designed for nanobot-ai's AgentHook lifecycle. On before_iteration(),
    detects heartbeat sessions, processes due buffers, and enriches the
    system prompt with alert data for the LLM to present per SOUL.md rules.

    Constructor callables decouple the hook from runtime concerns:
    - is_scheduled_session: returns True in heartbeat/cron sessions
    - get_current_date: wall-clock date in user's timezone
    """

    def __init__(
        self,
        buffer_store: BufferStore,
        is_scheduled_session: Callable[[], bool],
        get_current_date: Callable[[], date],
    ) -> None:
        self._buffer_store = buffer_store
        self._is_scheduled_session = is_scheduled_session
        self._get_current_date = get_current_date

    async def before_iteration(self, context: HookContext) -> None:
        """Auto-decrement due buffers and inject alerts into system prompt."""
        try:
            self._process(context)
        except Exception as exc:
            log.warning("Buffer hook failed: %s", exc)

    def _process(self, context: HookContext) -> None:
        """Core buffer logic, separated for testability."""
        messages = context.messages
        if not messages:
            return

        if not self._is_scheduled_session():
            return

        if messages[0].get("role") != "system":
            return

        current_date = self._get_current_date()
        active_buffers = self._buffer_store.list_active_buffers()
        if not active_buffers:
            return

        # Pass 1: auto-decrement due buffers with level > 0
        due_buffers = find_due_buffers(active_buffers, current_date)
        decremented_ids: list[str] = []
        for buffer in due_buffers:
            if buffer.buffer_level > 0:
                self._buffer_store.decrement(buffer.id)
                decremented_ids.append(buffer.id)
                log.info(
                    "Auto-decremented buffer %s (%s)",
                    buffer.id[:8], buffer.name,
                )
            else:
                log.info(
                    "Buffer %s (%s) is at level 0 — skipping decrement",
                    buffer.id[:8], buffer.name,
                )

        # Re-read to get post-decrement state for alert evaluation
        post_decrement_buffers = self._buffer_store.list_active_buffers()

        # Pass 2: collect buffers needing alerts (at or below threshold)
        alertable = collect_alertable_buffers(post_decrement_buffers)
        alert_block = format_buffer_alerts(alertable)
        if not alert_block:
            return

        messages[0] = {
            **messages[0],
            "content": inject_alerts_into_prompt(
                messages[0]["content"], alert_block
            ),
        }
        log.info(
            "Injected buffer alerts for %d buffer(s) "
            "(decremented %d this tick)",
            len(alertable), len(decremented_ids),
        )
