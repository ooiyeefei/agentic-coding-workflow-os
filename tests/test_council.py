from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import frontmatter
import pytest
from spanweave.council import DEFAULT_COUNCIL_MODELS, convene_council, tiebreak
from spanweave.council.schema import Verdict
from spanweave.llm import CapabilityManifest
from spanweave.llm.adapter import LLMAdapter, Message, Response, ToolCall, ToolDefinition
from spanweave.llm.capabilities import (
    CapabilityRequirements,
    UnsupportedCapabilityError,
)


class StubAdapter(LLMAdapter):
    def __init__(
        self,
        manifest: CapabilityManifest,
        *,
        verdict: Verdict,
        tracker: ConcurrencyTracker | None = None,
        prompt_auditor: Callable[[list[Message], list[ToolDefinition] | None], None] | None = None,
    ) -> None:
        super().__init__(manifest)
        self._verdict = verdict
        self._tracker = tracker
        self._prompt_auditor = prompt_auditor

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
    ) -> Response:
        self.ensure_supported(required_capabilities)
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert tools is not None
        assert tools[0].name == "submit_verdict"
        if self._prompt_auditor is not None:
            self._prompt_auditor(messages, tools)

        if self._tracker is not None:
            await self._tracker.enter()
            try:
                await asyncio.sleep(0.01)
            finally:
                self._tracker.exit()

        return Response(
            id=f"resp_{self.manifest.model}",
            provider=self.manifest.provider,
            model=self.manifest.model,
            tool_calls=[
                ToolCall(
                    id=f"call_{self.manifest.model}",
                    name="submit_verdict",
                    arguments={"verdict": _tool_verdict(self._verdict)},
                )
            ],
        )


class ConcurrencyTracker:
    def __init__(self) -> None:
        self.current = 0
        self.max_concurrent = 0
        self._lock = asyncio.Lock()

    async def enter(self) -> None:
        async with self._lock:
            self.current += 1
            self.max_concurrent = max(self.max_concurrent, self.current)

    def exit(self) -> None:
        self.current -= 1


@pytest.mark.asyncio
async def test_tiebreak_returns_coder_majority_and_persists_report(tmp_path: Path) -> None:
    manifests = make_manifests(DEFAULT_COUNCIL_MODELS)
    verdicts = {
        "claude-opus-4-7": Verdict.COMPATIBLE_WITH_CODER,
        "gpt-5": Verdict.COMPATIBLE_WITH_CODER,
        "claude-sonnet-4-6": Verdict.NEITHER,
    }

    verdict = await tiebreak(
        "Adopt the coder's patch",
        "Request a full revert",
        {"issue": 21, "rounds": 2},
        manifests=manifests,
        adapter_factory=make_adapter_factory(verdicts),
        memory_directory=tmp_path,
    )

    assert verdict is Verdict.COMPATIBLE_WITH_CODER

    records = list(tmp_path.glob("*.md"))
    assert len(records) == 1
    post = frontmatter.load(str(records[0]))
    assert post.metadata["type"] == "council_report"
    assert post.metadata["final_verdict"] == Verdict.COMPATIBLE_WITH_CODER.value
    assert post.metadata["models"] == list(DEFAULT_COUNCIL_MODELS)
    assert "Position A" in post.content
    assert "`claude-opus-4-7` (`anthropic`): `COMPATIBLE_WITH_CODER`" in post.content
    assert "`gpt-5` (`openai`): `COMPATIBLE_WITH_CODER`" in post.content
    assert "`claude-sonnet-4-6` (`anthropic`): `NEITHER`" in post.content


@pytest.mark.asyncio
async def test_tiebreak_returns_reviewer_majority(tmp_path: Path) -> None:
    models = ("model-a", "model-b", "model-c")
    manifests = make_manifests(models)
    verdict = await tiebreak(
        "Ship the change now",
        "Block until tests land",
        "The reviewer found a regression.",
        models=models,
        manifests=manifests,
        adapter_factory=make_adapter_factory(
            {
                "model-a": Verdict.COMPATIBLE_WITH_REVIEWER,
                "model-b": Verdict.COMPATIBLE_WITH_REVIEWER,
                "model-c": Verdict.NEITHER,
            }
        ),
        memory_directory=tmp_path,
    )

    assert verdict is Verdict.COMPATIBLE_WITH_REVIEWER


@pytest.mark.asyncio
async def test_tiebreak_returns_human_required_on_three_way_split(tmp_path: Path) -> None:
    models = ("model-a", "model-b", "model-c")
    manifests = make_manifests(models)
    verdict = await tiebreak(
        "Coder stance",
        "Reviewer stance",
        {"context": "split vote"},
        models=models,
        manifests=manifests,
        adapter_factory=make_adapter_factory(
            {
                "model-a": Verdict.COMPATIBLE_WITH_CODER,
                "model-b": Verdict.COMPATIBLE_WITH_REVIEWER,
                "model-c": Verdict.NEITHER,
            }
        ),
        memory_directory=tmp_path,
    )

    assert verdict is Verdict.HUMAN_REQUIRED


