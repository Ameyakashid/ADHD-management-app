"""Cognitive state detection for the ADHD assistant.

Loads a 6-state model from workspace/states.yaml, builds an LLM classification
prompt, and enforces Markov transition constraints. The detected state drives
tone and pacing adjustments in the bot's responses.

The module exposes pure functions and pydantic models — no global state.
"""

import logging
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

log = logging.getLogger(__name__)

StateName = Literal[
    "baseline", "focus", "hyperfocus", "avoidance", "overwhelm", "rsd"
]

ALL_STATES: frozenset[str] = frozenset(
    ["baseline", "focus", "hyperfocus", "avoidance", "overwhelm", "rsd"]
)


# ---------------------------------------------------------------------------
# Config models
# ---------------------------------------------------------------------------

class CognitiveState(BaseModel):
    """One cognitive state as defined in states.yaml."""

    description: str
    detection_signals: list[str]
    response_style: list[str]
    transitions: dict[str, float]

    @model_validator(mode="after")
    def validate_transitions(self) -> "CognitiveState":
        missing = ALL_STATES - set(self.transitions.keys())
        if missing:
            raise ValueError(
                f"Transition matrix missing target states: {sorted(missing)}"
            )
        extra = set(self.transitions.keys()) - ALL_STATES
        if extra:
            raise ValueError(
                f"Transition matrix has unknown states: {sorted(extra)}"
            )
        total = sum(self.transitions.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Transition probabilities sum to {total}, expected 1.0"
            )
        for name, prob in self.transitions.items():
            if prob < 0.0 or prob > 1.0:
                raise ValueError(
                    f"Transition probability for '{name}' is {prob}, "
                    f"must be between 0.0 and 1.0"
                )
        return self


class StateConfig(BaseModel):
    """Complete state configuration loaded from YAML."""

    states: dict[str, CognitiveState]

    @model_validator(mode="after")
    def validate_all_states_present(self) -> "StateConfig":
        missing = ALL_STATES - set(self.states.keys())
        if missing:
            raise ValueError(
                f"State config missing required states: {sorted(missing)}"
            )
        extra = set(self.states.keys()) - ALL_STATES
        if extra:
            raise ValueError(
                f"State config has unknown states: {sorted(extra)}"
            )
        return self


class DetectionResult(BaseModel):
    """Output of a state detection call."""

    previous_state: str
    detected_state: str
    is_transition_blocked: bool


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_state_config(config_path: Path) -> StateConfig:
    """Load and validate state configuration from a YAML file."""
    if not config_path.exists():
        raise FileNotFoundError(
            f"State config not found at {config_path}. "
            f"Expected workspace/states.yaml in the repo root."
        )
    raw = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict) or "states" not in data:
        raise ValueError(
            f"State config at {config_path} must have a top-level 'states' key"
        )
    return StateConfig.model_validate(data)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_classification_prompt(
    message: str,
    current_state: str,
    config: StateConfig,
) -> str:
    """Build the LLM classification prompt from config and user message."""
    state_descriptions: list[str] = []
    for name, state in config.states.items():
        signals = ", ".join(state.detection_signals)
        state_descriptions.append(
            f"- {name}: {state.description.strip()} "
            f"Signals: [{signals}]"
        )
    states_block = "\n".join(state_descriptions)

    return (
        "You are a cognitive state classifier for a user with AUDHD "
        "(ADHD + autism). Your job is to detect which cognitive state "
        "the user is currently in based on their message.\n\n"
        f"Current state: {current_state}\n\n"
        f"Possible states:\n{states_block}\n\n"
        f'User message: "{message}"\n\n'
        "Respond with ONLY the state name (one of: "
        f"{', '.join(sorted(ALL_STATES))}). "
        "No explanation, no punctuation, no extra text."
    )


# ---------------------------------------------------------------------------
# Transition enforcement
# ---------------------------------------------------------------------------

def enforce_transition(
    current_state: str,
    llm_detected: str,
    config: StateConfig,
) -> DetectionResult:
    """Apply Markov transition constraints to the LLM classification.

    If the transition probability from current_state to llm_detected is 0.0,
    the transition is blocked and current_state is returned instead.
    """
    current_transitions = config.states[current_state].transitions
    probability = current_transitions.get(llm_detected, 0.0)

    is_blocked = probability == 0.0 and llm_detected != current_state

    if is_blocked:
        log.info(
            "Blocked impossible transition %s -> %s (probability 0.0)",
            current_state,
            llm_detected,
        )
        return DetectionResult(
            previous_state=current_state,
            detected_state=current_state,
            is_transition_blocked=True,
        )

    return DetectionResult(
        previous_state=current_state,
        detected_state=llm_detected,
        is_transition_blocked=False,
    )


# ---------------------------------------------------------------------------
# LLM classification
# ---------------------------------------------------------------------------

def normalize_llm_response(raw_response: str) -> str:
    """Extract a valid state name from raw LLM output."""
    cleaned = raw_response.strip().lower().rstrip(".")
    if cleaned in ALL_STATES:
        return cleaned
    # Handle cases where LLM wraps the state in quotes or adds minor noise
    for state in ALL_STATES:
        if state in cleaned:
            return state
    raise ValueError(
        f"LLM returned unrecognizable state: '{raw_response}'. "
        f"Expected one of: {sorted(ALL_STATES)}"
    )


async def detect_state(
    message: str,
    current_state: str,
    config: StateConfig,
    llm_call: "LLMCallable",
) -> DetectionResult:
    """Detect the user's cognitive state from their message.

    Args:
        message: The user's message text.
        current_state: The user's current cognitive state name.
        config: Loaded and validated state configuration.
        llm_call: An async callable that takes a prompt string and returns
                  the LLM's response string. This decouples detection from
                  the specific LLM provider.

    Returns:
        DetectionResult with the detected state and transition metadata.

    Raises:
        ValueError: If current_state is not a valid state name, or if the
                    LLM returns an unrecognizable state.
    """
    if current_state not in ALL_STATES:
        raise ValueError(
            f"Invalid current state: '{current_state}'. "
            f"Must be one of: {sorted(ALL_STATES)}"
        )

    prompt = build_classification_prompt(message, current_state, config)
    raw_response = await llm_call(prompt)
    detected = normalize_llm_response(raw_response)

    return enforce_transition(current_state, detected, config)


# Type alias for the LLM call dependency
from typing import Protocol


class LLMCallable(Protocol):
    """Protocol for the async LLM call function passed to detect_state."""

    async def __call__(self, prompt: str) -> str: ...
