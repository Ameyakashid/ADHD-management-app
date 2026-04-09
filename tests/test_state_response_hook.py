"""Tests for StateResponseHook lifecycle and SOUL.md state rules."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from state_detection import (
    StateConfig,
    load_state_config,
)
from state_response_integration import (
    BASELINE_STATE,
    StateResponseHook,
    build_state_indicator,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
STATES_PATH = REPO_ROOT / "workspace" / "states.yaml"
SOUL_PATH = REPO_ROOT / "workspace" / "SOUL.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def state_config() -> StateConfig:
    return load_state_config(STATES_PATH)


@pytest.fixture(scope="module")
def soul_content() -> str:
    return SOUL_PATH.read_text(encoding="utf-8")


@dataclass
class MockHookContext:
    """Minimal stand-in for nanobot-ai's AgentHookContext."""
    messages: list[dict[str, str]] = field(default_factory=list)


def make_context(
    system_content: str, user_messages: list[str]
) -> MockHookContext:
    """Build a mock context with a system prompt and user messages."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content}
    ]
    for msg in user_messages:
        messages.append({"role": "user", "content": msg})
    return MockHookContext(messages=messages)


def run_async(coro: object) -> object:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# SOUL.md content tests
# ---------------------------------------------------------------------------

class TestSoulStateRules:
    """SOUL.md must have distinct, testable rules for each state."""

    ALL_STATES = ["baseline", "focus", "hyperfocus", "avoidance", "overwhelm", "rsd"]

    @pytest.mark.parametrize("state_name", ALL_STATES)
    def test_soul_has_state_heading(
        self, soul_content: str, state_name: str
    ) -> None:
        heading = f"### {state_name.capitalize()}"
        if state_name == "rsd":
            heading = "### RSD"
        assert heading in soul_content, (
            f"SOUL.md missing state heading: {heading}"
        )

    def test_focus_mentions_concise(self, soul_content: str) -> None:
        focus_section = self._extract_section(soul_content, "Focus")
        assert "concise" in focus_section.lower()

    def test_hyperfocus_mentions_no_interrupt(self, soul_content: str) -> None:
        section = self._extract_section(soul_content, "Hyperfocus")
        assert "not interrupt" in section.lower() or "do not interrupt" in section.lower()

    def test_avoidance_mentions_icnu(self, soul_content: str) -> None:
        section = self._extract_section(soul_content, "Avoidance")
        assert "icnu" in section.lower()

    def test_overwhelm_mentions_one_thing(self, soul_content: str) -> None:
        section = self._extract_section(soul_content, "Overwhelm")
        assert "one" in section.lower()
        assert "single" in section.lower() or "simplify" in section.lower()

    def test_rsd_validates_feelings_first(self, soul_content: str) -> None:
        section = self._extract_section(soul_content, "RSD")
        assert "first" in section.lower()
        assert "emotional" in section.lower() or "feeling" in section.lower()

    def test_rsd_bans_criticism(self, soul_content: str) -> None:
        section = self._extract_section(soul_content, "RSD")
        assert "criticism" in section.lower()

    def test_all_states_have_distinct_content(self, soul_content: str) -> None:
        sections = {}
        for state in self.ALL_STATES:
            heading = state.capitalize() if state != "rsd" else "RSD"
            sections[state] = self._extract_section(soul_content, heading)

        contents = list(sections.values())
        assert len(set(contents)) == len(contents), (
            "Two state sections have identical content"
        )

    def _extract_section(self, content: str, heading: str) -> str:
        """Extract text between ### heading and the next ### or ##."""
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
# Hook integration tests
# ---------------------------------------------------------------------------

