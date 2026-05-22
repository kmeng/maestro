"""
Unit tests for dispatch event models and truncation (T3.1).
"""

import json
from datetime import datetime, timezone

import pytest

from maestro.dispatch_log.events import (
    CostBreakdown,
    DispatchStartEvent,
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DISPATCH_EVENT_ADAPTER,
)
from maestro.dispatch_log.truncation import truncate_field, truncate_event


def _utc_now():
    return datetime.now(timezone.utc)


# 1. Construction
def test_each_model_constructs_with_valid_args():
    e = DispatchStartEvent(
        request_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        timestamp=_utc_now(),
        role="coder",
        model="gpt-4",
        member="turing",
        input_summary="Add user authentication endpoint",
    )
    assert e.event_type == "dispatch.start"
    assert e.role == "coder"

    cost = CostBreakdown(prompt_tokens=150, completion_tokens=60, usd=0.002)
    e = DispatchEndEvent(
        request_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        timestamp=_utc_now(),
        output_summary="Authentication module generated",
        duration_ms=1250,
        cost=cost,
    )
    assert e.output_summary == "Authentication module generated"
    assert e.cost == cost

    e = DispatchFailedEvent(
        request_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        timestamp=_utc_now(),
        duration_ms=340,
        error_kind="Timeout",
        error_message="Request to model timed out after 30 s.",
    )
    assert e.error_kind == "Timeout"

    e = DispatchFallbackConfigAbsentEvent(
        request_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        timestamp=_utc_now(),
        role="librarian",
        fallback_model="claude-3-haiku",
    )
    assert e.fallback_model == "claude-3-haiku"

    e = DispatchRefusedConfigInvalidEvent(
        request_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        timestamp=_utc_now(),
        validation_error_field="model",
        validation_error_message="Model 'turbo-chicken' is not registered.",
    )
    assert e.validation_error_field == "model"


# 2. Discriminated union parsing
@pytest.mark.parametrize(
    "event_dict,expected_class",
    [
        (
            {
                "event_type": "dispatch.start",
                "event_version": 1,
                "request_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "timestamp": "2025-04-01T08:00:00Z",
                "role": "scribe",
                "model": "gpt-4",
                "member": "turing",
                "input_summary": "summarize logs",
            },
            DispatchStartEvent,
        ),
        (
            {
                "event_type": "dispatch.end",
                "event_version": 1,
                "request_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "timestamp": "2025-04-01T08:00:00Z",
                "output_summary": "done",
                "duration_ms": 100,
            },
            DispatchEndEvent,
        ),
        (
            {
                "event_type": "dispatch.failed",
                "event_version": 1,
                "request_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "timestamp": "2025-04-01T08:00:00Z",
                "duration_ms": 200,
                "error_kind": "timeout",
                "error_message": "timed out",
            },
            DispatchFailedEvent,
        ),
        (
            {
                "event_type": "dispatch.fallback.config_absent",
                "event_version": 1,
                "request_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "timestamp": "2025-04-01T08:00:00Z",
                "role": "reviewer",
                "fallback_model": "claude",
            },
            DispatchFallbackConfigAbsentEvent,
        ),
        (
            {
                "event_type": "dispatch.refused.config_invalid",
                "event_version": 1,
                "request_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "timestamp": "2025-04-01T08:00:00Z",
                "validation_error_field": "model",
                "validation_error_message": "bad model",
            },
            DispatchRefusedConfigInvalidEvent,
        ),
    ],
)
def test_discriminated_union_parses_each_event_type(event_dict, expected_class):
    raw = json.dumps(event_dict)
    parsed = DISPATCH_EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, expected_class)


