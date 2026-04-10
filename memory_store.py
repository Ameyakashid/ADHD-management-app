"""Structured memory store for the ADHD assistant.

Provides a MemoryEntry model (Pydantic BaseModel) and a MemoryEntryStore
class that persists entries to a JSON file with atomic writes. Entries
track commitments, deadlines, blockers, energy states, and context
switches with soft-delete via resolve_entry.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

MemoryCategory = Literal[
    "commitment", "deadline", "blocker", "energy_state", "context_switch"
]
ALL_CATEGORIES: frozenset[str] = frozenset(
    ["commitment", "deadline", "blocker", "energy_state", "context_switch"]
)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class MemoryEntry(BaseModel):
    """A single structured memory entry in the ADHD assistant."""

    id: str
    category: MemoryCategory
    content: str
    created_at: datetime
    resolved_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def generate_entry_id() -> str:
    """Return a collision-safe hex entry ID."""
    return uuid.uuid4().hex


def build_entry(
    category: MemoryCategory,
    content: str,
    metadata: dict[str, str],
) -> MemoryEntry:
    """Construct a new MemoryEntry with generated ID and UTC timestamp."""
    return MemoryEntry(
        id=generate_entry_id(),
        category=category,
        content=content,
        created_at=datetime.now(timezone.utc),
        metadata=dict(metadata),
    )


def resolve_entry_model(entry: MemoryEntry) -> MemoryEntry:
    """Return a new MemoryEntry with resolved_at set to now."""
    data = entry.model_dump(mode="json")
    data["resolved_at"] = datetime.now(timezone.utc)
    return MemoryEntry.model_validate(data)


def serialize_entries(entries: dict[str, MemoryEntry]) -> str:
    """Serialize entry dict to JSON string."""
    data = {"entries": [e.model_dump(mode="json") for e in entries.values()]}
    return json.dumps(data, indent=2)


def deserialize_entries(raw: str) -> dict[str, MemoryEntry]:
    """Parse JSON string into an entry dict keyed by ID."""
    data = json.loads(raw)
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(
            "Memory store JSON must have a top-level 'entries' key. "
            f"Got keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
        )
    result: dict[str, MemoryEntry] = {}
    for item in data["entries"]:
        entry = MemoryEntry.model_validate(item)
        result[entry.id] = entry
    return result


# ---------------------------------------------------------------------------
# MemoryEntryStore
# ---------------------------------------------------------------------------

class MemoryEntryStore:
    """CRUD operations over a JSON-persisted memory entry collection.

    Loads entries from disk on init. Every mutation writes through to disk
    atomically (write to .tmp, then rename).
    """

    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path
        self._entries: dict[str, MemoryEntry] = {}
        if storage_path.exists():
            raw = storage_path.read_text(encoding="utf-8")
            self._entries = deserialize_entries(raw)

    def _save(self) -> None:
        content = serialize_entries(self._entries)
        tmp_path = self._storage_path.with_suffix(".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(self._storage_path)

    def reload(self) -> None:
        """Re-read entries from disk, discarding in-memory state."""
        if self._storage_path.exists():
            raw = self._storage_path.read_text(encoding="utf-8")
            self._entries = deserialize_entries(raw)
        else:
            self._entries = {}

    def create_entry(
        self,
        category: MemoryCategory,
        content: str,
        metadata: dict[str, str],
    ) -> MemoryEntry:
        """Create a new memory entry and persist it."""
        entry = build_entry(category, content, metadata)
        self._entries[entry.id] = entry
        self._save()
        log.info("Created %s entry %s", category, entry.id[:8])
        return entry

    def get_entry(self, entry_id: str) -> MemoryEntry:
        """Retrieve an entry by ID. Raises KeyError if not found."""
        entry = self._entries.get(entry_id)
        if entry is None:
            raise KeyError(
                f"Memory entry not found: '{entry_id}'. "
                f"Store contains {len(self._entries)} entry/entries."
            )
        return entry

    def list_entries(self) -> list[MemoryEntry]:
        """Return all entries (active and resolved)."""
        return list(self._entries.values())

    def list_active_entries(self) -> list[MemoryEntry]:
        """Return entries where resolved_at is None."""
        return [e for e in self._entries.values() if e.resolved_at is None]

    def list_entries_by_category(
        self, category: MemoryCategory,
    ) -> list[MemoryEntry]:
        """Return active entries filtered by category."""
        return [
            e for e in self._entries.values()
            if e.category == category and e.resolved_at is None
        ]

    def resolve_entry(self, entry_id: str) -> MemoryEntry:
        """Soft-delete an entry by setting resolved_at. Idempotent."""
        existing = self.get_entry(entry_id)
        resolved = resolve_entry_model(existing)
        self._entries[resolved.id] = resolved
        self._save()
        log.info("Resolved %s entry %s", resolved.category, entry_id[:8])
        return resolved
