"""Nanobot-ai tool wrappers for TaskStore CRUD operations.

Exposes five LLM-callable tools: create_task, list_tasks, get_task,
update_task, complete_task. Each tool delegates to a shared TaskStore
instance and returns LLM-readable string results.

Registration: call register_task_tools(registry, store) at startup.
There is no config.json.template mechanism for custom Python tools
in nanobot-ai v0.1.5 — registration is programmatic only.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.schema import (
    ArraySchema,
    StringSchema,
    tool_parameters_schema,
)

from task_store import Task, TaskStore, TaskUpdate

log = logging.getLogger(__name__)

TaskStatus = Literal["pending", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_task(task: Task) -> str:
    """Format a single task for LLM consumption."""
    lines = [
        f"[{task.id[:8]}] {task.title}",
        f"  Status: {task.status} | Priority: {task.priority}",
    ]
    if task.description:
        lines.append(f"  Description: {task.description}")
    if task.due_date:
        lines.append(f"  Due: {task.due_date.isoformat()}")
    if task.tags:
        lines.append(f"  Tags: {', '.join(task.tags)}")
    return "\n".join(lines)


def format_task_list(tasks: list[Task]) -> str:
    """Format multiple tasks for LLM consumption."""
    if not tasks:
        return "No tasks found."
    return "\n\n".join(format_task(t) for t in tasks)


def parse_iso_date(value: str) -> datetime:
    """Parse an ISO 8601 date string to a timezone-aware datetime.

    Raises ValueError with a clear message if parsing fails.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"Invalid date format: '{value}'. "
            "Expected ISO 8601 format (e.g. '2025-12-31' or '2025-12-31T14:00:00Z')."
        ) from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ---------------------------------------------------------------------------
# Tool classes
# ---------------------------------------------------------------------------

@tool_parameters(
    tool_parameters_schema(
        title=StringSchema("The task title — a short description of what needs to be done"),
        priority=StringSchema(
            "Task priority level",
            enum=["low", "medium", "high"],
        ),
        description=StringSchema(
            "Optional longer description with details about the task",
            nullable=True,
        ),
        due_date=StringSchema(
            "Optional due date in ISO 8601 format (e.g. '2025-12-31' or '2025-12-31T14:00:00Z')",
            nullable=True,
        ),
        tags=ArraySchema(
            StringSchema("A tag label"),
            description="Optional list of tags for categorization",
        ),
        required=["title", "priority"],
    )
)
class CreateTaskTool(Tool):
    """Tool to create a new task."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "create_task"

    @property
    def description(self) -> str:
        return (
            "Create a new task with a title, priority (low/medium/high), "
            "and optional description, due date, and tags."
        )

    async def execute(
        self,
        title: str,
        priority: str,
        description: str | None = None,
        due_date: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        parsed_due: datetime | None = None
        if due_date is not None:
            try:
                parsed_due = parse_iso_date(due_date)
            except ValueError as exc:
                return f"Error: {exc}"

        task = self._store.create_task(
            title=title,
            priority=priority,  # type: ignore[arg-type]
            description=description,
            due_date=parsed_due,
            tags=tags or [],
        )
        return f"Task created:\n{format_task(task)}"


@tool_parameters(
    tool_parameters_schema(
        status=StringSchema(
            "Optional filter by status",
            enum=["pending", "in_progress", "done"],
            nullable=True,
        ),
    )
)
class ListTasksTool(Tool):
    """Tool to list tasks, optionally filtered by status."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "list_tasks"

    @property
    def description(self) -> str:
        return (
            "List all tasks, optionally filtered by status "
            "(pending, in_progress, or done)."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, status: str | None = None) -> str:
        if status is not None:
            tasks = self._store.list_tasks_by_status(status)  # type: ignore[arg-type]
        else:
            tasks = self._store.list_tasks()
        return format_task_list(tasks)


