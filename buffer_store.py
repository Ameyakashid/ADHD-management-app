"""Buffer data model and persistent JSON storage for the ADHD assistant.

Provides a Buffer model (Pydantic BaseModel) and a BufferStore class that
persists buffers to a JSON file with atomic writes. Buffers track pre-loaded
units of recurring obligations with decrement and refill operations.
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

log = logging.getLogger(__name__)

BufferStatus = Literal["active", "paused", "archived"]
ALL_BUFFER_STATUSES: frozenset[str] = frozenset(["active", "paused", "archived"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Buffer(BaseModel):
    """A pre-loaded buffer of units for a recurring obligation."""

    id: str
    name: str
    buffer_level: int = Field(ge=0)
    buffer_capacity: int = Field(ge=1)
    recurrence_interval_days: int = Field(ge=1)
    next_due_date: date
    alert_threshold: int = Field(ge=0)
    status: BufferStatus
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def check_cross_field_invariants(self) -> "Buffer":
        if self.buffer_level > self.buffer_capacity:
            raise ValueError(
                f"buffer_level ({self.buffer_level}) cannot exceed "
                f"buffer_capacity ({self.buffer_capacity})"
            )
        if self.alert_threshold > self.buffer_capacity:
            raise ValueError(
                f"alert_threshold ({self.alert_threshold}) cannot exceed "
                f"buffer_capacity ({self.buffer_capacity})"
            )
        return self


class BufferUpdate(BaseModel):
    """Fields that can be changed on an existing buffer.

    Only fields explicitly set are applied — unset fields are ignored
    via model_dump(exclude_unset=True). buffer_level is NOT updatable
    here — use decrement/refill to enforce invariants.
    """

    name: str | None = None
    buffer_capacity: int | None = None
    recurrence_interval_days: int | None = None
    next_due_date: date | None = None
    alert_threshold: int | None = None
    status: BufferStatus | None = None


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def generate_buffer_id() -> str:
    """Return a collision-safe hex buffer ID."""
    return uuid.uuid4().hex


def build_buffer(
    name: str,
    buffer_level: int,
    buffer_capacity: int,
    recurrence_interval_days: int,
    next_due_date: date,
    alert_threshold: int,
) -> Buffer:
    """Construct a new Buffer with generated ID and UTC timestamps."""
    now = datetime.now(timezone.utc)
    return Buffer(
        id=generate_buffer_id(),
        name=name,
        buffer_level=buffer_level,
        buffer_capacity=buffer_capacity,
        recurrence_interval_days=recurrence_interval_days,
        next_due_date=next_due_date,
        alert_threshold=alert_threshold,
        status="active",
        created_at=now,
        updated_at=now,
    )


def decrement_buffer(buffer: Buffer) -> Buffer:
    """Return a new Buffer with level reduced by 1 and next_due_date advanced.

    Raises ValueError if buffer_level is already 0.
    """
    if buffer.buffer_level == 0:
        raise ValueError(
            f"Cannot decrement buffer '{buffer.name}' (id={buffer.id[:8]}): "
            f"buffer_level is already 0"
        )
    data = buffer.model_dump(mode="json")
    data["buffer_level"] = buffer.buffer_level - 1
    data["next_due_date"] = (
        buffer.next_due_date + timedelta(days=buffer.recurrence_interval_days)
    )
    data["updated_at"] = datetime.now(timezone.utc)
    return Buffer.model_validate(data)


def refill_buffer(buffer: Buffer, units: int) -> Buffer:
    """Return a new Buffer with level increased by units, capped at capacity.

    Raises ValueError if units < 1.
    """
    if units < 1:
        raise ValueError(
            f"Cannot refill buffer '{buffer.name}' with {units} units: "
            f"units must be at least 1"
        )
    new_level = min(buffer.buffer_level + units, buffer.buffer_capacity)
    data = buffer.model_dump(mode="json")
    data["buffer_level"] = new_level
    data["updated_at"] = datetime.now(timezone.utc)
    return Buffer.model_validate(data)


def apply_buffer_updates(buffer: Buffer, updates: BufferUpdate) -> Buffer:
    """Return a new Buffer with the specified fields changed."""
    changes = updates.model_dump(exclude_unset=True)
    if not changes:
        return buffer
    current = buffer.model_dump(mode="json")
    current.update(changes)
    current["updated_at"] = datetime.now(timezone.utc)
    return Buffer.model_validate(current)


def serialize_buffers(buffers: dict[str, Buffer]) -> str:
    """Serialize buffer dict to JSON string."""
    data = {"buffers": [b.model_dump(mode="json") for b in buffers.values()]}
    return json.dumps(data, indent=2)


def deserialize_buffers(raw: str) -> dict[str, Buffer]:
    """Parse JSON string into a buffer dict keyed by ID."""
    data = json.loads(raw)
    if not isinstance(data, dict) or "buffers" not in data:
        raise ValueError(
            "Buffer store JSON must have a top-level 'buffers' key. "
            f"Got keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
        )
    result: dict[str, Buffer] = {}
    for entry in data["buffers"]:
        buffer = Buffer.model_validate(entry)
        result[buffer.id] = buffer
    return result


# ---------------------------------------------------------------------------
# BufferStore
# ---------------------------------------------------------------------------

class BufferStore:
    """CRUD operations over a JSON-persisted buffer collection.

    Loads buffers from disk on init. Every mutation writes through to disk
    atomically (write to .tmp, then rename).
    """

    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path
        self._buffers: dict[str, Buffer] = {}
        if storage_path.exists():
            raw = storage_path.read_text(encoding="utf-8")
            self._buffers = deserialize_buffers(raw)

    def _save(self) -> None:
        content = serialize_buffers(self._buffers)
        tmp_path = self._storage_path.with_suffix(".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(self._storage_path)

    def reload(self) -> None:
        """Re-read buffers from disk, discarding in-memory state."""
        if self._storage_path.exists():
            raw = self._storage_path.read_text(encoding="utf-8")
            self._buffers = deserialize_buffers(raw)
        else:
            self._buffers = {}

    def create_buffer(
        self,
        name: str,
        buffer_level: int,
        buffer_capacity: int,
        recurrence_interval_days: int,
        next_due_date: date,
        alert_threshold: int,
    ) -> Buffer:
        """Create a new buffer and persist it."""
        buffer = build_buffer(
            name, buffer_level, buffer_capacity,
            recurrence_interval_days, next_due_date, alert_threshold,
        )
        self._buffers[buffer.id] = buffer
        self._save()
        log.info("Created buffer %s: %s", buffer.id[:8], buffer.name)
        return buffer

    def get_buffer(self, buffer_id: str) -> Buffer:
        """Retrieve a buffer by ID. Raises KeyError if not found."""
        buffer = self._buffers.get(buffer_id)
        if buffer is None:
            raise KeyError(
                f"Buffer not found: '{buffer_id}'. "
                f"Store contains {len(self._buffers)} buffer(s)."
            )
        return buffer

    def list_buffers(self) -> list[Buffer]:
        """Return all buffers."""
        return list(self._buffers.values())

    def list_active_buffers(self) -> list[Buffer]:
        """Return buffers with status 'active'."""
        return [b for b in self._buffers.values() if b.status == "active"]

    def update_buffer(self, buffer_id: str, updates: BufferUpdate) -> Buffer:
        """Apply partial updates to an existing buffer. Returns the new buffer."""
        existing = self.get_buffer(buffer_id)
        updated = apply_buffer_updates(existing, updates)
        self._buffers[updated.id] = updated
        self._save()
        log.info("Updated buffer %s", buffer_id[:8])
        return updated

    def decrement(self, buffer_id: str) -> Buffer:
        """Decrement buffer level by 1 and advance next_due_date."""
        existing = self.get_buffer(buffer_id)
        decremented = decrement_buffer(existing)
        self._buffers[decremented.id] = decremented
        self._save()
        log.info(
            "Decremented buffer %s to level %d",
            buffer_id[:8], decremented.buffer_level,
        )
        return decremented

    def refill(self, buffer_id: str, units: int) -> Buffer:
        """Refill buffer by adding units, capped at capacity."""
        existing = self.get_buffer(buffer_id)
        refilled = refill_buffer(existing, units)
        self._buffers[refilled.id] = refilled
        self._save()
        log.info(
            "Refilled buffer %s to level %d",
            buffer_id[:8], refilled.buffer_level,
        )
        return refilled

    def delete_buffer(self, buffer_id: str) -> Buffer:
        """Remove a buffer from the store. Returns the deleted buffer."""
        if buffer_id not in self._buffers:
            raise KeyError(
                f"Cannot delete buffer '{buffer_id}': not found. "
                f"Store contains {len(self._buffers)} buffer(s)."
            )
        buffer = self._buffers.pop(buffer_id)
        self._save()
        log.info("Deleted buffer %s: %s", buffer_id[:8], buffer.name)
        return buffer
