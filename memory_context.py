"""Memory context injection hook for nanobot-ai.

Reads active structured memories from MemoryEntryStore and injects
a formatted summary into the system prompt on each message. Placed
after the ## Long-term Memory section built by nanobot's ContextBuilder.
"""

import logging
from typing import Protocol

from memory_store import MemoryEntry, MemoryEntryStore

log = logging.getLogger(__name__)

DEFAULT_MAX_INJECTED_ENTRIES: int = 20

ACTIVE_MEMORIES_HEADING = "## Active Memories"
LONG_TERM_MEMORY_HEADING = "## Long-term Memory"


class HookContext(Protocol):
    """Minimal protocol matching nanobot-ai AgentHookContext.messages."""

    @property
    def messages(self) -> list[dict[str, str]]: ...


def format_single_entry(entry: MemoryEntry) -> str:
    """Format one memory entry as a compact markdown list item.

    Format: - [category] content (key=value, ...)
    """
    line = f"- [{entry.category}] {entry.content}"
    if entry.metadata:
        pairs = ", ".join(f"{k}={v}" for k, v in entry.metadata.items())
        line = f"{line} ({pairs})"
    return line


def format_memory_entries(entries: list[MemoryEntry]) -> str:
    """Format a list of memory entries with the Active Memories heading.

    Returns empty string for an empty list. Entries are sorted by
    created_at descending (most recent first).
    """
    if not entries:
        return ""
    sorted_entries = sorted(entries, key=lambda e: e.created_at, reverse=True)
    lines = [format_single_entry(e) for e in sorted_entries]
    return f"{ACTIVE_MEMORIES_HEADING}\n\n" + "\n".join(lines)


def inject_memories_into_prompt(
    system_content: str, memory_block: str
) -> str:
    """Insert memory_block after the Long-term Memory section in the prompt.

    Scans for '## Long-term Memory' heading and inserts the block before
    the next section boundary (line starting with '#' or '---').
    Falls back to appending at the end if the heading is not found.
    """
    if not memory_block:
        return system_content

    lines = system_content.split("\n")
    heading_index: int | None = None

    for i, line in enumerate(lines):
        if line.strip() == LONG_TERM_MEMORY_HEADING:
            heading_index = i
            break

    if heading_index is None:
        return system_content + "\n\n" + memory_block

    # Scan forward from heading to find the next section boundary
    insert_at = len(lines)
    for i in range(heading_index + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("#") or stripped == "---":
            insert_at = i
            break

    before = lines[:insert_at]
    after = lines[insert_at:]
    return "\n".join(before) + "\n\n" + memory_block + "\n\n" + "\n".join(after)


class MemoryContextHook:
    """Hook that injects active memories into the system prompt.

    Designed for nanobot-ai's AgentHook lifecycle. Call before_iteration()
    before each LLM call to enrich the system prompt with active memories.
    """

    def __init__(self, store: MemoryEntryStore, max_entries: int) -> None:
        self._store = store
        self._max_entries = max_entries

    async def before_iteration(self, context: HookContext) -> None:
        """Read active memories and inject them into the system prompt."""
        try:
            self._inject(context)
        except Exception as exc:
            log.warning("Memory context injection failed: %s", exc)

    def _inject(self, context: HookContext) -> None:
        """Core injection logic, separated for testability."""
        messages = context.messages
        if not messages:
            return

        if messages[0].get("role") != "system":
            return

        entries = self._store.list_active_entries()
        sorted_entries = sorted(
            entries, key=lambda e: e.created_at, reverse=True
        )
        truncated = sorted_entries[: self._max_entries]

        formatted = format_memory_entries(truncated)
        if not formatted:
            return

        messages[0] = {
            **messages[0],
            "content": inject_memories_into_prompt(
                messages[0]["content"], formatted
            ),
        }