# 3. Round-trip
def test_round_trip_each_model():
    ts = _utc_now()
    cost = CostBreakdown(prompt_tokens=10, completion_tokens=5)
    start = DispatchStartEvent(
        request_id="REQ1", timestamp=ts, role="coder",
        model="gpt-4", member="alice", input_summary="test",
    )
    end = DispatchEndEvent(
        request_id="REQ1", timestamp=ts,
        output_summary="ok", duration_ms=42, cost=cost,
    )
    failed = DispatchFailedEvent(
        request_id="REQ1", timestamp=ts,
        duration_ms=1, error_kind="Err", error_message="boom",
    )
    fallback = DispatchFallbackConfigAbsentEvent(
        request_id="REQ1", timestamp=ts,
        role="librarian", fallback_model="haiku",
    )
    refused = DispatchRefusedConfigInvalidEvent(
        request_id="REQ1", timestamp=ts,
        validation_error_field="x", validation_error_message="bad",
    )
    for orig in (start, end, failed, fallback, refused):
        json_str = orig.model_dump_json()
        restored = DISPATCH_EVENT_ADAPTER.validate_json(json_str)
        assert restored == orig


# 4. Truncation per field cap
@pytest.mark.parametrize(
    "field_name,cap",
    [("input_summary", 1024), ("output_summary", 1024),
     ("error_message", 512), ("validation_error_message", 512)],
)
def test_truncation_per_field_cap(field_name, cap):
    oversized = "x" * 10_000
    result = truncate_field(oversized, cap)
    byte_len = len(result.encode("utf-8"))
    assert byte_len <= cap + 64
    assert "<truncated " in result


# 5. Full event under 4 KB after truncation
def test_full_event_under_4kb_after_truncate_event():
    ts = _utc_now()
    event = DispatchStartEvent(
        request_id="REQ1", timestamp=ts,
        role="coder", model="gpt-4", member="alice",
        input_summary="x" * 10_000,
    )
    truncated = truncate_event(event)
    serialized = truncated.model_dump_json()
    assert len(serialized.encode("utf-8")) + 1 <= 4096


# 6. UTF-8 boundary safety
def test_truncation_utf8_boundary_safe():
    value = "中" * 1000
    cap = 512
    result = truncate_field(value, cap)
    encoded = result.encode("utf-8")
    decoded = encoded.decode("utf-8")
    assert decoded == result
    assert "<truncated " in result
    assert len(encoded) <= cap + 64


# 7. No-op under cap
def test_truncate_field_no_op_when_under_cap():
    result = truncate_field("hello", 1024)
    assert result == "hello"


# 8. Tiny cap raises ValueError
def test_truncate_field_raises_on_tiny_cap():
    with pytest.raises(ValueError, match="cap_bytes"):
        truncate_field("anything", 32)


# 9. truncate_event returns same type
def test_truncate_event_returns_same_type():
    ts = _utc_now()
    events = [
        DispatchStartEvent(
            request_id="R", timestamp=ts, role="coder",
            model="m", member="a", input_summary="x" * 10_000,
        ),
        DispatchEndEvent(
            request_id="R", timestamp=ts,
            output_summary="x" * 10_000, duration_ms=1,
        ),
        DispatchFailedEvent(
            request_id="R", timestamp=ts,
            duration_ms=1, error_kind="E", error_message="x" * 10_000,
        ),
        DispatchFallbackConfigAbsentEvent(
            request_id="R", timestamp=ts,
            role="reviewer", fallback_model="fallback",
        ),
        DispatchRefusedConfigInvalidEvent(
            request_id="R", timestamp=ts,
            validation_error_field="f",
            validation_error_message="x" * 10_000,
        ),
    ]
    for orig in events:
        result = truncate_event(orig)
        assert type(result) is type(orig)


# 10. Non-truncatable field returns equivalent event
def test_truncate_event_no_truncatable_field_returns_equivalent():
    ts = _utc_now()
    event = DispatchFallbackConfigAbsentEvent(
        request_id="REQ", timestamp=ts,
        role="scribe", fallback_model="backup",
    )
    result = truncate_event(event)
    assert result.model_dump() == event.model_dump()
