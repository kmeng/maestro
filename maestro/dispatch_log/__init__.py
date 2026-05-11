"""
Dispatch log event models and truncation utility (T3.1).
"""

from .events import (
    CostBreakdown,
    DispatchEvent,
    DispatchStartEvent,
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DISPATCH_EVENT_ADAPTER,
)
from .truncation import truncate_field, truncate_event, FIELD_CAPS

__all__ = [
    "CostBreakdown",
    "DispatchEvent",
    "DispatchStartEvent",
    "DispatchEndEvent",
    "DispatchFailedEvent",
    "DispatchFallbackConfigAbsentEvent",
    "DispatchRefusedConfigInvalidEvent",
    "DISPATCH_EVENT_ADAPTER",
    "truncate_field",
    "truncate_event",
    "FIELD_CAPS",
]
