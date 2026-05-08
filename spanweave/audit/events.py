from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from ulid import ULID

from spanweave.util.ulid import EntityPrefix, validate_prefixed_id


class EventType(StrEnum):
    LLM_CALL = "LLM_CALL"
    TOOL_CALL = "TOOL_CALL"
    GATE_ENTERED = "GATE_ENTERED"
    DECISION_LOGGED = "DECISION_LOGGED"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED"
    COST_ACCRUED = "COST_ACCRUED"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_event_id() -> str:
    return f"evt_{ULID()}"


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=_new_event_id)
    event_type: EventType
    run_id: str
    timestamp: datetime = Field(default_factory=_utc_now)

    @field_validator("event_id")
    @classmethod
    def _validate_event_id(cls, value: str) -> str:
        prefix = "evt_"
        if not value.startswith(prefix):
            raise ValueError(f"expected 'evt_' prefixed ID, got {value!r}")
        try:
            ULID.parse(value.removeprefix(prefix))
        except ValueError as exc:
            raise ValueError(f"invalid ULID payload in {value!r}") from exc
        return value

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return validate_prefixed_id(value, EntityPrefix.RUN)

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)

    def to_json_line(self) -> str:
        return json.dumps(self.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_json_line(cls, line: str) -> AuditEvent:
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object, got {type(payload).__name__}")
        event_type_raw = payload.get("event_type")
        if event_type_raw is None:
            raise ValueError("missing 'event_type' field")
        try:
            event_type = EventType(event_type_raw)
        except ValueError as exc:
            raise ValueError(f"unknown event_type {event_type_raw!r}") from exc
        schema_class = EVENT_SCHEMAS.get(event_type)
        if schema_class is None:
            raise ValueError(f"no schema registered for {event_type!r}")
        return schema_class.model_validate(payload)


class LLMCallEvent(AuditEvent):
    event_type: Literal[EventType.LLM_CALL] = EventType.LLM_CALL

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    stop_reason: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class ToolCallEvent(AuditEvent):
    event_type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL

    tool_name: str = Field(min_length=1)
    arguments_summary: str = ""
    result_summary: str = ""
    success: bool = True
    duration_ms: int | None = Field(default=None, ge=0)


class GateEnteredEvent(AuditEvent):
    event_type: Literal[EventType.GATE_ENTERED] = EventType.GATE_ENTERED

    gate_name: str = Field(min_length=1)
    from_stage: str = ""
    to_stage: str = ""
    verdict: str = ""


class DecisionLoggedEvent(AuditEvent):
    event_type: Literal[EventType.DECISION_LOGGED] = EventType.DECISION_LOGGED

    decision_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class OverrideAppliedEvent(AuditEvent):
    event_type: Literal[EventType.OVERRIDE_APPLIED] = EventType.OVERRIDE_APPLIED

    target: str = Field(min_length=1)
    original_value: str = ""
    override_value: str = ""
    reason: str = ""


class CostAccruedEvent(AuditEvent):
    event_type: Literal[EventType.COST_ACCRUED] = EventType.COST_ACCRUED

    cost_usd: float = Field(ge=0.0)
    category: str = Field(min_length=1)
    detail: str = ""


EVENT_SCHEMAS: dict[EventType, type[AuditEvent]] = {
    EventType.LLM_CALL: LLMCallEvent,
    EventType.TOOL_CALL: ToolCallEvent,
    EventType.GATE_ENTERED: GateEnteredEvent,
    EventType.DECISION_LOGGED: DecisionLoggedEvent,
    EventType.OVERRIDE_APPLIED: OverrideAppliedEvent,
    EventType.COST_ACCRUED: CostAccruedEvent,
}


__all__ = [
    "AuditEvent",
    "CostAccruedEvent",
    "DecisionLoggedEvent",
    "EVENT_SCHEMAS",
    "EventType",
    "GateEnteredEvent",
    "LLMCallEvent",
    "OverrideAppliedEvent",
    "ToolCallEvent",
]
