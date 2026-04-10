"""Tests for buffer hook — pure functions."""

from datetime import date, datetime, timedelta, timezone

from buffer_store import Buffer
from buffer_hook import (
    collect_alertable_buffers,
    find_due_buffers,
    format_buffer_alert_line,
    format_buffer_alerts,
    inject_alerts_into_prompt,
)

TODAY = date(2026, 4, 10)
NOW = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
SYSTEM_PROMPT = "# Soul\n\nYou are an assistant."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_buffer(
    name: str,
    buffer_level: int,
    buffer_capacity: int,
    next_due_date: date,
    alert_threshold: int,
    recurrence_interval_days: int = 30,
    status: str = "active",
) -> Buffer:
    return Buffer(
        id=name.lower().replace(" ", "_") + "_id_padding_hex",
        name=name,
        buffer_level=buffer_level,
        buffer_capacity=buffer_capacity,
        next_due_date=next_due_date,
        alert_threshold=alert_threshold,
        recurrence_interval_days=recurrence_interval_days,
        status=status,  # type: ignore[arg-type]
        created_at=NOW,
        updated_at=NOW,
    )


# ---------------------------------------------------------------------------
# find_due_buffers
# ---------------------------------------------------------------------------

class TestFindDueBuffers:

    def test_empty_list(self) -> None:
        assert find_due_buffers([], TODAY) == []

    def test_due_today(self) -> None:
        buf = _make_buffer("Rent", 3, 4, TODAY, 1)
        result = find_due_buffers([buf], TODAY)
        assert len(result) == 1
        assert result[0].name == "Rent"

    def test_overdue(self) -> None:
        past = TODAY - timedelta(days=5)
        buf = _make_buffer("Meds", 2, 4, past, 1, 7)
        result = find_due_buffers([buf], TODAY)
        assert len(result) == 1

    def test_not_yet_due(self) -> None:
        future = TODAY + timedelta(days=3)
        buf = _make_buffer("Sub", 4, 4, future, 1)
        assert find_due_buffers([buf], TODAY) == []

    def test_mixed_due_and_not_due(self) -> None:
        due = _make_buffer("Rent", 3, 4, TODAY, 1)
        not_due = _make_buffer("Sub", 4, 4, TODAY + timedelta(days=5), 1)
        result = find_due_buffers([due, not_due], TODAY)
        assert len(result) == 1
        assert result[0].name == "Rent"

    def test_level_zero_still_returned(self) -> None:
        buf = _make_buffer("Empty", 0, 4, TODAY, 1)
        result = find_due_buffers([buf], TODAY)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# format_buffer_alert_line
# ---------------------------------------------------------------------------

class TestFormatBufferAlertLine:

    def test_format_includes_name_and_level(self) -> None:
        buf = _make_buffer("Rent", 1, 4, TODAY, 2)
        line = format_buffer_alert_line(buf)
        assert "Rent" in line
        assert "1/4" in line

    def test_format_includes_due_date(self) -> None:
        buf = _make_buffer("Meds", 2, 4, date(2026, 4, 17), 2, 7)
        line = format_buffer_alert_line(buf)
        assert "2026-04-17" in line

    def test_format_includes_interval(self) -> None:
        buf = _make_buffer("Sub", 1, 3, TODAY, 1)
        line = format_buffer_alert_line(buf)
        assert "every 30 days" in line

    def test_no_guilt_phrases(self) -> None:
        buf = _make_buffer("Rent", 0, 4, TODAY, 1)
        line = format_buffer_alert_line(buf)
        lower = line.lower()
        for phrase in ["urgent", "warning", "danger", "failing", "behind"]:
            assert phrase not in lower


# ---------------------------------------------------------------------------
# format_buffer_alerts
# ---------------------------------------------------------------------------

class TestFormatBufferAlerts:

    def test_empty_returns_empty_string(self) -> None:
        assert format_buffer_alerts([]) == ""

    def test_single_buffer(self) -> None:
        buf = _make_buffer("Rent", 1, 4, TODAY, 2)
        result = format_buffer_alerts([buf])
        assert result.startswith("## Buffer Alerts")
        assert "Rent" in result

    def test_multiple_buffers(self) -> None:
        bufs = [
            _make_buffer("Rent", 1, 4, TODAY, 2),
            _make_buffer("Meds", 0, 4, TODAY, 1, 7),
        ]
        result = format_buffer_alerts(bufs)
        assert "Rent" in result
        assert "Meds" in result

    def test_header_is_factual(self) -> None:
        buf = _make_buffer("Test", 1, 4, TODAY, 2)
        result = format_buffer_alerts([buf])
        assert "## Buffer Alerts" in result
        lower = result.lower()
        for phrase in ["urgent", "critical", "danger", "you need to"]:
            assert phrase not in lower


# ---------------------------------------------------------------------------
# collect_alertable_buffers
# ---------------------------------------------------------------------------

class TestCollectAlertableBuffers:

    def test_empty(self) -> None:
        assert collect_alertable_buffers([]) == []

    def test_below_threshold(self) -> None:
        buf = _make_buffer("Rent", 1, 4, TODAY, 2)
        result = collect_alertable_buffers([buf])
        assert len(result) == 1

    def test_at_threshold(self) -> None:
        buf = _make_buffer("Meds", 2, 4, TODAY, 2, 7)
        result = collect_alertable_buffers([buf])
        assert len(result) == 1

    def test_above_threshold_excluded(self) -> None:
        buf = _make_buffer("Sub", 3, 4, TODAY, 1)
        assert collect_alertable_buffers([buf]) == []

    def test_level_zero(self) -> None:
        buf = _make_buffer("Rent", 0, 4, TODAY, 1)
        result = collect_alertable_buffers([buf])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# inject_alerts_into_prompt
# ---------------------------------------------------------------------------

class TestInjectAlertsIntoPrompt:

    def test_empty_block_returns_unchanged(self) -> None:
        assert inject_alerts_into_prompt(SYSTEM_PROMPT, "") == SYSTEM_PROMPT

    def test_appends_block(self) -> None:
        block = "## Buffer Alerts\n\n- Rent: 1/4"
        result = inject_alerts_into_prompt(SYSTEM_PROMPT, block)
        assert result.endswith(block)
        assert SYSTEM_PROMPT in result
        assert "\n\n## Buffer Alerts" in result
