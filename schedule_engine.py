"""State-aware scheduling logic for the ADHD assistant.

Pure decision layer: given a check-in type and cognitive state, returns an
action (fire/defer/modify/suppress). Also assembles the data context each
check-in type needs from TaskStore and MemoryEntryStore.
"""

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from checkin_schedule import CheckInType
from memory_store import MemoryCategory, MemoryEntry, MemoryEntryStore
from state_detection import StateName
from task_store import Task, TaskStore

ScheduleActionType = Literal["fire", "defer", "modify", "suppress"]

PRIORITY_SORT_KEY: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ScheduleAction(BaseModel):
    """Result of evaluating a check-in against the current cognitive state."""

    action: ScheduleActionType
    reason: str
    modified_scope: str | None = None


class CheckInContext(BaseModel):
    """Assembled data a check-in needs to render its content."""

    checkin_type: CheckInType
    pending_tasks: list[Task] = Field(default_factory=list)
    in_progress_tasks: list[Task] = Field(default_factory=list)
    completed_today_tasks: list[Task] = Field(default_factory=list)
    overdue_tasks: list[Task] = Field(default_factory=list)
    deadline_memories: list[MemoryEntry] = Field(default_factory=list)
    energy_memories: list[MemoryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def sort_tasks_by_priority(tasks: list[Task]) -> list[Task]:
    """Sort tasks by priority (high first), then by due date (earliest first).

    Tasks with due dates sort before those without within the same priority.
    """
    max_dt = datetime.max.replace(tzinfo=timezone.utc)
    return sorted(
        tasks,
        key=lambda t: (
            PRIORITY_SORT_KEY[t.priority],
            0 if t.due_date is not None else 1,
            t.due_date or max_dt,
        ),
    )


def filter_tasks_completed_today(
    tasks: list[Task],
    today: date,
) -> list[Task]:
    """Return tasks whose updated_at date matches today."""
    return [t for t in tasks if t.updated_at.date() == today]


def filter_overdue_tasks(
    tasks: list[Task],
    today: date,
) -> list[Task]:
    """Return pending tasks whose due_date is before today."""
    return [
        t for t in tasks
        if t.due_date is not None and t.due_date.date() < today
    ]


# ---------------------------------------------------------------------------
# State × check-in evaluation
# ---------------------------------------------------------------------------

def evaluate_checkin(
    checkin_type: CheckInType,
    cognitive_state: StateName,
) -> ScheduleAction:
    """Decide what action to take for a check-in given the cognitive state.

    Implements the 6-state × 4-type decision matrix.
    """
    if cognitive_state in ("baseline", "focus"):
        return ScheduleAction(
            action="fire",
            reason=f"{cognitive_state} state — proceed normally",
        )

    if cognitive_state == "hyperfocus":
        if checkin_type == "evening_review":
            return ScheduleAction(
                action="fire",
                reason="evening review fires even during hyperfocus",
            )
        return ScheduleAction(
            action="suppress",
            reason="hyperfocus — avoid interrupting flow",
        )

    if cognitive_state == "avoidance":
        if checkin_type == "morning_motivation":
            return ScheduleAction(
                action="fire",
                reason="ICNU motivation framing for avoidance",
            )
        if checkin_type == "evening_review":
            return ScheduleAction(
                action="fire",
                reason="evening review fires during avoidance",
            )
        return ScheduleAction(
            action="modify",
            reason="avoidance — reduce task scope",
            modified_scope="reduced",
        )

    if cognitive_state == "overwhelm":
        if checkin_type == "morning_motivation":
            return ScheduleAction(
                action="fire",
                reason="motivation fires normally during overwhelm",
            )
        return ScheduleAction(
            action="modify",
            reason="overwhelm — limit to single item",
            modified_scope="single_item",
        )

    # rsd
    if checkin_type == "morning_motivation":
        return ScheduleAction(
            action="fire",
            reason="gentle emotional check-in for RSD",
        )
    return ScheduleAction(
        action="suppress",
        reason="RSD — suppress task-related check-ins",
    )


# ---------------------------------------------------------------------------
# Check-in content assembly
# ---------------------------------------------------------------------------

def assemble_checkin_context(
    checkin_type: CheckInType,
    task_store: TaskStore,
    memory_store: MemoryEntryStore,
    today: date,
) -> CheckInContext:
    """Gather the data a check-in type needs to render its content.

    Reads from stores (read-only) but mutates nothing. The caller provides
    today as a local-time date; UTC→local conversion is the caller's concern.
    """
    if checkin_type == "morning_motivation":
        return CheckInContext(checkin_type=checkin_type)

    if checkin_type == "morning_plan":
        pending = sort_tasks_by_priority(
            task_store.list_tasks_by_status("pending"),
        )
        deadlines = memory_store.list_entries_by_category("deadline")
        return CheckInContext(
            checkin_type=checkin_type,
            pending_tasks=pending,
            deadline_memories=deadlines,
        )

    if checkin_type == "afternoon_check":
        in_progress = task_store.list_tasks_by_status("in_progress")
        energy = memory_store.list_entries_by_category("energy_state")
        return CheckInContext(
            checkin_type=checkin_type,
            in_progress_tasks=in_progress,
            energy_memories=energy,
        )

    # evening_review
    done_tasks = task_store.list_tasks_by_status("done")
    completed_today = filter_tasks_completed_today(done_tasks, today)
    pending_tasks = task_store.list_tasks_by_status("pending")
    overdue = filter_overdue_tasks(pending_tasks, today)
    return CheckInContext(
        checkin_type=checkin_type,
        completed_today_tasks=completed_today,
        overdue_tasks=overdue,
    )
