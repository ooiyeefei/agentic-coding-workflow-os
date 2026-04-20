from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from ulid import ULID

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
FindingReference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
AuditReference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Verdict(StrEnum):
    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"
    REJECTED = "REJECTED"


class Severity(StrEnum):
    RED = "RED"
    ORANGE = "ORANGE"
    YELLOW = "YELLOW"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: FindingReference
    severity: Severity
    description: NonEmptyText
    file: NonEmptyText
    line: int | None = Field(default=None, ge=1)
    verification: NonEmptyText


class CommandOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command: NonEmptyText
    stdout: str = ""
    stderr: str = ""
    exit_code: int
    finding_ids: list[FindingReference] = Field(default_factory=list)


class EvidencePack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    findings: list[Finding] = Field(default_factory=list)
    execution: list[CommandOutput] = Field(default_factory=list)
    audit_chain: list[AuditReference] = Field(default_factory=list, min_length=1)
    timestamp: datetime
    reviewer_persona_id: NonEmptyText

    @field_validator("audit_chain")
    @classmethod
    def _validate_audit_chain(cls, value: list[AuditReference]) -> list[AuditReference]:
        for reference in value:
            try:
                ULID.parse(reference)
            except ValueError as exc:
                raise ValueError(f"invalid audit ULID {reference!r}") from exc
        return value

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_finding_links(self) -> EvidencePack:
        finding_ids = [finding.finding_id for finding in self.findings]
        duplicates = sorted(
            finding_id for finding_id, count in Counter(finding_ids).items() if count > 1
        )
        if duplicates:
            duplicates_text = ", ".join(duplicates)
            raise ValueError(f"duplicate finding_id values: {duplicates_text}")

        known_findings = set(finding_ids)
        missing = sorted(
            {
                finding_id
                for command_output in self.execution
                for finding_id in command_output.finding_ids
                if finding_id not in known_findings
            }
        )
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"execution references unknown finding_id values: {missing_text}")

        return self


__all__ = [
    "CommandOutput",
    "EvidencePack",
    "Finding",
    "Severity",
    "Verdict",
]
