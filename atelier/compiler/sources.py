from __future__ import annotations

from typing import Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator

PriorityTier: TypeAlias = Literal["must", "should", "nice"]
SourceType: TypeAlias = Literal[
    "issue_text",
    "repo_rule",
    "adr",
    "sample_doc",
    "worktree_ref",
    "objective",
    "exact_commands",
    "acceptance_gate",
]

PRIORITY_ORDER: dict[PriorityTier, int] = {
    "must": 0,
    "should": 1,
    "nice": 2,
}
VALID_SOURCE_TYPES = {
    "issue_text",
    "repo_rule",
    "adr",
    "sample_doc",
    "worktree_ref",
    "objective",
    "exact_commands",
    "acceptance_gate",
}
SourceTypeT = TypeVar("SourceTypeT", bound=SourceType)


class ContextSource(BaseModel, Generic[SourceTypeT]):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: SourceTypeT
    source_id: str
    title: str
    content: str
    priority: PriorityTier
    path: str | None = None

    @field_validator("source_id", "title", "content")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("source fields must not be blank")
        return cleaned

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        if value not in VALID_SOURCE_TYPES:
            raise ValueError("unsupported source_type")
        return value

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip()
        return cleaned or None


class IssueText(ContextSource[Literal["issue_text"]]):
    source_type: Literal["issue_text"] = "issue_text"


class RepoRule(ContextSource[Literal["repo_rule"]]):
    source_type: Literal["repo_rule"] = "repo_rule"


class ADR(ContextSource[Literal["adr"]]):
    source_type: Literal["adr"] = "adr"


class SampleDoc(ContextSource[Literal["sample_doc"]]):
    source_type: Literal["sample_doc"] = "sample_doc"


class WorktreeRef(ContextSource[Literal["worktree_ref"]]):
    source_type: Literal["worktree_ref"] = "worktree_ref"


class Objective(ContextSource[Literal["objective"]]):
    source_type: Literal["objective"] = "objective"
    source_id: str = "objective"
    title: str = "Objective"
    priority: PriorityTier = "must"


class ExactCommands(ContextSource[Literal["exact_commands"]]):
    source_type: Literal["exact_commands"] = "exact_commands"


class AcceptanceGate(ContextSource[Literal["acceptance_gate"]]):
    source_type: Literal["acceptance_gate"] = "acceptance_gate"


Source: TypeAlias = (
    IssueText
    | RepoRule
    | ADR
    | SampleDoc
    | WorktreeRef
    | Objective
    | ExactCommands
    | AcceptanceGate
)


def sort_sources_by_priority(sources: list[Source]) -> list[Source]:
    return sorted(sources, key=lambda source: PRIORITY_ORDER[source.priority])


__all__ = [
    "ADR",
    "AcceptanceGate",
    "ContextSource",
    "ExactCommands",
    "IssueText",
    "Objective",
    "PRIORITY_ORDER",
    "PriorityTier",
    "RepoRule",
    "SampleDoc",
    "Source",
    "SourceType",
    "WorktreeRef",
    "sort_sources_by_priority",
]
