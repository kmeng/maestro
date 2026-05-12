"""
Pydantic models for the dispatch log event contract (T3.1).

Defines the five event types specified in ADR-0007 and a
discriminated-union adapter for type-safe JSON parsing.
"""

from datetime import datetime
from typing import Literal, Optional, Union, Annotated

from pydantic import BaseModel, Field, TypeAdapter

from maestro.team.models import RoleId


class CostBreakdown(BaseModel):
    """Token usage and optional USD cost for a dispatch call."""
    prompt_tokens: int
    completion_tokens: int
    usd: Optional[float] = None


class _DispatchEventBase(BaseModel):
    """Fields shared by all dispatch events."""
    event_version: int = Field(default=1)
    request_id: str
    timestamp: datetime


class DispatchStartEvent(_DispatchEventBase):
    """Emitted when a dispatching run begins."""
    event_type: Literal["dispatch.start"] = "dispatch.start"
    role: RoleId
    model: str
    member: str
    input_summary: str


class DispatchEndEvent(_DispatchEventBase):
    """Emitted when a dispatching run completes normally."""
    event_type: Literal["dispatch.end"] = "dispatch.end"
    output_summary: str
    duration_ms: int
    cost: Optional[CostBreakdown] = None


class DispatchFailedEvent(_DispatchEventBase):
    """Emitted when a dispatching run fails."""
    event_type: Literal["dispatch.failed"] = "dispatch.failed"
    duration_ms: int
    error_kind: str
    error_message: str


class DispatchFallbackConfigAbsentEvent(_DispatchEventBase):
    """Emitted when dispatch falls back because primary configuration is absent."""
    event_type: Literal["dispatch.fallback.config_absent"] = "dispatch.fallback.config_absent"
    role: RoleId
    fallback_model: str


class DispatchRefusedConfigInvalidEvent(_DispatchEventBase):
    """Emitted when dispatch refuses to run because configuration is invalid."""
    event_type: Literal["dispatch.refused.config_invalid"] = "dispatch.refused.config_invalid"
    validation_error_field: str
    validation_error_message: str


DispatchEvent = Annotated[
    Union[
        DispatchStartEvent,
        DispatchEndEvent,
        DispatchFailedEvent,
        DispatchFallbackConfigAbsentEvent,
        DispatchRefusedConfigInvalidEvent,
    ],
    Field(discriminator="event_type"),
]

DISPATCH_EVENT_ADAPTER = TypeAdapter(DispatchEvent)
