"""Tests for scheduling hook — pure functions, hook lifecycle, and workspace content."""

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest

from checkin_schedule import CheckInScheduleStore
from memory_store import MemoryEntry, MemoryEntryStore
from scheduling_hook import (
    CHECKIN_DISPLAY_NAMES,
    SchedulingHook,
    format_checkin_prompt,
    format_task_summary,
    inject_checkin_into_prompt,
)
from schedule_engine import CheckInContext, ScheduleAction
from task_store import Task, TaskStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SOUL_PATH = REPO_ROOT / "workspace" / "SOUL.md"
HEARTBEAT_PATH = REPO_ROOT / "workspace" / "HEARTBEAT.md"

SYSTEM_PROMPT = "# Soul\n\nYou are an assistant.\n\n## Scheduled Check-Ins\n\nGuidance here."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class MockHookContext:
    messages: list[dict[str, str]] = field(default_factory=list)


def _make_task(
    title: str,
    status: str,
    priority: str,
    due_date: datetime | None,
) -> Task:
    now = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    return Task(
        id=title.lower().replace(" ", "_"),
        title=title,
        status=status,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
        due_date=due_date,
    )


def _make_memory(category: str, content: str) -> MemoryEntry:
    return MemoryEntry(
        id="abcdef1234567890abcdef1234567890",
        category=category,  # type: ignore[arg-type]
        content=content,
        created_at=datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc),
        metadata={},
    )


def _run(coro: object) -> object:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# format_task_summary
# ---------------------------------------------------------------------------

class TestFormatTaskSummary:

    def test_empty_context(self) -> None:
        ctx = CheckInContext(checkin_type="morning_motivation")
        assert format_task_summary(ctx) == []

    def test_pending_tasks(self) -> None:
        ctx = CheckInContext(
            checkin_type="morning_plan",
            pending_tasks=[
                _make_task("Fix bug", "pending", "high", None),
                _make_task("Write docs", "pending", "low", None),
            ],
        )
        lines = format_task_summary(ctx)
        assert len(lines) == 1
        assert "2 pending" in lines[0]
        assert "Fix bug" in lines[0]

    def test_in_progress_tasks(self) -> None:
        ctx = CheckInContext(
            checkin_type="afternoon_check",
            in_progress_tasks=[
                _make_task("API work", "in_progress", "medium", None),
            ],
        )
        lines = format_task_summary(ctx)
        assert len(lines) == 1
        assert "API work" in lines[0]

    def test_completed_and_overdue(self) -> None:
        ctx = CheckInContext(
            checkin_type="evening_review",
            completed_today_tasks=[
                _make_task("Done task", "done", "low", None),
            ],
            overdue_tasks=[
                _make_task("Late task", "pending", "high", None),
            ],
        )
        lines = format_task_summary(ctx)
        assert len(lines) == 2
        assert "1 completed" in lines[0]
        assert "1 overdue" in lines[1]

    def test_deadline_and_energy_memories(self) -> None:
        ctx = CheckInContext(
            checkin_type="morning_plan",
            deadline_memories=[_make_memory("deadline", "Report due Monday")],
            energy_memories=[_make_memory("energy_state", "Feeling drained")],
        )
        lines = format_task_summary(ctx)
        assert len(lines) == 2
        assert "1 upcoming deadlines" in lines[0]
        assert "Feeling drained" in lines[1]


# ---------------------------------------------------------------------------
# format_checkin_prompt
# ---------------------------------------------------------------------------

class TestFormatCheckinPrompt:

    def test_fire_action_with_context(self) -> None:
        action = ScheduleAction(
            action="fire", reason="baseline state — proceed normally"
        )
        ctx = CheckInContext(
            checkin_type="morning_plan",
            pending_tasks=[_make_task("Top task", "pending", "high", None)],
        )
        result = format_checkin_prompt("morning_plan", action, ctx)
        assert "Morning Plan" in result
        assert "fire" in result
        assert "Top task" in result
        assert "Deliver this check-in" in result

    def test_modify_action_includes_scope(self) -> None:
        action = ScheduleAction(
            action="modify",
            reason="avoidance — reduce task scope",
            modified_scope="reduced",
        )
        ctx = CheckInContext(checkin_type="afternoon_check")
        result = format_checkin_prompt("afternoon_check", action, ctx)
        assert "Modified scope: reduced" in result

    def test_empty_context_no_context_section(self) -> None:
        action = ScheduleAction(
            action="fire", reason="baseline state — proceed normally"
        )
        ctx = CheckInContext(checkin_type="morning_motivation")
        result = format_checkin_prompt("morning_motivation", action, ctx)
        assert "### Context" not in result


