"""Tests for MemoryEntry model, pure helpers, and serialization."""

from datetime import datetime, timezone

import pytest

from memory_store import (
    ALL_CATEGORIES,
    MemoryEntry,
    build_entry,
    deserialize_entries,
    resolve_entry_model,
    serialize_entries,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_entry() -> MemoryEntry:
    return MemoryEntry(
        id="abc123",
        category="commitment",
        content="Will finish the report by Friday",
        created_at=datetime(2026, 4, 9, 10, 0, tzinfo=timezone.utc),
        metadata={"context": "standup"},
    )


# ---------------------------------------------------------------------------
# Type constant tests
# ---------------------------------------------------------------------------

class TestTypeConstants:
    """Verify the Literal type matches the frozenset constant."""

    def test_all_categories(self) -> None:
        assert ALL_CATEGORIES == {
            "commitment", "deadline", "blocker", "energy_state", "context_switch"
        }

    def test_all_categories_has_five_members(self) -> None:
        assert len(ALL_CATEGORIES) == 5


# ---------------------------------------------------------------------------
# MemoryEntry model tests
# ---------------------------------------------------------------------------

class TestMemoryEntryModel:
    """Verify MemoryEntry model validation and serialization."""

    def test_round_trip_json(self, sample_entry: MemoryEntry) -> None:
        dumped = sample_entry.model_dump(mode="json")
        restored = MemoryEntry.model_validate(dumped)
        assert restored.id == sample_entry.id
        assert restored.category == sample_entry.category
        assert restored.content == sample_entry.content

    def test_accepts_all_five_categories(self) -> None:
        now = datetime.now(timezone.utc)
        for cat in ALL_CATEGORIES:
            entry = MemoryEntry(
                id="x", category=cat, content="test", created_at=now,
            )
            assert entry.category == cat

    def test_rejects_invalid_category(self) -> None:
        with pytest.raises(Exception):
            MemoryEntry(
                id="x",
                category="invalid",
                content="bad",
                created_at=datetime.now(timezone.utc),
            )

    def test_optional_fields_default(self) -> None:
        entry = MemoryEntry(
            id="x",
            category="blocker",
            content="stuck",
            created_at=datetime.now(timezone.utc),
        )
        assert entry.resolved_at is None
        assert entry.metadata == {}

    def test_datetime_survives_json_round_trip(
        self, sample_entry: MemoryEntry,
    ) -> None:
        dumped = sample_entry.model_dump(mode="json")
        restored = MemoryEntry.model_validate(dumped)
        assert restored.created_at == sample_entry.created_at

    def test_metadata_round_trip(self) -> None:
        entry = MemoryEntry(
            id="m1",
            category="deadline",
            content="Project due",
            created_at=datetime.now(timezone.utc),
            metadata={"due_date": "2026-04-15", "priority": "high"},
        )
        dumped = entry.model_dump(mode="json")
        restored = MemoryEntry.model_validate(dumped)
        assert restored.metadata == {"due_date": "2026-04-15", "priority": "high"}


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestBuildEntry:
    """Verify build_entry constructs valid entries."""

    def test_creates_entry_with_correct_category(self) -> None:
        entry = build_entry("commitment", "I'll do it", {})
        assert entry.category == "commitment"
        assert entry.content == "I'll do it"

    def test_generates_unique_ids(self) -> None:
        entry_a = build_entry("blocker", "A", {})
        entry_b = build_entry("blocker", "B", {})
        assert entry_a.id != entry_b.id

    def test_sets_utc_timestamp(self) -> None:
        entry = build_entry("deadline", "Due soon", {})
        assert entry.created_at.tzinfo is not None

    def test_resolved_at_is_none(self) -> None:
        entry = build_entry("energy_state", "Low energy", {})
        assert entry.resolved_at is None

    def test_defensive_copies_metadata(self) -> None:
        original_meta = {"key": "value"}
        entry = build_entry("context_switch", "Switched to email", original_meta)
        original_meta["key"] = "changed"
        assert entry.metadata == {"key": "value"}

    def test_includes_metadata(self) -> None:
        entry = build_entry(
            "deadline", "Report due", {"due_date": "2026-04-15"},
        )
        assert entry.metadata == {"due_date": "2026-04-15"}


class TestResolveEntryModel:
    """Verify resolve_entry_model returns new entry with resolved_at set."""

    def test_sets_resolved_at(self, sample_entry: MemoryEntry) -> None:
        resolved = resolve_entry_model(sample_entry)
        assert resolved.resolved_at is not None
        assert resolved.resolved_at.tzinfo is not None

    def test_does_not_mutate_original(self, sample_entry: MemoryEntry) -> None:
        resolve_entry_model(sample_entry)
        assert sample_entry.resolved_at is None

    def test_preserves_other_fields(self, sample_entry: MemoryEntry) -> None:
        resolved = resolve_entry_model(sample_entry)
        assert resolved.id == sample_entry.id
        assert resolved.category == sample_entry.category
        assert resolved.content == sample_entry.content
        assert resolved.created_at == sample_entry.created_at
        assert resolved.metadata == sample_entry.metadata


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    """Verify serialize/deserialize round-trip."""

    def test_round_trip(self, sample_entry: MemoryEntry) -> None:
        entries = {sample_entry.id: sample_entry}
        raw = serialize_entries(entries)
        restored = deserialize_entries(raw)
        assert sample_entry.id in restored
        assert restored[sample_entry.id].content == sample_entry.content

    def test_deserialize_rejects_missing_entries_key(self) -> None:
        with pytest.raises(ValueError, match="top-level 'entries' key"):
            deserialize_entries('{"items": []}')

    def test_deserialize_empty_list(self) -> None:
        result = deserialize_entries('{"entries": []}')
        assert result == {}

    def test_multiple_entries_round_trip(self) -> None:
        entries: dict[str, MemoryEntry] = {}
        for cat in ["commitment", "deadline", "blocker"]:
            entry = build_entry(cat, f"test {cat}", {})
            entries[entry.id] = entry
        raw = serialize_entries(entries)
        restored = deserialize_entries(raw)
        assert len(restored) == 3
