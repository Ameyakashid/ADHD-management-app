"""Tests for state_response_integration pure functions."""

import pytest

from state_response_integration import (
    STATE_INDICATOR_PREFIX,
    build_state_indicator,
    extract_latest_user_message,
    inject_state_into_prompt,
)


class TestBuildStateIndicator:
    """build_state_indicator produces correct format."""

    def test_baseline_indicator(self) -> None:
        result = build_state_indicator("baseline")
        assert result == "[Current cognitive state: baseline]"

    def test_rsd_indicator(self) -> None:
        result = build_state_indicator("rsd")
        assert result == "[Current cognitive state: rsd]"


class TestExtractLatestUserMessage:
    """extract_latest_user_message finds the right message."""

    def test_finds_last_user_message(self) -> None:
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "second"},
        ]
        assert extract_latest_user_message(messages) == "second"

    def test_returns_none_with_no_user_messages(self) -> None:
        messages = [{"role": "system", "content": "system prompt"}]
        assert extract_latest_user_message(messages) is None

    def test_skips_empty_user_messages(self) -> None:
        messages = [
            {"role": "user", "content": "real message"},
            {"role": "user", "content": "   "},
        ]
        assert extract_latest_user_message(messages) == "real message"

    def test_returns_none_on_empty_list(self) -> None:
        assert extract_latest_user_message([]) is None


class TestInjectStateIntoPrompt:
    """inject_state_into_prompt places indicator correctly."""

    SAMPLE_PROMPT = (
        "# Soul\n\n"
        "You are an assistant.\n\n"
        "## State-Aware Adaptation\n\n"
        "Some adaptation rules here.\n\n"
        "## Personality Voices\n\n"
        "Reserved."
    )

    def test_injects_indicator_after_heading(self) -> None:
        result = inject_state_into_prompt(self.SAMPLE_PROMPT, "focus")
        indicator = build_state_indicator("focus")
        assert indicator in result

        lines = result.split("\n")
        heading_idx = next(
            i for i, l in enumerate(lines)
            if l.strip() == "## State-Aware Adaptation"
        )
        # Indicator should appear within 2 lines after heading
        nearby = "\n".join(lines[heading_idx:heading_idx + 4])
        assert indicator in nearby

    def test_replaces_existing_indicator(self) -> None:
        prompt_with_indicator = inject_state_into_prompt(
            self.SAMPLE_PROMPT, "focus"
        )
        result = inject_state_into_prompt(prompt_with_indicator, "rsd")
        assert build_state_indicator("rsd") in result
        assert build_state_indicator("focus") not in result

    def test_only_one_indicator_after_multiple_injections(self) -> None:
        prompt = self.SAMPLE_PROMPT
        for state in ["baseline", "focus", "hyperfocus", "overwhelm"]:
            prompt = inject_state_into_prompt(prompt, state)

        count = prompt.count(STATE_INDICATOR_PREFIX)
        assert count == 1, f"Expected 1 indicator, found {count}"

    def test_fallback_when_heading_missing(self) -> None:
        prompt = "# Soul\n\nNo state section here."
        result = inject_state_into_prompt(prompt, "avoidance")
        assert build_state_indicator("avoidance") in result

    def test_preserves_other_content(self) -> None:
        result = inject_state_into_prompt(self.SAMPLE_PROMPT, "baseline")
        assert "# Soul" in result
        assert "## Personality Voices" in result
        assert "Reserved." in result