# ---------------------------------------------------------------------------
# inject_checkin_into_prompt
# ---------------------------------------------------------------------------

class TestInjectCheckinIntoPrompt:

    def test_appends_block(self) -> None:
        result = inject_checkin_into_prompt("System prompt.", "Check-in block.")
        assert result == "System prompt.\n\nCheck-in block."

    def test_empty_block_returns_original(self) -> None:
        result = inject_checkin_into_prompt("System prompt.", "")
        assert result == "System prompt."


# ---------------------------------------------------------------------------
# SchedulingHook
# ---------------------------------------------------------------------------

class TestSchedulingHook:

    def _make_hook(
        self,
        tmp_path: Path,
        is_scheduled: bool,
        cognitive_state: str,
        current_date: date,
        current_time: time,
    ) -> SchedulingHook:
        schedule_store = CheckInScheduleStore(
            tmp_path / "schedule.json"
        )
        task_store = TaskStore(tmp_path / "tasks.json")
        memory_store = MemoryEntryStore(tmp_path / "memories.json")
        return SchedulingHook(
            schedule_store=schedule_store,
            task_store=task_store,
            memory_store=memory_store,
            is_scheduled_session=lambda: is_scheduled,
            get_cognitive_state=lambda: cognitive_state,
            get_current_date=lambda: current_date,
            get_current_time=lambda: current_time,
        )

    def test_fires_due_checkin(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="baseline",
            current_date=date(2026, 4, 10),
            current_time=time(8, 15),
        )
        ctx = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat task"},
            ]
        )
        _run(hook.before_iteration(ctx))
        assert "Morning Motivation" in ctx.messages[0]["content"]

    def test_skips_non_scheduled_session(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=False,
            cognitive_state="baseline",
            current_date=date(2026, 4, 10),
            current_time=time(8, 15),
        )
        ctx = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "user message"},
            ]
        )
        _run(hook.before_iteration(ctx))
        assert ctx.messages[0]["content"] == SYSTEM_PROMPT

    def test_skips_when_nothing_due(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="baseline",
            current_date=date(2026, 4, 10),
            current_time=time(6, 0),
        )
        ctx = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat task"},
            ]
        )
        _run(hook.before_iteration(ctx))
        assert ctx.messages[0]["content"] == SYSTEM_PROMPT

    def test_suppresses_during_hyperfocus(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="hyperfocus",
            current_date=date(2026, 4, 10),
            current_time=time(9, 30),
        )
        ctx = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat task"},
            ]
        )
        _run(hook.before_iteration(ctx))
        # morning_plan at 09:30 should be suppressed during hyperfocus
        assert "Morning Plan" not in ctx.messages[0]["content"]

    def test_suppress_records_fired(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="hyperfocus",
            current_date=date(2026, 4, 10),
            current_time=time(8, 15),
        )
        ctx = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat"},
            ]
        )
        _run(hook.before_iteration(ctx))
        # morning_motivation at 08:15 during hyperfocus → suppress + record
        entry = hook._schedule_store.get_entry("morning_motivation")
        assert entry.last_run_date == date(2026, 4, 10)

    def test_modify_includes_scope(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="avoidance",
            current_date=date(2026, 4, 10),
            current_time=time(9, 30),
        )
        # Pre-fire morning_motivation so morning_plan is the first due
        hook._schedule_store.record_fired(
            "morning_motivation", date(2026, 4, 10)
        )
        ctx = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat"},
            ]
        )
        _run(hook.before_iteration(ctx))
        # morning_plan + avoidance = modify with reduced scope
        assert "Modified scope: reduced" in ctx.messages[0]["content"]

    def test_records_fired_after_fire(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="baseline",
            current_date=date(2026, 4, 10),
            current_time=time(8, 15),
        )
        ctx = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat"},
            ]
        )
        _run(hook.before_iteration(ctx))
        entry = hook._schedule_store.get_entry("morning_motivation")
        assert entry.last_run_date == date(2026, 4, 10)

    def test_does_not_fire_same_checkin_twice(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="baseline",
            current_date=date(2026, 4, 10),
            current_time=time(8, 15),
        )
        ctx1 = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat"},
            ]
        )
        _run(hook.before_iteration(ctx1))
        assert "Morning Motivation" in ctx1.messages[0]["content"]

        # Second tick at same time — morning_motivation already fired
        ctx2 = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat"},
            ]
        )
        _run(hook.before_iteration(ctx2))
        assert "Morning Motivation" not in ctx2.messages[0]["content"]

    def test_empty_messages_no_crash(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="baseline",
            current_date=date(2026, 4, 10),
            current_time=time(8, 15),
        )
        ctx = MockHookContext(messages=[])
        _run(hook.before_iteration(ctx))

    def test_no_system_message_no_crash(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="baseline",
            current_date=date(2026, 4, 10),
            current_time=time(8, 15),
        )
        ctx = MockHookContext(
            messages=[{"role": "user", "content": "heartbeat"}]
        )
        _run(hook.before_iteration(ctx))

    def test_processes_only_first_due_checkin(self, tmp_path: Path) -> None:
        hook = self._make_hook(
            tmp_path,
            is_scheduled=True,
            cognitive_state="baseline",
            current_date=date(2026, 4, 10),
            current_time=time(9, 30),
        )
        ctx = MockHookContext(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "heartbeat"},
            ]
        )
        _run(hook.before_iteration(ctx))
        content = ctx.messages[0]["content"]
        # At 09:30 both morning_motivation (08:00) and morning_plan (09:00) are due
        # Only one should be injected
        active_count = content.count("## Active Check-In:")
        assert active_count == 1


