from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest


def load_swap_demo_module():
    module_path = Path(__file__).resolve().parents[1] / "demo" / "swap-demo.py"
    spec = importlib.util.spec_from_file_location("swap_demo_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


swap_demo = load_swap_demo_module()


def test_prepare_fixture_creates_expected_failure_surface(tmp_path: Path) -> None:
    fixture = swap_demo.prepare_fixture(tmp_path)

    assert fixture.fixture_path.exists()
    assert fixture.test_path.exists()
    assert "range(0, len(values) - window)" in fixture.fixture_path.read_text(encoding="utf-8")
    assert fixture.expected_failure_signal == "expected 3 windows, got 2"


def test_run_review_check_returns_real_pytest_failure(tmp_path: Path) -> None:
    fixture = swap_demo.prepare_fixture(tmp_path)
    tool_call = swap_demo.ToolCall(
        id="call_check",
        name="run_review_check",
        arguments={"check": "pytest"},
    )

    result = swap_demo.execute_tool_call(tool_call, fixture)

    assert result["exit_code"] != 0
    assert fixture.expected_failure_signal in result["stdout"]


@pytest.mark.asyncio
async def test_mock_backend_review_finds_bug_and_uses_tools(tmp_path: Path) -> None:
    fixture = swap_demo.prepare_fixture(tmp_path)
    manifest = swap_demo.resolve_single_manifest(
        swap_demo.load_manifest_map(),
        swap_demo.DEFAULT_CLAUDE_MODEL,
        swap_demo.REQUIRED_CAPABILITIES,
    )
    backend = swap_demo.create_backend(
        label="claude",
        manifest=manifest,
        mode="mock",
        output_root=tmp_path,
    )

    result = await swap_demo.run_backend_review(backend, fixture)

    assert result.bug_detected is True
    assert {entry.tool_name for entry in result.tool_transcript} == swap_demo.REQUIRED_TOOLS
    assert "off-by-one" in result.response_content.lower()


@pytest.mark.asyncio
async def test_run_backend_review_fails_if_a_required_tool_is_missing(tmp_path: Path) -> None:
    class MissingArtifactAdapter(swap_demo.LLMAdapter):
        def __init__(self, manifest: swap_demo.CapabilityManifest) -> None:
            super().__init__(manifest)
            self.calls = 0

        async def generate(
            self,
            messages: list[swap_demo.Message],
            tools: list[swap_demo.ToolDefinition] | None = None,
            required_capabilities: swap_demo.CapabilityRequirements | None = None,
        ) -> swap_demo.Response:
            self.ensure_supported(required_capabilities)
            del messages, tools
            self.calls += 1
            if self.calls == 1:
                return swap_demo.Response(
                    provider=self.manifest.provider,
                    model=self.manifest.model,
                    tool_calls=[
                        swap_demo.ToolCall(
                            id="check_only",
                            name="run_review_check",
                            arguments={"check": "pytest"},
                        )
                    ],
                    stop_reason="tool_use",
                )
            return swap_demo.Response(
                provider=self.manifest.provider,
                model=self.manifest.model,
                content=(
                    "## Verdict\n"
                    "REJECT\n\n"
                    "## Bug\n"
                    "There is an off-by-one bug.\n"
                ),
                stop_reason="completed",
            )

    fixture = swap_demo.prepare_fixture(tmp_path)
    manifest = swap_demo.resolve_single_manifest(
        swap_demo.load_manifest_map(),
        swap_demo.DEFAULT_CLAUDE_MODEL,
        swap_demo.REQUIRED_CAPABILITIES,
    )
    backend = swap_demo.SwapDemoBackend(
        label="claude",
        manifest=manifest,
        adapter=MissingArtifactAdapter(manifest),
        run_mode="mock",
        output_path=tmp_path / "claude" / "evidence.md",
    )

    with pytest.raises(RuntimeError, match="required tools"):
        await swap_demo.run_backend_review(backend, fixture)


def test_unsupported_capability_check_mentions_tool_use() -> None:
    message = swap_demo.run_unsupported_capability_check()

    assert "tool_use=True" in message
    assert swap_demo.DEMO_TOOL_LESS_MODEL in message


def test_detect_planted_bug_requires_root_cause_not_only_failure_signal() -> None:
    response = (
        "## Verdict\n"
        "REJECT\n\n"
        "## Evidence\n"
        "The pytest run fails with `expected 3 windows, got 2`.\n"
    )

    assert (
        swap_demo.detect_planted_bug(response, "expected 3 windows, got 2") is False
    )


def test_configured_tool_less_model_raises_unsupported_capability() -> None:
    with pytest.raises(swap_demo.UnsupportedCapabilityError):
        swap_demo.resolve_single_manifest(
            swap_demo.load_manifest_map(),
            swap_demo.DEMO_TOOL_LESS_MODEL,
            swap_demo.REQUIRED_CAPABILITIES,
        )


@pytest.mark.asyncio
async def test_run_demo_async_writes_both_evidence_packs(tmp_path: Path) -> None:
    args = argparse.Namespace(
        mode="mock",
        claude_model=swap_demo.DEFAULT_CLAUDE_MODEL,
        codex_model=swap_demo.DEFAULT_CODEX_MODEL,
        output_root=str(tmp_path),
    )

    results, unsupported_error = await swap_demo.run_demo_async(args)

    assert len(results) == 2
    assert unsupported_error
    assert (tmp_path / "claude" / "evidence.md").exists()
    assert (tmp_path / "codex" / "evidence.md").exists()
    assert (
        (tmp_path / "codex" / "evidence.md").read_text(encoding="utf-8")
        != (tmp_path / "claude" / "evidence.md").read_text(encoding="utf-8")
    )


@pytest.mark.asyncio
async def test_auto_mode_falls_back_to_mock_for_both_backends_if_one_key_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "demo-key")
    args = argparse.Namespace(
        mode="auto",
        claude_model=swap_demo.DEFAULT_CLAUDE_MODEL,
        codex_model=swap_demo.DEFAULT_CODEX_MODEL,
        output_root=str(tmp_path),
    )

    results, _ = await swap_demo.run_demo_async(args)

    assert [result.backend.run_mode for result in results] == ["mock", "mock"]
