"""Shared protocol for nanobot-ai hook context.

Used by StateResponseHook, MemoryContextHook, SchedulingHook, and BufferHook to define
the minimal interface they need from nanobot-ai's AgentHookContext.
"""

from typing import Protocol


class HookContext(Protocol):
    """Minimal protocol matching nanobot-ai AgentHookContext.messages."""

    @property
    def messages(self) -> list[dict[str, str]]: ...
