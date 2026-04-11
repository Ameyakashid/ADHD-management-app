"""Integration tests for the buffer hook pipeline.

End-to-end: create buffer → due date arrives → auto-decrement → alert surfaces.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from buffer_store import BufferStore
from buffer_hook import BufferHook


TODAY = date(2026, 4, 10)
SYSTEM_PROMPT = "# Soul\n\nYou are a helpful assistant.\n\n## Buffer System\n\nGuidance here."


@dataclass
class MockHookContext:
    messages: list[dict[str, str]] = field(default_factory=list)


def _run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


class TestBufferPipeline:
    """Full pipeline: create → due → decrement → alert."""

    def test_buffer_created_then_due_then_decremented_and_alerted(
        self, tmp_path: Path
    ) -> None:
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Rent", 2, 4, 30, TODAY, 2)
        assert buf.buffer_level == 2
        assert buf.next_due_date == TODAY

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=lambda: True,
            get_current_date=lambda: TODAY,
        )

        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))

        updated = store.get_buffer(buf.id)
        assert updated.buffer_level == 1
        assert updated.next_due_date == TODAY + timedelta(days=30)

        # Alert injected because 1 <= alert_threshold(2)
        assert "## Buffer Alerts" in ctx.messages[0]["content"]
        assert "Rent" in ctx.messages[0]["content"]
        assert "1/4" in ctx.messages[0]["content"]

    def test_buffer_not_due_no_decrement_no_alert(
        self, tmp_path: Path
    ) -> None:
        store = BufferStore(tmp_path / "buf.json")
        future = TODAY + timedelta(days=15)
        buf = store.create_buffer("Sub", 4, 4, 30, future, 1)

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=lambda: True,
            get_current_date=lambda: TODAY,
        )
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))

        assert store.get_buffer(buf.id).buffer_level == 4
        assert ctx.messages[0]["content"] == SYSTEM_PROMPT

    def test_level_zero_alerts_without_decrement(
        self, tmp_path: Path
    ) -> None:
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Meds", 0, 4, 7, TODAY, 1)

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=lambda: True,
            get_current_date=lambda: TODAY,
        )
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))

        assert store.get_buffer(buf.id).buffer_level == 0
        assert store.get_buffer(buf.id).next_due_date == TODAY
        assert "## Buffer Alerts" in ctx.messages[0]["content"]
        assert "0/4" in ctx.messages[0]["content"]

    def test_multiple_buffers_mixed_states(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        rent = store.create_buffer("Rent", 2, 4, 30, TODAY, 2)
        meds = store.create_buffer("Meds", 0, 4, 7, TODAY, 1)
        sub = store.create_buffer(
            "Netflix", 4, 4, 30, TODAY + timedelta(days=20), 1
        )

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=lambda: True,
            get_current_date=lambda: TODAY,
        )
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))

        # Rent decremented: 2 → 1, still below threshold(2) → alert
        assert store.get_buffer(rent.id).buffer_level == 1
        # Meds at 0 → not decremented, alert
        assert store.get_buffer(meds.id).buffer_level == 0
        # Netflix not due → untouched, above threshold → no alert
        assert store.get_buffer(sub.id).buffer_level == 4

        content = ctx.messages[0]["content"]
        assert "Rent" in content
        assert "Meds" in content
        assert "Netflix" not in content

    def test_staleness_across_two_heartbeat_ticks(
        self, tmp_path: Path
    ) -> None:
        """Two heartbeat ticks on same date — second should not decrement again."""
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Rent", 3, 4, 30, TODAY, 2)

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=lambda: True,
            get_current_date=lambda: TODAY,
        )

        # Tick 1
        ctx1 = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx1))
        assert store.get_buffer(buf.id).buffer_level == 2

        # Tick 2 — same date, next_due_date now in future
        ctx2 = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx2))
        assert store.get_buffer(buf.id).buffer_level == 2

    def test_multi_period_overdue_single_decrement_per_tick(
        self, tmp_path: Path
    ) -> None:
        """Buffer overdue by multiple periods — only one decrement per tick."""
        overdue_date = TODAY - timedelta(days=20)
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Rent", 3, 4, 7, overdue_date, 2)

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=lambda: True,
            get_current_date=lambda: TODAY,
        )

        # Tick 1: decrement once, next_due_date advances by 7
        ctx1 = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx1))
        updated = store.get_buffer(buf.id)
        assert updated.buffer_level == 2
        assert updated.next_due_date == overdue_date + timedelta(days=7)

        # Still overdue (overdue_date+7 = TODAY-13, still <= TODAY)
        # Tick 2: decrement again
        ctx2 = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx2))
        updated2 = store.get_buffer(buf.id)
        assert updated2.buffer_level == 1
        assert updated2.next_due_date == overdue_date + timedelta(days=14)

    def test_alert_text_is_adhd_friendly(self, tmp_path: Path) -> None:
        """Alert text should be factual, not guilt-inducing or panicky."""
        store = BufferStore(tmp_path / "buf.json")
        store.create_buffer("Rent", 1, 4, 30, TODAY, 2)

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=lambda: True,
            get_current_date=lambda: TODAY,
        )
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))

        content = ctx.messages[0]["content"]
        banned_phrases = [
            "running out", "urgent", "WARNING", "CRITICAL",
            "you must", "overdue", "late", "failed",
        ]
        for phrase in banned_phrases:
            assert phrase.lower() not in content.lower(), (
                f"Alert contains banned phrase: '{phrase}'"
            )

    def test_paused_buffer_ignored(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        from buffer_store import BufferUpdate
        buf = store.create_buffer("Rent", 1, 4, 30, TODAY, 2)
        store.update_buffer(buf.id, BufferUpdate(status="paused"))

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=lambda: True,
            get_current_date=lambda: TODAY,
        )
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))

        assert ctx.messages[0]["content"] == SYSTEM_PROMPT
