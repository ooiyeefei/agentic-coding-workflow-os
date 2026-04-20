from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from atelier.council.schema import CouncilReport, CouncilVote, Verdict
from atelier.llm import (
    AnthropicAdapter,
    CapabilityManifest,
    CapabilityRequirements,
    LLMAdapter,
    Message,
    OpenAIAdapter,
    ToolDefinition,
    UnsupportedCapabilityError,
    load_capability_manifests,
)
from atelier.memory import DEFAULT_COUNCIL_MEMORY_DIR, write_council_report

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = REPO_ROOT / ".atelier" / "defaults" / "models"
DEFAULT_COUNCIL_MODELS: tuple[str, str, str] = (
    "claude-opus-4-7",
    "gpt-5",
    "claude-sonnet-4-6",
)
COUNCIL_REQUIRED_CAPABILITIES = CapabilityRequirements(tool_use=True)
_VOTE_TOOL_NAME = "submit_verdict"

AdapterFactory = Callable[[CapabilityManifest], LLMAdapter]


class _AnonymousVerdict(StrEnum):
    POSITION_A = "POSITION_A"
    POSITION_B = "POSITION_B"
    NEITHER = Verdict.NEITHER.value


class _VoteSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: _AnonymousVerdict

    @model_validator(mode="after")
    def validate_submission(self) -> _VoteSubmission:
        return self


def _build_default_adapter(manifest: CapabilityManifest) -> LLMAdapter:
    if manifest.provider == "anthropic":
        return AnthropicAdapter(manifest)
    if manifest.provider == "openai":
        return OpenAIAdapter(manifest)
    raise ValueError(f"unsupported council adapter provider: {manifest.provider}")


def _vote_tool() -> ToolDefinition:
    return ToolDefinition(
        name=_VOTE_TOOL_NAME,
        description="Submit exactly one council verdict.",
        input_schema={
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": [
                        _AnonymousVerdict.POSITION_A.value,
                        _AnonymousVerdict.POSITION_B.value,
                        Verdict.NEITHER.value,
                    ],
                }
            },
            "required": ["verdict"],
            "additionalProperties": False,
        },
        strict=True,
    )


async def tiebreak(
    coder_position: Any,
    reviewer_position: Any,
    context: Any,
    models: Sequence[str] | None = None,
    *,
    manifests: Iterable[CapabilityManifest] | None = None,
    model_directory: str | Path = DEFAULT_MODEL_DIR,
    adapter_factory: AdapterFactory = _build_default_adapter,
    memory_directory: str | Path = DEFAULT_COUNCIL_MEMORY_DIR,
) -> Verdict:
    report = await convene_council(
        coder_position,
        reviewer_position,
        context,
        models,
        manifests=manifests,
        model_directory=model_directory,
        adapter_factory=adapter_factory,
        memory_directory=memory_directory,
    )
    return report.final_verdict


async def convene_council(
    coder_position: Any,
    reviewer_position: Any,
    context: Any,
    models: Sequence[str] | None = None,
    *,
    manifests: Iterable[CapabilityManifest] | None = None,
    model_directory: str | Path = DEFAULT_MODEL_DIR,
    adapter_factory: AdapterFactory = _build_default_adapter,
    memory_directory: str | Path = DEFAULT_COUNCIL_MEMORY_DIR,
) -> CouncilReport:
    selected_model_ids = _resolve_model_ids(models)
    resolved_manifests = _resolve_manifests(
        selected_model_ids,
        manifests=manifests,
        model_directory=model_directory,
    )

    rendered_coder_position = _render_payload(coder_position)
    rendered_reviewer_position = _render_payload(reviewer_position)
    rendered_context = _render_payload(context)

    votes = await asyncio.gather(
        *[
            _collect_vote(
                manifest,
                rendered_coder_position=rendered_coder_position,
                rendered_reviewer_position=rendered_reviewer_position,
                rendered_context=rendered_context,
                adapter_factory=adapter_factory,
            )
            for manifest in resolved_manifests
        ]
    )

    report = CouncilReport(
        coder_position=rendered_coder_position,
        reviewer_position=rendered_reviewer_position,
        context=rendered_context,
        models=list(selected_model_ids),
        votes=votes,
        final_verdict=_tally_votes(votes),
    )
    return write_council_report(report, directory=memory_directory)


