"""Tests for state detection — prompt building, LLM normalization, and detection."""

import asyncio
from pathlib import Path

import pytest

from state_detection import (
    ALL_STATES,
    DetectionResult,
    StateConfig,
    build_classification_prompt,
    detect_state,
    enforce_transition,
    load_state_config,
    normalize_llm_response,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
STATES_PATH = REPO_ROOT / "workspace" / "states.yaml"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def state_config() -> StateConfig:
    return load_state_config(STATES_PATH)


# ---------------------------------------------------------------------------
# Prompt construction tests
# ---------------------------------------------------------------------------

class TestPromptConstruction:
    """Verify classification prompt includes required elements."""

    def test_prompt_includes_current_state(
        self, state_config: StateConfig
    ) -> None:
        prompt = build_classification_prompt("hello", "baseline", state_config)
        assert "Current state: baseline" in prompt

    def test_prompt_includes_user_message(
        self, state_config: StateConfig
    ) -> None:
        prompt = build_classification_prompt(
            "I can't start anything", "baseline", state_config
        )
        assert "I can't start anything" in prompt

    def test_prompt_includes_all_state_names(
        self, state_config: StateConfig
    ) -> None:
        prompt = build_classification_prompt("test", "baseline", state_config)
        for state_name in ALL_STATES:
            assert state_name in prompt, (
                f"Prompt missing state name: {state_name}"
            )

    def test_prompt_includes_detection_signals(
        self, state_config: StateConfig
    ) -> None:
        prompt = build_classification_prompt("test", "baseline", state_config)
        for state in state_config.states.values():
            assert state.detection_signals[0] in prompt

    def test_prompt_requests_single_word_response(
        self, state_config: StateConfig
    ) -> None:
        prompt = build_classification_prompt("test", "baseline", state_config)
        assert "ONLY the state name" in prompt


# ---------------------------------------------------------------------------
# LLM response normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeLlmResponse:
    """Verify raw LLM output is correctly normalized to state names."""

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_exact_match(self, state_name: str) -> None:
        assert normalize_llm_response(state_name) == state_name

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_with_whitespace(self, state_name: str) -> None:
        assert normalize_llm_response(f"  {state_name}  \n") == state_name

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_with_caps(self, state_name: str) -> None:
        assert normalize_llm_response(state_name.upper()) == state_name

    def test_with_trailing_period(self) -> None:
        assert normalize_llm_response("avoidance.") == "avoidance"

    def test_with_surrounding_text(self) -> None:
        assert normalize_llm_response("The state is overwhelm") == "overwhelm"

    def test_rejects_garbage(self) -> None:
        with pytest.raises(ValueError, match="unrecognizable state"):
            normalize_llm_response("I think the user seems tired")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="unrecognizable state"):
            normalize_llm_response("")

    def test_hyperfocus_not_matched_as_focus(self) -> None:
        assert normalize_llm_response("I'm in a hyperfocus zone") == "hyperfocus"

    def test_longer_state_matched_before_shorter_substring(self) -> None:
        assert normalize_llm_response("clearly hyperfocus state") == "hyperfocus"


# ---------------------------------------------------------------------------
# Transition enforcement tests
# ---------------------------------------------------------------------------

class TestEnforceTransition:
    """Verify Markov constraints block impossible transitions."""

    def test_allows_valid_transition(
        self, state_config: StateConfig
    ) -> None:
        result = enforce_transition("baseline", "focus", state_config)
        assert result.detected_state == "focus"
        assert not result.is_transition_blocked

    def test_blocks_impossible_transition(
        self, state_config: StateConfig
    ) -> None:
        result = enforce_transition("avoidance", "hyperfocus", state_config)
        assert result.detected_state == "avoidance"
        assert result.is_transition_blocked

    def test_allows_self_transition(
        self, state_config: StateConfig
    ) -> None:
        result = enforce_transition("hyperfocus", "hyperfocus", state_config)
        assert result.detected_state == "hyperfocus"
        assert not result.is_transition_blocked

    def test_result_includes_previous_state(
        self, state_config: StateConfig
    ) -> None:
        result = enforce_transition("baseline", "avoidance", state_config)
        assert result.previous_state == "baseline"


# ---------------------------------------------------------------------------
# Full detect_state integration tests (mocked LLM)
# ---------------------------------------------------------------------------

class TestDetectState:
    """End-to-end detection with mocked LLM responses."""

    def test_detects_avoidance_from_message(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "avoidance"

        result = asyncio.run(
            detect_state("I know I should but I can't start", "baseline", state_config, mock_llm)
        )
        assert result.detected_state == "avoidance"
        assert result.previous_state == "baseline"
        assert not result.is_transition_blocked

    def test_detects_hyperfocus_from_focus(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "hyperfocus"

        result = asyncio.run(
            detect_state("been coding for 6 hours straight", "focus", state_config, mock_llm)
        )
        assert result.detected_state == "hyperfocus"

    def test_blocks_impossible_llm_classification(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "hyperfocus"

        result = asyncio.run(
            detect_state("I can't cope", "overwhelm", state_config, mock_llm)
        )
        assert result.detected_state == "overwhelm"
        assert result.is_transition_blocked

    def test_handles_noisy_llm_response(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "  RSD  \n"

        result = asyncio.run(
            detect_state("they all think I'm useless", "baseline", state_config, mock_llm)
        )
        assert result.detected_state == "rsd"

    def test_rejects_invalid_current_state(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "baseline"

        with pytest.raises(ValueError, match="Invalid current state"):
            asyncio.run(
                detect_state("hello", "nonexistent", state_config, mock_llm)
            )

    def test_raises_on_unrecognizable_llm_response(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "the user seems happy and productive today"

        with pytest.raises(ValueError, match="unrecognizable state"):
            asyncio.run(
                detect_state("hello", "baseline", state_config, mock_llm)
            )

    def test_passes_prompt_to_llm(
        self, state_config: StateConfig
    ) -> None:
        captured_prompts: list[str] = []

        async def mock_llm(prompt: str) -> str:
            captured_prompts.append(prompt)
            return "baseline"

        asyncio.run(
            detect_state("test message", "baseline", state_config, mock_llm)
        )
        assert len(captured_prompts) == 1
        assert "test message" in captured_prompts[0]
        assert "Current state: baseline" in captured_prompts[0]
