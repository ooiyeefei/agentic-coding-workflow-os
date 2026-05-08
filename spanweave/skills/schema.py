from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SemVer = Annotated[str, StringConstraints(pattern=r"^\d+\.\d+\.\d+$")]


class SkillFrontmatter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: SemVer
    inputs: list[NonEmptyText] = Field(min_length=1)
    expected_artifacts: list[NonEmptyText] = Field(min_length=1)
    success_checks: list[NonEmptyText] = Field(min_length=1)
    next_transition: NonEmptyText


class Skill(SkillFrontmatter):
    model_config = ConfigDict(frozen=True)

    name: NonEmptyText
    path: NonEmptyText
    content: str = Field(min_length=1)
