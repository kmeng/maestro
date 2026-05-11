"""
UTF-8-safe head+tail truncation utility for dispatch log fields (T3.1).

Keeps field values under configurable byte caps so that serialised
JSON lines stay below the 4 KiB writer limit.
"""

from maestro.dispatch_log.events import (
    DispatchEvent,
    DispatchStartEvent,
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchFallbackConfigAbsentEvent,
)


FIELD_CAPS: dict[str, int] = {
    "input_summary": 1024,
    "output_summary": 1024,
    "error_message": 512,
    "validation_error_message": 512,
}


def truncate_field(value: str, cap_bytes: int) -> str:
    """Head+tail trim a field value to fit a byte cap while keeping the
    start and end readable for debugging."""
    if cap_bytes < 64:
        raise ValueError(f"cap_bytes must be >= 64; got {cap_bytes}")
    encoded = value.encode("utf-8")
    N = len(encoded)
    if N <= cap_bytes:
        return value
    half = (cap_bytes - 32) // 2
    leading = encoded[:half].decode("utf-8", errors="ignore")
    trailing = encoded[-half:].decode("utf-8", errors="ignore")
    marker = f"…<truncated {N}→{cap_bytes} bytes>…"
    return leading + marker + trailing


def truncate_event(event: DispatchEvent) -> DispatchEvent:
    """Apply FIELD_CAPS truncation to the relevant field on *event*.
    Returns a new instance; never mutates the input."""
    if isinstance(event, DispatchStartEvent):
        return event.model_copy(
            update={
                "input_summary": truncate_field(
                    event.input_summary, FIELD_CAPS["input_summary"]
                )
            }
        )
    if isinstance(event, DispatchEndEvent):
        return event.model_copy(
            update={
                "output_summary": truncate_field(
                    event.output_summary, FIELD_CAPS["output_summary"]
                )
            }
        )
    if isinstance(event, DispatchFailedEvent):
        return event.model_copy(
            update={
                "error_message": truncate_field(
                    event.error_message, FIELD_CAPS["error_message"]
                )
            }
        )
    if isinstance(event, DispatchRefusedConfigInvalidEvent):
        return event.model_copy(
            update={
                "validation_error_message": truncate_field(
                    event.validation_error_message,
                    FIELD_CAPS["validation_error_message"],
                )
            }
        )
    if isinstance(event, DispatchFallbackConfigAbsentEvent):
        return event
    raise TypeError(f"Unrecognised event type: {type(event)}")
