"""Persist cognitive state to a JSON file for dashboard consumption.

Writes current state plus a rolling history of recent transitions.
Follows the project's atomic-write pattern (write .tmp, then replace).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

MAX_HISTORY_ENTRIES = 20


class CognitiveStateSnapshot(BaseModel):
    """A single cognitive state observation."""

    state: str
    previous_state: str
    detected_at: datetime
    is_transition_blocked: bool


class CognitiveStateFile(BaseModel):
    """On-disk format for cognitive state persistence."""

    current: CognitiveStateSnapshot
    history: list[CognitiveStateSnapshot] = Field(default_factory=list)


def build_snapshot(
    state: str,
    previous_state: str,
    is_transition_blocked: bool,
    detected_at: datetime,
) -> CognitiveStateSnapshot:
    """Create a new snapshot from detection results."""
    return CognitiveStateSnapshot(
        state=state,
        previous_state=previous_state,
        detected_at=detected_at,
        is_transition_blocked=is_transition_blocked,
    )


def append_to_history(
    history: list[CognitiveStateSnapshot],
    snapshot: CognitiveStateSnapshot,
) -> list[CognitiveStateSnapshot]:
    """Return a new history list with the snapshot appended, trimmed to max."""
    return [*history, snapshot][-MAX_HISTORY_ENTRIES:]


def serialize_state_file(state_file: CognitiveStateFile) -> str:
    """Serialize state file to JSON string."""
    return json.dumps(state_file.model_dump(mode="json"), indent=2)


def deserialize_state_file(raw: str) -> CognitiveStateFile:
    """Parse JSON string into a CognitiveStateFile."""
    return CognitiveStateFile.model_validate(json.loads(raw))


def write_cognitive_state(
    file_path: Path,
    state: str,
    previous_state: str,
    is_transition_blocked: bool,
) -> CognitiveStateFile:
    """Persist cognitive state to disk with atomic write.

    Reads existing history if the file exists, appends the new snapshot,
    trims to MAX_HISTORY_ENTRIES, and writes atomically.
    """
    now = datetime.now(timezone.utc)
    snapshot = build_snapshot(state, previous_state, is_transition_blocked, now)

    existing_history: list[CognitiveStateSnapshot] = []
    if file_path.exists():
        try:
            existing = deserialize_state_file(
                file_path.read_text(encoding="utf-8")
            )
            existing_history = existing.history
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning("Corrupt state file, resetting history: %s", exc)

    state_file = CognitiveStateFile(
        current=snapshot,
        history=append_to_history(existing_history, snapshot),
    )

    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = serialize_state_file(state_file)
    tmp_path = file_path.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(file_path)

    log.info("Persisted cognitive state: %s → %s", previous_state, state)
    return state_file


def read_cognitive_state(file_path: Path) -> CognitiveStateFile | None:
    """Read persisted cognitive state from disk. Returns None if missing."""
    if not file_path.exists():
        return None
    raw = file_path.read_text(encoding="utf-8")
    return deserialize_state_file(raw)
