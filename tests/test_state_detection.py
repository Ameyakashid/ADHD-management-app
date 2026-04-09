"""Tests for state_detection module — config loading, prompt building, and detection."""

import asyncio
from pathlib import Path

import pytest
import yaml

from state_detection import (
    ALL_STATES,
    CognitiveState,
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


@pytest.fixture(scope="module")
def raw_yaml() -> dict[str, object]:
    return yaml.safe_load(STATES_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Config file structure tests
# ---------------------------------------------------------------------------

class TestConfigFileStructure:
    """Verify states.yaml has correct structure and all required states."""

    def test_config_file_exists(self) -> None:
        assert STATES_PATH.exists(), f"states.yaml not found at {STATES_PATH}"

    def test_config_loads_without_error(self, state_config: StateConfig) -> None:
        assert state_config is not None

    def test_all_six_states_present(self, state_config: StateConfig) -> None:
        assert set(state_config.states.keys()) == ALL_STATES

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_state_has_description(
        self, state_config: StateConfig, state_name: str
    ) -> None:
        state = state_config.states[state_name]
        assert len(state.description.strip()) > 10, (
            f"State '{state_name}' description is too short"
        )

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_state_has_detection_signals(
        self, state_config: StateConfig, state_name: str
    ) -> None:
        state = state_config.states[state_name]
        assert len(state.detection_signals) >= 2, (
            f"State '{state_name}' needs at least 2 detection signals"
        )

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_state_has_response_style(
        self, state_config: StateConfig, state_name: str
    ) -> None:
        state = state_config.states[state_name]
        assert len(state.response_style) >= 1, (
            f"State '{state_name}' needs at least 1 response style rule"
        )


# ---------------------------------------------------------------------------
# Transition matrix tests
# ---------------------------------------------------------------------------

class TestTransitionMatrix:
    """Verify Markov transition probabilities are valid."""

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_transitions_sum_to_one(
        self, state_config: StateConfig, state_name: str
    ) -> None:
        state = state_config.states[state_name]
        total = sum(state.transitions.values())
        assert abs(total - 1.0) < 0.01, (
            f"State '{state_name}' transitions sum to {total}, expected 1.0"
        )

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_transitions_cover_all_states(
        self, state_config: StateConfig, state_name: str
    ) -> None:
        state = state_config.states[state_name]
        assert set(state.transitions.keys()) == ALL_STATES, (
            f"State '{state_name}' transition matrix doesn't cover all states"
        )

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_all_probabilities_non_negative(
        self, state_config: StateConfig, state_name: str
    ) -> None:
        state = state_config.states[state_name]
        for target, prob in state.transitions.items():
            assert prob >= 0.0, (
                f"Negative probability {state_name} -> {target}: {prob}"
            )

    @pytest.mark.parametrize("state_name", sorted(ALL_STATES))
    def test_self_transition_exists(
        self, state_config: StateConfig, state_name: str
    ) -> None:
        """Self-transition should be significant to prevent state flickering."""
        state = state_config.states[state_name]
        assert state.transitions[state_name] >= 0.20, (
            f"State '{state_name}' self-transition {state.transitions[state_name]} "
            f"is too low — risks state flickering"
        )

    def test_avoidance_cannot_reach_hyperfocus(
        self, state_config: StateConfig
    ) -> None:
        """Avoidance -> Hyperfocus should be impossible (0.0)."""
        prob = state_config.states["avoidance"].transitions["hyperfocus"]
        assert prob == 0.0, (
            f"Avoidance -> Hyperfocus should be 0.0, got {prob}"
        )

    def test_overwhelm_cannot_reach_hyperfocus(
        self, state_config: StateConfig
    ) -> None:
        """Overwhelm -> Hyperfocus should be impossible (0.0)."""
        prob = state_config.states["overwhelm"].transitions["hyperfocus"]
        assert prob == 0.0, (
            f"Overwhelm -> Hyperfocus should be 0.0, got {prob}"
        )

    def test_rsd_cannot_reach_hyperfocus(
        self, state_config: StateConfig
    ) -> None:
        """RSD -> Hyperfocus should be impossible (0.0)."""
        prob = state_config.states["rsd"].transitions["hyperfocus"]
        assert prob == 0.0, (
            f"RSD -> Hyperfocus should be 0.0, got {prob}"
        )

    def test_hyperfocus_can_crash_to_overwhelm(
        self, state_config: StateConfig
    ) -> None:
        """Hyperfocus -> Overwhelm should exist (post-hyperfocus crash)."""
        prob = state_config.states["hyperfocus"].transitions["overwhelm"]
        assert prob > 0.0, (
            f"Hyperfocus -> Overwhelm should be possible, got {prob}"
        )


# ---------------------------------------------------------------------------
# Config validation error tests
# ---------------------------------------------------------------------------

class TestConfigValidation:
    """Verify pydantic models reject invalid configurations."""

    def test_rejects_missing_state(self) -> None:
        incomplete = {
            "states": {
                name: {
                    "description": "test",
                    "detection_signals": ["signal"],
                    "response_style": ["style"],
                    "transitions": {s: 1.0 / 6 for s in ALL_STATES},
                }
                for name in list(ALL_STATES)[:5]
            }
        }
        with pytest.raises(ValueError, match="missing required states"):
            StateConfig.model_validate(incomplete)

    def test_rejects_probabilities_not_summing_to_one(self) -> None:
        bad_transitions = {s: 0.1 for s in ALL_STATES}
        with pytest.raises(ValueError, match="sum to"):
            CognitiveState(
                description="test",
                detection_signals=["signal"],
                response_style=["style"],
                transitions=bad_transitions,
            )

    def test_rejects_negative_probability(self) -> None:
        transitions = {s: 0.2 for s in ALL_STATES}
        transitions["baseline"] = -0.1
        transitions["focus"] = 0.3
        with pytest.raises(ValueError, match="must be between"):
            CognitiveState(
                description="test",
                detection_signals=["signal"],
                response_style=["style"],
                transitions=transitions,
            )

    def test_rejects_unknown_state_in_transitions(self) -> None:
        transitions = {s: 1.0 / 6 for s in ALL_STATES}
        transitions["nonexistent"] = 0.0
        with pytest.raises(ValueError, match="unknown states"):
            CognitiveState(
                description="test",
                detection_signals=["signal"],
                response_style=["style"],
                transitions=transitions,
            )

    def test_rejects_missing_state_in_transitions(self) -> None:
        transitions = {s: 0.2 for s in list(ALL_STATES)[:5]}
        with pytest.raises(ValueError, match="missing target states"):
            CognitiveState(
                description="test",
                detection_signals=["signal"],
                response_style=["style"],
                transitions=transitions,
            )


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

    def _run_async(self, coro: object) -> DetectionResult:
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_detects_avoidance_from_message(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "avoidance"

        result = self._run_async(
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

        result = self._run_async(
            detect_state("been coding for 6 hours straight", "focus", state_config, mock_llm)
        )
        assert result.detected_state == "hyperfocus"

    def test_blocks_impossible_llm_classification(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "hyperfocus"

        result = self._run_async(
            detect_state("I can't cope", "overwhelm", state_config, mock_llm)
        )
        assert result.detected_state == "overwhelm"
        assert result.is_transition_blocked

    def test_handles_noisy_llm_response(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "  RSD  \n"

        result = self._run_async(
            detect_state("they all think I'm useless", "baseline", state_config, mock_llm)
        )
        assert result.detected_state == "rsd"

    def test_rejects_invalid_current_state(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "baseline"

        with pytest.raises(ValueError, match="Invalid current state"):
            self._run_async(
                detect_state("hello", "nonexistent", state_config, mock_llm)
            )

    def test_raises_on_unrecognizable_llm_response(
        self, state_config: StateConfig
    ) -> None:
        async def mock_llm(prompt: str) -> str:
            return "the user seems happy and productive today"

        with pytest.raises(ValueError, match="unrecognizable state"):
            self._run_async(
                detect_state("hello", "baseline", state_config, mock_llm)
            )

    def test_passes_prompt_to_llm(
        self, state_config: StateConfig
    ) -> None:
        captured_prompts: list[str] = []

        async def mock_llm(prompt: str) -> str:
            captured_prompts.append(prompt)
            return "baseline"

        self._run_async(
            detect_state("test message", "baseline", state_config, mock_llm)
        )
        assert len(captured_prompts) == 1
        assert "test message" in captured_prompts[0]
        assert "Current state: baseline" in captured_prompts[0]