@pytest.mark.asyncio
async def test_tiebreak_rejects_unsupported_capability_before_adapter_construction() -> None:
    manifests = [
        make_manifest(model="model-a", provider="openai", tool_use=False),
        make_manifest(model="model-b", provider="openai"),
        make_manifest(model="model-c", provider="anthropic"),
    ]

    with pytest.raises(UnsupportedCapabilityError):
        await tiebreak(
            "Coder stance",
            "Reviewer stance",
            "Context",
            models=["model-a", "model-b", "model-c"],
            manifests=manifests,
            adapter_factory=raising_adapter_factory,
        )


@pytest.mark.asyncio
async def test_convene_council_dispatches_all_votes_concurrently(tmp_path: Path) -> None:
    tracker = ConcurrencyTracker()
    models = ("model-a", "model-b", "model-c")
    manifests = make_manifests(models)
    await convene_council(
        "Coder stance",
        "Reviewer stance",
        "Context",
        models=models,
        manifests=manifests,
        adapter_factory=make_adapter_factory(
            {
                "model-a": Verdict.COMPATIBLE_WITH_CODER,
                "model-b": Verdict.COMPATIBLE_WITH_CODER,
                "model-c": Verdict.NEITHER,
            },
            tracker=tracker,
        ),
        memory_directory=tmp_path,
    )

    assert tracker.max_concurrent == 3


@pytest.mark.asyncio
async def test_convene_council_anonymizes_model_facing_vote_protocol(tmp_path: Path) -> None:
    models = ("model-a", "model-b", "model-c")
    manifests = make_manifests(models)
    await convene_council(
        "Adopt patch 17",
        "Reject patch 17",
        "A neutral context packet.",
        models=models,
        manifests=manifests,
        adapter_factory=make_adapter_factory(
            {
                "model-a": Verdict.COMPATIBLE_WITH_CODER,
                "model-b": Verdict.COMPATIBLE_WITH_CODER,
                "model-c": Verdict.NEITHER,
            },
            prompt_auditor=assert_anonymous_vote_protocol,
        ),
        memory_directory=tmp_path,
    )


def make_adapter_factory(
    verdicts: dict[str, Verdict],
    *,
    tracker: ConcurrencyTracker | None = None,
    prompt_auditor: Callable[[list[Message], list[ToolDefinition] | None], None] | None = None,
) -> Any:
    def _factory(manifest: CapabilityManifest) -> StubAdapter:
        return StubAdapter(
            manifest,
            verdict=verdicts[manifest.model],
            tracker=tracker,
            prompt_auditor=prompt_auditor,
        )

    return _factory


def raising_adapter_factory(_: CapabilityManifest) -> LLMAdapter:
    raise AssertionError("adapter construction should not happen for unsupported models")


def make_manifests(models: tuple[str, str, str]) -> list[CapabilityManifest]:
    providers = ("anthropic", "openai", "anthropic")
    return [
        make_manifest(model=model, provider=provider)
        for model, provider in zip(models, providers, strict=True)
    ]


def assert_anonymous_vote_protocol(
    messages: list[Message],
    tools: list[ToolDefinition] | None,
) -> None:
    user_prompt = messages[1].content
    assert "COMPATIBLE_WITH_CODER" not in user_prompt
    assert "COMPATIBLE_WITH_REVIEWER" not in user_prompt

    assert tools is not None
    schema_text = json.dumps(tools[0].input_schema, sort_keys=True)
    assert "COMPATIBLE_WITH_CODER" not in schema_text
    assert "COMPATIBLE_WITH_REVIEWER" not in schema_text
    assert "POSITION_A" in schema_text
    assert "POSITION_B" in schema_text


def _tool_verdict(verdict: Verdict) -> str:
    if verdict is Verdict.COMPATIBLE_WITH_CODER:
        return "POSITION_A"
    if verdict is Verdict.COMPATIBLE_WITH_REVIEWER:
        return "POSITION_B"
    return Verdict.NEITHER.value


def make_manifest(
    *,
    model: str,
    provider: str,
    tool_use: bool = True,
) -> CapabilityManifest:
    return CapabilityManifest.model_validate(
        {
            "provider": provider,
            "model": model,
            "offers": {
                "tool_use": tool_use,
                "parallel_tool_use": True,
                "long_context": 200000,
                "code_execution": False,
                "structured_outputs": False,
            },
            "cost_per_mtok_in": 1.0,
            "cost_per_mtok_out": 1.0,
        }
    )
