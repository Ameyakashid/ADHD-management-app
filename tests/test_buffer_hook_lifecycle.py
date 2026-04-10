"""Tests for buffer hook — hook lifecycle, decrement, alerts, workspace."""

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from buffer_store import BufferStore
from buffer_hook import BufferHook

REPO_ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_PATH = REPO_ROOT / "workspace" / "HEARTBEAT.md"

SYSTEM_PROMPT = "# Soul\n\nYou are an assistant."
TODAY = date(2026, 4, 10)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class MockHookContext:
    messages: list[dict[str, str]] = field(default_factory=list)


def _run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


def _make_hook(
    store: BufferStore,
    is_scheduled: bool = True,
    current_date: date = TODAY,
) -> BufferHook:
    return BufferHook(
        buffer_store=store,
        is_scheduled_session=lambda: is_scheduled,
        get_current_date=lambda: current_date,
    )


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestBufferHookGuards:

    def test_empty_messages_noop(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        hook = _make_hook(store)
        ctx = MockHookContext(messages=[])
        _run(hook.before_iteration(ctx))
        assert ctx.messages == []

    def test_not_scheduled_noop(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        hook = _make_hook(store, is_scheduled=False)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        assert ctx.messages[0]["content"] == SYSTEM_PROMPT

    def test_non_system_first_message_noop(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "user", "content": "hello"}]
        )
        _run(hook.before_iteration(ctx))
        assert ctx.messages[0]["content"] == "hello"

    def test_no_active_buffers_noop(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        assert ctx.messages[0]["content"] == SYSTEM_PROMPT

    def test_exception_does_not_propagate(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")

        def exploding() -> bool:
            raise RuntimeError("boom")

        hook = BufferHook(
            buffer_store=store,
            is_scheduled_session=exploding,  # type: ignore[arg-type]
            get_current_date=lambda: TODAY,
        )
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        assert ctx.messages[0]["content"] == SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Auto-decrement
# ---------------------------------------------------------------------------

class TestBufferHookDecrement:

    def test_due_buffer_gets_decremented(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Rent", 3, 4, 30, TODAY, 2)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        updated = store.get_buffer(buf.id)
        assert updated.buffer_level == 2
        assert updated.next_due_date == TODAY + timedelta(days=30)

    def test_level_zero_not_decremented(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Meds", 0, 4, 7, TODAY, 1)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        updated = store.get_buffer(buf.id)
        assert updated.buffer_level == 0
        assert updated.next_due_date == TODAY

    def test_staleness_guard_prevents_double_decrement(
        self, tmp_path: Path
    ) -> None:
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Rent", 3, 4, 30, TODAY, 2)
        hook = _make_hook(store)

        ctx1 = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx1))
        assert store.get_buffer(buf.id).buffer_level == 2

        ctx2 = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx2))
        assert store.get_buffer(buf.id).buffer_level == 2

    def test_overdue_buffer_decremented(self, tmp_path: Path) -> None:
        past = TODAY - timedelta(days=3)
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Sub", 2, 3, 7, past, 1)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        updated = store.get_buffer(buf.id)
        assert updated.buffer_level == 1
        assert updated.next_due_date == past + timedelta(days=7)

    def test_multiple_due_buffers_all_decremented(
        self, tmp_path: Path
    ) -> None:
        store = BufferStore(tmp_path / "buf.json")
        buf1 = store.create_buffer("Rent", 3, 4, 30, TODAY, 2)
        buf2 = store.create_buffer("Meds", 2, 4, 7, TODAY, 1)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        assert store.get_buffer(buf1.id).buffer_level == 2
        assert store.get_buffer(buf2.id).buffer_level == 1


# ---------------------------------------------------------------------------
# Alert injection
# ---------------------------------------------------------------------------

class TestBufferHookAlerts:

    def test_alert_injected_when_below_threshold(
        self, tmp_path: Path
    ) -> None:
        store = BufferStore(tmp_path / "buf.json")
        store.create_buffer("Rent", 1, 4, 30, TODAY, 2)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        assert "## Buffer Alerts" in ctx.messages[0]["content"]
        assert "Rent" in ctx.messages[0]["content"]

    def test_no_alert_when_healthy(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        future = TODAY + timedelta(days=20)
        store.create_buffer("Rent", 4, 4, 30, future, 1)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        assert ctx.messages[0]["content"] == SYSTEM_PROMPT

    def test_level_zero_generates_alert(self, tmp_path: Path) -> None:
        store = BufferStore(tmp_path / "buf.json")
        store.create_buffer("Meds", 0, 4, 7, TODAY, 1)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        content = ctx.messages[0]["content"]
        assert "## Buffer Alerts" in content
        assert "Meds" in content
        assert "0/4" in content

    def test_alert_reflects_post_decrement_level(
        self, tmp_path: Path
    ) -> None:
        """Buffer at level 2 with threshold 1: decrement to 1 triggers alert."""
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Rent", 2, 4, 30, TODAY, 1)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        assert store.get_buffer(buf.id).buffer_level == 1
        assert "## Buffer Alerts" in ctx.messages[0]["content"]
        assert "Rent" in ctx.messages[0]["content"]

    def test_no_alert_post_decrement_still_above(
        self, tmp_path: Path
    ) -> None:
        """Buffer at level 3 with threshold 1: decrement to 2, no alert."""
        store = BufferStore(tmp_path / "buf.json")
        buf = store.create_buffer("Rent", 3, 4, 30, TODAY, 1)
        hook = _make_hook(store)
        ctx = MockHookContext(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
        _run(hook.before_iteration(ctx))
        assert store.get_buffer(buf.id).buffer_level == 2
        assert ctx.messages[0]["content"] == SYSTEM_PROMPT

    def test_prompt_uses_spread_copy(self, tmp_path: Path) -> None:
        """messages[0] is replaced via spread, not mutated in place."""
        store = BufferStore(tmp_path / "buf.json")
        store.create_buffer("Low", 1, 4, 30, TODAY, 1)
        hook = _make_hook(store)
        original_msg = {"role": "system", "content": SYSTEM_PROMPT}
        ctx = MockHookContext(messages=[original_msg])
        _run(hook.before_iteration(ctx))
        assert ctx.messages[0] is not original_msg
        assert ctx.messages[0]["role"] == "system"


# ---------------------------------------------------------------------------
# Workspace content
# ---------------------------------------------------------------------------

class TestHeartbeatContent:

    def test_heartbeat_has_buffer_section(self) -> None:
        content = HEARTBEAT_PATH.read_text(encoding="utf-8")
        assert "## Buffer Monitoring" in content
        assert "auto-decrement" in content.lower()
        assert "alert_threshold" in content
