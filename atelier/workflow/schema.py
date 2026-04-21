from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GateType(StrEnum):
    AUTO = "auto"
    REVIEW = "review"
    APPROVAL = "approval"


class OnRejectAction(StrEnum):
    HALT = "halt"
    REVISE = "revise"
    COUNCIL = "council"


_REVERT_TO_PREFIX = "revert_to:"


def parse_on_reject(value: str) -> tuple[str, str | None]:
    if value.startswith(_REVERT_TO_PREFIX):
        target = value[len(_REVERT_TO_PREFIX) :]
        if not target:
            raise ValueError("revert_to: requires a target stage id")
        return "revert_to", target
    if value not in OnRejectAction.__members__.values():
        raise ValueError(f"invalid on_reject: {value!r}")
    return value, None


class StageDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonEmptyText
    persona: NonEmptyText
    skill: NonEmptyText
    gate_type: GateType = GateType.AUTO
    retry_max: int = Field(default=0, ge=0, le=50)
    on_reject: str = OnRejectAction.HALT

    @field_validator("on_reject")
    @classmethod
    def _validate_on_reject(cls, value: str) -> str:
        parse_on_reject(value)
        return value


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: NonEmptyText
    version: NonEmptyText
    description: str = ""
    stages: list[StageDefinition] = Field(min_length=1)

    @field_validator("stages")
    @classmethod
    def _validate_unique_stage_ids(cls, value: list[StageDefinition]) -> list[StageDefinition]:
        seen: set[str] = set()
        for stage in value:
            if stage.id in seen:
                raise ValueError(f"duplicate stage id: {stage.id!r}")
            seen.add(stage.id)
        return value

    @model_validator(mode="after")
    def _validate_revert_targets(self) -> WorkflowDefinition:
        stage_ids = {s.id for s in self.stages}
        for stage in self.stages:
            action, target = parse_on_reject(stage.on_reject)
            if action == "revert_to" and target not in stage_ids:
                raise ValueError(
                    f"stage {stage.id!r} has on_reject {stage.on_reject!r} "
                    f"but target {target!r} is not a stage in this workflow"
                )
        return self

    def stage_index(self, stage_id: str) -> int:
        for i, stage in enumerate(self.stages):
            if stage.id == stage_id:
                return i
        raise KeyError(f"stage {stage_id!r} not found in workflow {self.name!r}")


__all__ = [
    "GateType",
    "OnRejectAction",
    "StageDefinition",
    "WorkflowDefinition",
    "parse_on_reject",
]