# ---------------------------------------------------------------------------
# SOUL.md content
# ---------------------------------------------------------------------------

class TestSoulCheckinSection:

    @pytest.fixture(scope="class")
    def soul_content(self) -> str:
        return SOUL_PATH.read_text(encoding="utf-8")

    def test_has_scheduled_checkins_heading(self, soul_content: str) -> None:
        assert "## Scheduled Check-Ins" in soul_content

    @pytest.mark.parametrize("checkin_heading", [
        "### Morning Motivation (08:00)",
        "### Morning Plan (09:00)",
        "### Afternoon Check (14:00)",
        "### Evening Review (20:00)",
    ])
    def test_has_checkin_type_heading(
        self, soul_content: str, checkin_heading: str
    ) -> None:
        assert checkin_heading in soul_content

    def test_morning_motivation_mentions_icnu(self, soul_content: str) -> None:
        section = self._extract("Morning Motivation", soul_content)
        assert "icnu" in section.lower()

    def test_morning_plan_mentions_one_thing(self, soul_content: str) -> None:
        section = self._extract("Morning Plan", soul_content)
        assert "one thing" in section.lower()

    def test_afternoon_check_mentions_energy(self, soul_content: str) -> None:
        section = self._extract("Afternoon Check", soul_content)
        assert "energy" in section.lower()

    def test_evening_review_mentions_went_well(self, soul_content: str) -> None:
        section = self._extract("Evening Review", soul_content)
        assert "went well" in section.lower()

    def test_evening_review_mentions_closure(self, soul_content: str) -> None:
        section = self._extract("Evening Review", soul_content)
        assert "closure" in section.lower() or "wrap up" in section.lower()

    def _extract(self, heading: str, content: str) -> str:
        marker = f"### {heading}"
        start = content.find(marker)
        if start == -1:
            return ""
        start += len(marker)
        next_h3 = content.find("\n### ", start)
        next_h2 = content.find("\n## ", start)
        ends = [e for e in [next_h3, next_h2] if e != -1]
        end = min(ends) if ends else len(content)
        return content[start:end]


# ---------------------------------------------------------------------------
# HEARTBEAT.md content
# ---------------------------------------------------------------------------

class TestHeartbeatContent:

    @pytest.fixture(scope="class")
    def heartbeat_content(self) -> str:
        return HEARTBEAT_PATH.read_text(encoding="utf-8")

    @pytest.mark.parametrize("section", [
        "Morning Motivation",
        "Morning Plan",
        "Afternoon Check",
        "Evening Review",
    ])
    def test_has_all_checkin_sections(
        self, heartbeat_content: str, section: str
    ) -> None:
        assert f"## {section}" in heartbeat_content

    def test_mentions_scheduling_engine(self, heartbeat_content: str) -> None:
        assert "scheduling engine" in heartbeat_content.lower()
