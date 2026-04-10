"""Integration tests for the full task management pipeline.

Tests the end-to-end flow: tool registration, CRUD round-trip via
ToolRegistry.execute(), persistence across TaskStore restarts, and
SOUL.md task management content validation.

SOUL.md tests always run. Tool integration tests require nanobot-ai
(Python 3.11+) and are skipped if the package is unavailable.
"""

import asyncio
import re
from pathlib import Path

import pytest

from task_store import TaskStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SOUL_PATH = REPO_ROOT / "workspace" / "SOUL.md"

BANNED_ROOTS = [
    "you should",
    "just do it",
    "just focus",
    "just try",
    "it's easy",
    "it's simple",
    "it's not that hard",
    "why didn't you",
    "why can't you",
    "you forgot again",
    "you always forget",
    "try harder",
    "you need to try",
    "everyone else can",
    "normal people",
    "you're not trying",
    "you don't care",
    "I already told you",
    "you just need to",
    "all you have to do",
]

try:
    from nanobot.agent.tools.registry import ToolRegistry
    from task_tools import register_task_tools
    HAS_NANOBOT = True
except ImportError:
    HAS_NANOBOT = False

requires_nanobot = pytest.mark.skipif(
    not HAS_NANOBOT,
    reason="nanobot-ai not installed (requires Python 3.11+)",
)


def run(coro):  # noqa: ANN001, ANN201
    """Run an async coroutine synchronously for testing."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# SOUL.md Task Management content tests (always run — no nanobot dependency)
# ---------------------------------------------------------------------------

class TestSoulTaskManagement:
    """Validate the Task Management section exists and follows rules."""

    @pytest.fixture(scope="class")
    def soul_content(self) -> str:
        return SOUL_PATH.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def task_section(self, soul_content: str) -> str:
        match = re.search(
            r"^## Task Management\n(.*?)(?=\n## |\Z)",
            soul_content,
            re.DOTALL | re.MULTILINE,
        )
        assert match, "SOUL.md missing '## Task Management' section"
        return match.group(1)

    def test_section_exists(self, soul_content: str) -> None:
        assert re.search(
            r"^## Task Management", soul_content, re.MULTILINE
        ), "SOUL.md missing '## Task Management' heading"

    def test_has_task_creation_guidance(self, task_section: str) -> None:
        assert "task creation" in task_section.lower()

    def test_has_task_list_guidance(self, task_section: str) -> None:
        assert "list" in task_section.lower()

    def test_has_completion_guidance(self, task_section: str) -> None:
        assert "completion" in task_section.lower()

    def test_has_state_aware_guidance(self, task_section: str) -> None:
        for state in ["Baseline", "Focus", "Hyperfocus", "Avoidance", "Overwhelm", "RSD"]:
            assert f"**{state}**" in task_section, (
                f"Task Management section missing state-aware guidance for {state}"
            )

    def test_references_icnu_for_avoidance(self, task_section: str) -> None:
        avoidance_idx = task_section.find("Avoidance")
        assert avoidance_idx != -1
        avoidance_text = task_section[avoidance_idx:avoidance_idx + 200]
        assert "ICNU" in avoidance_text

    @pytest.mark.parametrize("phrase", BANNED_ROOTS)
    def test_no_banned_phrases(self, task_section: str, phrase: str) -> None:
        assert phrase.lower() not in task_section.lower(), (
            f"Task Management section contains banned phrase: '{phrase}'"
        )


# ---------------------------------------------------------------------------
# Tool integration tests (require nanobot-ai)
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "integration_tasks.json"


@requires_nanobot
class TestCrudCycleViaRegistry:
    """End-to-end create -> list -> update -> complete -> list-done cycle."""

    def test_full_crud_cycle(self, storage_path: Path) -> None:
        store = TaskStore(storage_path)
        registry = ToolRegistry()
        register_task_tools(registry, store)

        create_result = run(registry.execute(
            "create_task",
            {"title": "Integration test task", "priority": "medium"},
        ))
        assert "Task created:" in create_result
        assert "Integration test task" in create_result

        task_id = store.list_tasks()[0].id

        list_result = run(registry.execute("list_tasks", {}))
        assert "Integration test task" in list_result

        get_result = run(registry.execute(
            "get_task", {"task_id": task_id},
        ))
        assert "Integration test task" in get_result

        update_result = run(registry.execute(
            "update_task",
            {"task_id": task_id, "title": "Updated title", "priority": "high"},
        ))
        assert "Task updated:" in update_result
        assert "Updated title" in update_result

        complete_result = run(registry.execute(
            "complete_task", {"task_id": task_id},
        ))
        assert "Task completed:" in complete_result
        assert "done" in complete_result

        done_list = run(registry.execute(
            "list_tasks", {"status": "done"},
        ))
        assert "Updated title" in done_list

        pending_list = run(registry.execute(
            "list_tasks", {"status": "pending"},
        ))
        assert pending_list == "No tasks found."


@requires_nanobot
class TestPersistenceAcrossRestart:
    """Verify tasks survive constructing a new TaskStore + tools."""

    def test_tasks_persist_after_new_store(
        self, storage_path: Path
    ) -> None:
        store_a = TaskStore(storage_path)
        registry_a = ToolRegistry()
        register_task_tools(registry_a, store_a)

        run(registry_a.execute(
            "create_task",
            {"title": "Persistent task", "priority": "high"},
        ))
        run(registry_a.execute(
            "create_task",
            {"title": "Second persistent", "priority": "low"},
        ))

        store_b = TaskStore(storage_path)
        registry_b = ToolRegistry()
        register_task_tools(registry_b, store_b)

        list_result = run(registry_b.execute("list_tasks", {}))
        assert "Persistent task" in list_result
        assert "Second persistent" in list_result

    def test_completed_status_persists(
        self, storage_path: Path
    ) -> None:
        store_a = TaskStore(storage_path)
        registry_a = ToolRegistry()
        register_task_tools(registry_a, store_a)

        run(registry_a.execute(
            "create_task",
            {"title": "Will be done", "priority": "medium"},
        ))
        task_id = store_a.list_tasks()[0].id
        run(registry_a.execute(
            "complete_task", {"task_id": task_id},
        ))

        store_b = TaskStore(storage_path)
        assert store_b.get_task(task_id).status == "done"
