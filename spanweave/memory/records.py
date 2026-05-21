from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator
from ulid import ULID

from spanweave.util.ulid import EntityPrefix, validate_prefixed_id


def _new_record_id(prefix: str) -> str:
    return f"{prefix}_{ULID()}"


def _validate_record_id(value: str, prefix: str) -> str:
    prefix_text = f"{prefix}_"
    if not value.startswith(prefix_text):
        raise ValueError(f"expected {prefix!r} ID, got {value!r}")

    try:
        ULID.parse(value.removeprefix(prefix_text))
    except ValueError as exc:
        raise ValueError(f"invalid ULID payload in {value!r}") from exc

    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_prefix: ClassVar[str]
    collection_name: ClassVar[str]
    record_type: ClassVar[str]

    id: str
    type: str
    version: int = 1
    run_id: str
    stage_id: str
    timestamp: datetime = Field(default_factory=_utc_now)
    related_issues: list[str] = Field(default_factory=list)
    related_adrs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str = Field(min_length=1)
    body: str = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_record_id(value, cls.id_prefix)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != cls.record_type:
            raise ValueError(f"expected record type {cls.record_type!r}, got {value!r}")
        return value

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_prefixed_id(value, EntityPrefix.RUN)

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id(cls, value: str) -> str:
        return validate_prefixed_id(value, EntityPrefix.STAGE)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("related_issues", "related_adrs", "tags")
    @classmethod
    def validate_string_list(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip()
            if not item:
                raise ValueError("list items must be non-empty")
            normalized.append(item)
        return normalized

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source must be non-empty")
        return normalized

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body must contain non-whitespace content")
        return value

    @property
    def filename(self) -> str:
        return f"{self.id}.md"

    @property
    def collection(self) -> str:
        return self.collection_name

    @property
    def path_fragment(self) -> Path:
        return Path(self.collection_name) / self.filename

    def frontmatter(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("body")
        return payload


class Decision(MemoryRecord):
    id_prefix = "decision"
    collection_name = "decisions"
    record_type = "Decision"

    id: str = Field(default_factory=lambda: _new_record_id(Decision.id_prefix))
    type: str = "Decision"


class ReviewFinding(MemoryRecord):
    id_prefix = "review_finding"
    collection_name = "findings"
    record_type = "ReviewFinding"

    id: str = Field(default_factory=lambda: _new_record_id(ReviewFinding.id_prefix))
    type: str = "ReviewFinding"


class RejectedAlternative(MemoryRecord):
    id_prefix = "rejected_alternative"
    collection_name = "rejected_alternatives"
    record_type = "RejectedAlternative"

    id: str = Field(default_factory=lambda: _new_record_id(RejectedAlternative.id_prefix))
    type: str = "RejectedAlternative"


class SkillOutcome(MemoryRecord):
    id_prefix = "skill_outcome"
    collection_name = "skill_outcomes"
    record_type = "SkillOutcome"

    id: str = Field(default_factory=lambda: _new_record_id(SkillOutcome.id_prefix))
    type: str = "SkillOutcome"
    selected_skill_id: str = Field(min_length=1)
    skill_version: str | None = None
    task_text: str = Field(min_length=1)
    result_summary: str = Field(min_length=1)
    success_score: float = Field(ge=0.0, le=1.0)
    feedback: float = Field(ge=-1.0, le=1.0)
    error_type: str | None = None
    error_message: str | None = None
    applied_rules: list[str] = Field(default_factory=list)

    @field_validator("selected_skill_id", "task_text", "result_summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must contain non-whitespace content")
        return normalized

    @field_validator("skill_version", "error_type", "error_message")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WorkflowEvent(MemoryRecord):
    id_prefix = "workflow_event"
    collection_name = "workflow_events"
    record_type = "WorkflowEvent"

    id: str = Field(default_factory=lambda: _new_record_id(WorkflowEvent.id_prefix))
    type: str = "WorkflowEvent"


Record: TypeAlias = Decision | ReviewFinding | RejectedAlternative | SkillOutcome | WorkflowEvent

RECORD_TYPES: dict[str, type[MemoryRecord]] = {
    "Decision": Decision,
    "ReviewFinding": ReviewFinding,
    "RejectedAlternative": RejectedAlternative,
    "SkillOutcome": SkillOutcome,
    "WorkflowEvent": WorkflowEvent,
}

__all__ = [
    "Decision",
    "MemoryRecord",
    "Record",
    "RECORD_TYPES",
    "RejectedAlternative",
    "ReviewFinding",
    "SkillOutcome",
    "WorkflowEvent",
]
