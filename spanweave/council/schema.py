from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ulid import ULID

from spanweave.llm.adapter import Cost, Usage


def _new_council_report_id() -> str:
    return f"council_{ULID()}"


def _vote_list() -> list[CouncilVote]:
    return []


def _model_list() -> list[str]:
    return []


class Verdict(StrEnum):
    COMPATIBLE_WITH_CODER = "COMPATIBLE_WITH_CODER"
    COMPATIBLE_WITH_REVIEWER = "COMPATIBLE_WITH_REVIEWER"
    NEITHER = "NEITHER"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


class CouncilVote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    provider: str
    verdict: Verdict
    response_id: str | None = None
    usage: Usage = Field(default_factory=Usage)
    cost: Cost = Field(default_factory=Cost)

    @model_validator(mode="after")
    def validate_vote(self) -> CouncilVote:
        if self.verdict is Verdict.HUMAN_REQUIRED:
            raise ValueError("individual council votes cannot be HUMAN_REQUIRED")
        return self


class CouncilReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_new_council_report_id)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    coder_position: str
    reviewer_position: str
    context: str
    models: list[str] = Field(default_factory=_model_list)
    votes: list[CouncilVote] = Field(default_factory=_vote_list)
    final_verdict: Verdict
    memory_path: str | None = None

    @model_validator(mode="after")
    def validate_report(self) -> CouncilReport:
        if len(self.models) != 3:
            raise ValueError("council reports must record exactly three model ids")
        if len(set(self.models)) != len(self.models):
            raise ValueError("council reports require distinct model ids")
        if len(self.votes) != 3:
            raise ValueError("council reports must contain exactly three votes")

        vote_models = [vote.model for vote in self.votes]
        if set(vote_models) != set(self.models):
            raise ValueError("council vote models must match the selected models")

        counts = Counter(vote.verdict for vote in self.votes)
        majority_verdict = next(
            (verdict for verdict, count in counts.items() if count >= 2),
            Verdict.HUMAN_REQUIRED,
        )
        if self.final_verdict is not majority_verdict:
            raise ValueError("final_verdict does not match the council vote breakdown")

        return self


__all__ = ["CouncilReport", "CouncilVote", "Verdict"]
