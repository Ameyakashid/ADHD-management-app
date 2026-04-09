"""Tests for state configuration — YAML structure, transition matrix, and validation."""

from pathlib import Path

import pytest
import yaml

from state_detection import (
    ALL_STATES,
    CognitiveState,
    StateConfig,
    load_state_config,
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