class TestStateResponseHook:
    """Integration tests for the StateResponseHook lifecycle."""

    SYSTEM_PROMPT = (
        "# Soul\n\nYou are an assistant.\n\n"
        "## State-Aware Adaptation\n\n"
        "Apply rules based on detected state.\n\n"
        "### Baseline\n- Normal voice\n\n"
        "### Focus\n- Be concise\n\n"
        "## Personality Voices\n\nReserved."
    )

    def _make_hook(
        self, state_config: StateConfig, response: str
    ) -> StateResponseHook:
        async def mock_llm(prompt: str) -> str:
            return response

        return StateResponseHook(config=state_config, llm_call=mock_llm)

    def test_injects_state_on_first_message(
        self, state_config: StateConfig
    ) -> None:
        hook = self._make_hook(state_config, "focus")
        ctx = make_context(self.SYSTEM_PROMPT, ["Working on the API now"])

        run_async(hook.before_iteration(ctx))

        assert build_state_indicator("focus") in ctx.messages[0]["content"]

    def test_state_persists_across_calls(
        self, state_config: StateConfig
    ) -> None:
        responses = iter(["focus", "focus"])

        async def mock_llm(prompt: str) -> str:
            return next(responses)

        hook = StateResponseHook(config=state_config, llm_call=mock_llm)

        ctx1 = make_context(self.SYSTEM_PROMPT, ["Starting work"])
        run_async(hook.before_iteration(ctx1))
        assert hook.current_state == "focus"

        ctx2 = make_context(self.SYSTEM_PROMPT, ["Making progress"])
        run_async(hook.before_iteration(ctx2))
        assert hook.current_state == "focus"

    def test_state_transitions_between_messages(
        self, state_config: StateConfig
    ) -> None:
        responses = iter(["focus", "avoidance"])

        async def mock_llm(prompt: str) -> str:
            return next(responses)

        hook = StateResponseHook(config=state_config, llm_call=mock_llm)

        ctx1 = make_context(self.SYSTEM_PROMPT, ["Getting stuff done"])
        run_async(hook.before_iteration(ctx1))
        assert hook.current_state == "focus"

        ctx2 = make_context(self.SYSTEM_PROMPT, ["I know I need to but..."])
        run_async(hook.before_iteration(ctx2))
        assert hook.current_state == "avoidance"

    def test_falls_back_to_baseline_on_detection_error(
        self, state_config: StateConfig
    ) -> None:
        async def failing_llm(prompt: str) -> str:
            raise ValueError("LLM returned garbage")

        hook = StateResponseHook(config=state_config, llm_call=failing_llm)
        ctx = make_context(self.SYSTEM_PROMPT, ["hello there"])

        run_async(hook.before_iteration(ctx))

        assert hook.current_state == BASELINE_STATE
        assert build_state_indicator(BASELINE_STATE) in ctx.messages[0]["content"]

    def test_falls_back_on_unexpected_exception(
        self, state_config: StateConfig
    ) -> None:
        async def exploding_llm(prompt: str) -> str:
            raise RuntimeError("Connection lost")

        hook = StateResponseHook(config=state_config, llm_call=exploding_llm)
        ctx = make_context(self.SYSTEM_PROMPT, ["test message"])

        run_async(hook.before_iteration(ctx))

        assert hook.current_state == BASELINE_STATE

    def test_does_nothing_with_empty_messages(
        self, state_config: StateConfig
    ) -> None:
        hook = self._make_hook(state_config, "focus")
        ctx = MockHookContext(messages=[])

        run_async(hook.before_iteration(ctx))

        assert hook.current_state == BASELINE_STATE

    def test_does_nothing_without_user_message(
        self, state_config: StateConfig
    ) -> None:
        hook = self._make_hook(state_config, "focus")
        ctx = MockHookContext(
            messages=[{"role": "system", "content": self.SYSTEM_PROMPT}]
        )

        run_async(hook.before_iteration(ctx))

        assert hook.current_state == BASELINE_STATE

    def test_does_not_mutate_original_system_message(
        self, state_config: StateConfig
    ) -> None:
        hook = self._make_hook(state_config, "overwhelm")
        original_content = self.SYSTEM_PROMPT
        ctx = make_context(original_content, ["everything is too much"])

        run_async(hook.before_iteration(ctx))

        assert ctx.messages[0]["content"] != original_content
        assert build_state_indicator("overwhelm") in ctx.messages[0]["content"]

    def test_initial_state_is_baseline(
        self, state_config: StateConfig
    ) -> None:
        hook = self._make_hook(state_config, "baseline")
        assert hook.current_state == BASELINE_STATE

    @pytest.mark.parametrize("state_name", [
        "baseline", "focus", "hyperfocus", "avoidance", "overwhelm", "rsd"
    ])
    def test_each_state_produces_distinct_indicator(
        self, state_config: StateConfig, state_name: str
    ) -> None:
        hook = self._make_hook(state_config, state_name)
        ctx = make_context(self.SYSTEM_PROMPT, ["test message"])

        run_async(hook.before_iteration(ctx))

        expected = build_state_indicator(state_name)
        assert expected in ctx.messages[0]["content"]

    def test_blocked_transition_keeps_current_state(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "hyperfocus"

        hook = StateResponseHook(config=state_config, llm_call=mock_llm)
        hook._current_state = "overwhelm"

        ctx = make_context(self.SYSTEM_PROMPT, ["I'm in the zone"])
        run_async(hook.before_iteration(ctx))

        assert hook.current_state == "overwhelm"
        assert build_state_indicator("overwhelm") in ctx.messages[0]["content"]