@tool_parameters(
    tool_parameters_schema(
        task_id=StringSchema("The full hex ID of the task to retrieve"),
        required=["task_id"],
    )
)
class GetTaskTool(Tool):
    """Tool to retrieve a single task by ID."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "get_task"

    @property
    def description(self) -> str:
        return "Get the full details of a single task by its ID."

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, task_id: str) -> str:
        try:
            task = self._store.get_task(task_id)
        except KeyError:
            return (
                f"Error: Task not found: '{task_id}'. "
                f"The store contains {len(self._store.list_tasks())} task(s)."
            )
        return format_task(task)


@tool_parameters(
    tool_parameters_schema(
        task_id=StringSchema("The full hex ID of the task to update"),
        title=StringSchema("New title for the task", nullable=True),
        description=StringSchema("New description for the task", nullable=True),
        status=StringSchema(
            "New status for the task",
            enum=["pending", "in_progress", "done"],
            nullable=True,
        ),
        priority=StringSchema(
            "New priority for the task",
            enum=["low", "medium", "high"],
            nullable=True,
        ),
        due_date=StringSchema(
            "New due date in ISO 8601 format, or null to clear",
            nullable=True,
        ),
        tags=ArraySchema(
            StringSchema("A tag label"),
            description="New tags list (replaces existing tags)",
            nullable=True,
        ),
        required=["task_id"],
    )
)
class UpdateTaskTool(Tool):
    """Tool to update fields on an existing task."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "update_task"

    @property
    def description(self) -> str:
        return (
            "Update one or more fields on an existing task. "
            "Only provide the fields you want to change."
        )

    async def execute(
        self,
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        due_date: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        parsed_due: datetime | None = None
        has_due_date = due_date is not None
        if has_due_date:
            try:
                parsed_due = parse_iso_date(due_date)  # type: ignore[arg-type]
            except ValueError as exc:
                return f"Error: {exc}"

        updates = TaskUpdate(
            **({"title": title} if title is not None else {}),
            **({"description": description} if description is not None else {}),
            **({"status": status} if status is not None else {}),  # type: ignore[dict-item]
            **({"priority": priority} if priority is not None else {}),  # type: ignore[dict-item]
            **({"due_date": parsed_due} if has_due_date else {}),
            **({"tags": tags} if tags is not None else {}),
        )

        try:
            task = self._store.update_task(task_id, updates)
        except KeyError:
            return (
                f"Error: Task not found: '{task_id}'. "
                f"The store contains {len(self._store.list_tasks())} task(s)."
            )
        return f"Task updated:\n{format_task(task)}"


@tool_parameters(
    tool_parameters_schema(
        task_id=StringSchema("The full hex ID of the task to mark as done"),
        required=["task_id"],
    )
)
class CompleteTaskTool(Tool):
    """Tool to mark a task as done."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "complete_task"

    @property
    def description(self) -> str:
        return "Mark a task as done by its ID."

    async def execute(self, task_id: str) -> str:
        try:
            task = self._store.mark_complete(task_id)
        except KeyError:
            return (
                f"Error: Task not found: '{task_id}'. "
                f"The store contains {len(self._store.list_tasks())} task(s)."
            )
        return f"Task completed:\n{format_task(task)}"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_task_tools(registry: ToolRegistry, store: TaskStore) -> None:
    """Register all task CRUD tools into a ToolRegistry.

    Call this at startup after constructing the ToolRegistry and TaskStore.
    Example:
        store = TaskStore(Path("~/.nanobot/workspace/tasks.json"))
        register_task_tools(loop.tools, store)
    """
    registry.register(CreateTaskTool(store=store))
    registry.register(ListTasksTool(store=store))
    registry.register(GetTaskTool(store=store))
    registry.register(UpdateTaskTool(store=store))
    registry.register(CompleteTaskTool(store=store))
    log.info("Registered 5 task tools: create, list, get, update, complete")