async def _collect_vote(
    manifest: CapabilityManifest,
    *,
    rendered_coder_position: str,
    rendered_reviewer_position: str,
    rendered_context: str,
    adapter_factory: AdapterFactory,
) -> CouncilVote:
    adapter = adapter_factory(manifest)
    response = await adapter.generate(
        messages=[
            Message(role="system", content=_system_prompt()),
            Message(
                role="user",
                content=_user_prompt(
                    rendered_coder_position=rendered_coder_position,
                    rendered_reviewer_position=rendered_reviewer_position,
                    rendered_context=rendered_context,
                ),
            ),
        ],
        tools=[_vote_tool()],
        required_capabilities=COUNCIL_REQUIRED_CAPABILITIES,
    )
    submission = _parse_vote_submission(response.tool_calls)
    return CouncilVote(
        model=manifest.model,
        provider=manifest.provider,
        verdict=_materialize_verdict(submission.verdict),
        response_id=response.id,
        usage=response.usage,
        cost=response.cost,
    )


def _resolve_model_ids(models: Sequence[str] | None) -> tuple[str, str, str]:
    selected = tuple(DEFAULT_COUNCIL_MODELS if models is None else models)
    if len(selected) != 3:
        raise ValueError("council tiebreaker requires exactly three model ids")
    if len(set(selected)) != 3:
        raise ValueError("council tiebreaker requires three distinct model ids")
    return selected[0], selected[1], selected[2]


def _resolve_manifests(
    model_ids: Sequence[str],
    *,
    manifests: Iterable[CapabilityManifest] | None,
    model_directory: str | Path,
) -> list[CapabilityManifest]:
    available = (
        list(manifests)
        if manifests is not None
        else load_capability_manifests(model_directory)
    )
    available_by_model = {manifest.model: manifest for manifest in available}

    resolved: list[CapabilityManifest] = []
    failures: dict[str, list[str]] = {}
    for model_id in model_ids:
        manifest = available_by_model.get(model_id)
        if manifest is None:
            raise ValueError(f"unknown council model {model_id!r}")
        missing = manifest.missing_capabilities(COUNCIL_REQUIRED_CAPABILITIES)
        if missing:
            failures[manifest.model] = missing
        resolved.append(manifest)

    if failures:
        raise UnsupportedCapabilityError(
            requirements=COUNCIL_REQUIRED_CAPABILITIES,
            failures=failures,
        )

    return resolved


def _parse_vote_submission(tool_calls: list[Any]) -> _VoteSubmission:
    if len(tool_calls) != 1:
        raise ValueError("council voters must return exactly one tool call")

    tool_call = tool_calls[0]
    if tool_call.name != _VOTE_TOOL_NAME:
        raise ValueError(f"unexpected council tool call {tool_call.name!r}")
    return _VoteSubmission.model_validate(tool_call.arguments)


def _tally_votes(votes: Sequence[CouncilVote]) -> Verdict:
    counts: dict[Verdict, int] = {}
    for vote in votes:
        counts[vote.verdict] = counts.get(vote.verdict, 0) + 1
        if counts[vote.verdict] >= 2:
            return vote.verdict
    return Verdict.HUMAN_REQUIRED


def _system_prompt() -> str:
    return (
        "You are one member of a three-model council resolving a deadlock between two positions. "
        "Decide which position is more compatible with the supplied context. "
        "Call the submit_verdict tool exactly once and do not answer with prose."
    )


def _user_prompt(
    *,
    rendered_coder_position: str,
    rendered_reviewer_position: str,
    rendered_context: str,
) -> str:
    return (
        "Evaluate the two anonymized positions below.\n\n"
        "Call `submit_verdict` once with `POSITION_A`, `POSITION_B`, or `NEITHER`.\n"
        "Choose `NEITHER` only when neither position is sufficiently compatible "
        "with the context.\n\n"
        "## Position A\n"
        f"{rendered_coder_position}\n\n"
        "## Position B\n"
        f"{rendered_reviewer_position}\n\n"
        "## Shared Context\n"
        f"{rendered_context}\n"
    )


def _materialize_verdict(verdict: _AnonymousVerdict) -> Verdict:
    if verdict is _AnonymousVerdict.POSITION_A:
        return Verdict.COMPATIBLE_WITH_CODER
    if verdict is _AnonymousVerdict.POSITION_B:
        return Verdict.COMPATIBLE_WITH_REVIEWER
    return Verdict.NEITHER


def _render_payload(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump_json(indent=2)
    try:
        return json.dumps(value, indent=2, sort_keys=True)
    except TypeError:
        return str(value)


__all__ = [
    "COUNCIL_REQUIRED_CAPABILITIES",
    "DEFAULT_COUNCIL_MODELS",
    "convene_council",
    "tiebreak",
]
