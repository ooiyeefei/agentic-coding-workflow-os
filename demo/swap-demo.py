#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spanweave.defaults import DEFAULT_MODELS_DIR, DEFAULT_PERSONAS_DIR  # noqa: E402
from spanweave.llm import (  # noqa: E402
    AnthropicAdapter,
    CapabilityManifest,
    CapabilityOffers,
    CapabilityRequirements,
    LLMAdapter,
    Message,
    OpenAIAdapter,
    Response,
    ToolCall,
    ToolDefinition,
    UnsupportedCapabilityError,
    load_capability_manifests,
    route_persona_to_model,
)

DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
DEFAULT_CODEX_MODEL = "gpt-5"
DEMO_TOOL_LESS_MODEL = "tool-less-demo-model"
REQUIRED_CAPABILITIES = CapabilityRequirements(tool_use=True)
VALID_MODES = {"auto", "live", "mock"}
REQUIRED_TOOLS = {"read_review_artifact", "run_review_check"}
MAX_REVIEW_ROUNDS = 6
BUG_ROOT_CAUSE_PATTERNS = (
    "off-by-one",
    "boundary error",
    "boundary bug",
    "one step early",
    "final valid window",
    "last valid window",
    "last rolling window",
    "len(values) - window",
    "drops the [6, 8] window",
)

FIXTURE_SOURCE = """from __future__ import annotations


def rolling_window_average(values: list[int], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        return []

    averages: list[float] = []
    for start in range(0, len(values) - window):
        chunk = values[start : start + window]
        averages.append(sum(chunk) / window)
    return averages
"""

FIXTURE_TEST = """from fixture import rolling_window_average


def test_rolling_window_average_keeps_final_window() -> None:
    result = rolling_window_average([2, 4, 6, 8], window=2)

    assert result == [3.0, 5.0, 7.0], "expected 3 windows, got 2"
"""


@dataclass(slots=True)
class SwapDemoFixture:
    workspace_dir: Path
    fixture_path: Path
    test_path: Path
    bug_summary: str
    expected_failure_signal: str


@dataclass(slots=True)
class ToolTranscriptEntry:
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass(slots=True)
class SwapDemoBackend:
    label: str
    manifest: CapabilityManifest
    adapter: LLMAdapter
    run_mode: str
    output_path: Path


@dataclass(slots=True)
class SwapDemoRunResult:
    backend: SwapDemoBackend
    response_content: str
    tool_transcript: list[ToolTranscriptEntry]
    bug_detected: bool
    evidence_summary: str


class MockDemoAdapter(LLMAdapter):
    def __init__(self, manifest: CapabilityManifest, *, backend_label: str) -> None:
        super().__init__(manifest)
        self.backend_label = backend_label

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
        *,
        run_id: str | None = None,
        policy: Any = None,
    ) -> Response:
        self.ensure_supported(required_capabilities)
        del tools, run_id, policy  # The mock uses the same tool names but does not inspect schemas.

        if not any(message.role == "tool" for message in messages):
            return Response(
                provider=self.manifest.provider,
                model=self.manifest.model,
                tool_calls=[
                    ToolCall(
                        id=f"{self.backend_label}_read",
                        name="read_review_artifact",
                        arguments={"target": "all"},
                    ),
                    ToolCall(
                        id=f"{self.backend_label}_check",
                        name="run_review_check",
                        arguments={"check": "pytest"},
                    ),
                ],
                stop_reason="tool_use",
            )

        if self.backend_label == "claude":
            content = (
                "## Verdict\n"
                "REJECT\n\n"
                "## Bug\n"
                "There is an off-by-one bug in `rolling_window_average`. "
                "The loop uses `range(0, len(values) - window)`, so the final valid "
                "window is skipped.\n\n"
                "## Evidence\n"
                "The pytest run fails with `expected 3 windows, got 2`, which matches "
                "the missing last window.\n\n"
                "## Recommendation\n"
                "Iterate through `len(values) - window + 1` starts so every valid "
                "window is averaged."
            )
        else:
            content = (
                "## Verdict\n"
                "REJECT\n\n"
                "## Bug\n"
                "The fixture has an off-by-one boundary error. "
                "`range(0, len(values) - window)` stops one step early and drops "
                "the `[6, 8]` window.\n\n"
                "## Evidence\n"
                "The executed pytest check reports `expected 3 windows, got 2`, "
                "confirming the last rolling window never makes it into the result.\n\n"
                "## Recommendation\n"
                "Change the upper bound to `len(values) - window + 1` and keep the "
                "guard clauses as they are."
            )

        return Response(
            provider=self.manifest.provider,
            model=self.manifest.model,
            content=content,
            stop_reason="completed",
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the same reviewer protocol against Claude and Codex/OpenAI and write "
            "side-by-side Evidence Packs."
        )
    )
    parser.add_argument(
        "--mode",
        default=os.getenv("SWAP_DEMO_MODE", "auto"),
        help="Run mode: auto, live, or mock.",
    )
    parser.add_argument(
        "--claude-model",
        default=os.getenv("SWAP_DEMO_CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL),
        help="Claude manifest model to use.",
    )
    parser.add_argument(
        "--codex-model",
        default=os.getenv("SWAP_DEMO_CODEX_MODEL", DEFAULT_CODEX_MODEL),
        help="Codex/OpenAI manifest model to use.",
    )
    parser.add_argument(
        "--output-root",
        default=str(REPO_ROOT / "demo" / "swap-demo-output"),
        help="Directory where Evidence Packs and the generated workspace are written.",
    )
    return parser.parse_args(argv)


def normalize_mode(raw_mode: str) -> str:
    mode = raw_mode.lower().strip()
    if mode not in VALID_MODES:
        valid = ", ".join(sorted(VALID_MODES))
        raise ValueError(f"Unsupported mode {raw_mode!r}. Expected one of: {valid}")
    return mode


def load_manifest_map() -> dict[str, CapabilityManifest]:
    manifests = load_capability_manifests(DEFAULT_MODELS_DIR)
    manifest_map = {manifest.model: manifest for manifest in manifests}
    manifest_map[DEMO_TOOL_LESS_MODEL] = build_demo_tool_less_manifest()
    return manifest_map


def build_demo_tool_less_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        provider="demo",
        model=DEMO_TOOL_LESS_MODEL,
        offers=CapabilityOffers(
            tool_use=False,
            parallel_tool_use=False,
            long_context=1024,
            code_execution=False,
            structured_outputs=False,
        ),
        cost_per_mtok_in=0.0,
        cost_per_mtok_out=0.0,
    )


def resolve_single_manifest(
    manifest_map: dict[str, CapabilityManifest],
    model_name: str,
    requirements: CapabilityRequirements,
) -> CapabilityManifest:
    manifest = manifest_map.get(model_name)
    if manifest is None:
        available = ", ".join(sorted(manifest_map))
        raise ValueError(f"Unknown model {model_name!r}. Available manifests: {available}")
    return route_persona_to_model(requirements, [manifest])


def load_reviewer_prompt_body() -> str:
    prompt_path = DEFAULT_PERSONAS_DIR / "reviewer.md"
    post = frontmatter.load(str(prompt_path))
    return post.content.strip()


def build_system_prompt() -> str:
    reviewer_prompt = load_reviewer_prompt_body()
    return (
        f"{reviewer_prompt}\n\n"
        "## Demo Instructions\n"
        "You are participating in Spanweave's LLM swappability demo.\n"
        "Use the provided tools before your final verdict.\n"
        "Read the generated review artifacts, run the approved failing check, and then "
        "reply in markdown with the exact headings `Verdict`, `Bug`, `Evidence`, and "
        "`Recommendation`.\n"
        "Name the defect precisely. If you find a boundary bug, state that it is an "
        "off-by-one bug explicitly."
    )


def build_user_message(fixture: SwapDemoFixture) -> str:
    return (
        "Review this tiny Python workspace for correctness.\n\n"
        "Review target:\n"
        f"- Fixture: {fixture.fixture_path}\n"
        f"- Test: {fixture.test_path}\n"
        f"- Known context: a small data-processing helper may contain a boundary bug.\n\n"
        "Required workflow:\n"
        "1. Read the generated artifacts with `read_review_artifact`.\n"
        "2. Execute the approved failing check with `run_review_check`.\n"
        "3. Return one final markdown review with the required headings.\n"
        "Do not skip the tools. A review without execution evidence is incomplete."
    )


def build_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="read_review_artifact",
            description="Read the generated buggy fixture, its pytest file, or both.",
            input_schema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["fixture", "test", "all"],
                    }
                },
                "required": ["target"],
                "additionalProperties": False,
            },
        ),
        ToolDefinition(
            name="run_review_check",
            description="Run the approved pytest check against the generated fixture.",
            input_schema={
                "type": "object",
                "properties": {
                    "check": {
                        "type": "string",
                        "enum": ["pytest"],
                    }
                },
                "required": ["check"],
                "additionalProperties": False,
            },
        ),
    ]


def prepare_fixture(output_root: Path) -> SwapDemoFixture:
    workspace_dir = output_root / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    fixture_path = workspace_dir / "fixture.py"
    test_path = workspace_dir / "test_fixture.py"
    fixture_path.write_text(FIXTURE_SOURCE, encoding="utf-8")
    test_path.write_text(FIXTURE_TEST, encoding="utf-8")

    return SwapDemoFixture(
        workspace_dir=workspace_dir,
        fixture_path=fixture_path,
        test_path=test_path,
        bug_summary="Off-by-one loop bound drops the final valid rolling window.",
        expected_failure_signal="expected 3 windows, got 2",
    )


def create_backend(
    *,
    label: str,
    manifest: CapabilityManifest,
    mode: str,
    output_root: Path,
) -> SwapDemoBackend:
    requested_live = mode == "live"
    allow_auto = mode == "auto"

    live_available, api_key = get_live_credentials(manifest)

    if requested_live and not live_available:
        raise RuntimeError(
            f"Live mode requested for {label}, but the required API key is missing."
        )

    run_mode = "live" if (requested_live or (allow_auto and live_available)) else "mock"
    if run_mode == "live":
        if manifest.provider == "anthropic":
            adapter = AnthropicAdapter(manifest, api_key=api_key)
        elif manifest.provider == "openai":
            adapter = OpenAIAdapter(manifest, api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider {manifest.provider!r}")
    else:
        adapter = MockDemoAdapter(manifest, backend_label=label)

    output_path = output_root / label / "evidence.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return SwapDemoBackend(
        label=label,
        manifest=manifest,
        adapter=adapter,
        run_mode=run_mode,
        output_path=output_path,
    )


def get_live_credentials(manifest: CapabilityManifest) -> tuple[bool, str | None]:
    api_key: str | None = None
    if manifest.provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
    elif manifest.provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
    return bool(api_key), api_key


def execute_tool_call(tool_call: ToolCall, fixture: SwapDemoFixture) -> dict[str, Any]:
    arguments = tool_call.arguments if isinstance(tool_call.arguments, dict) else {}

    if tool_call.name == "read_review_artifact":
        target = str(arguments.get("target", "all"))
        payload: dict[str, Any] = {"target": target}
        if target in {"fixture", "all"}:
            payload["fixture"] = {
                "path": str(fixture.fixture_path),
                "content": fixture.fixture_path.read_text(encoding="utf-8"),
            }
        if target in {"test", "all"}:
            payload["test"] = {
                "path": str(fixture.test_path),
                "content": fixture.test_path.read_text(encoding="utf-8"),
            }
        return payload

    if tool_call.name == "run_review_check":
        command = [sys.executable, "-m", "pytest", fixture.test_path.name, "-q"]
        completed = subprocess.run(
            command,
            cwd=fixture.workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "check": str(arguments.get("check", "pytest")),
            "command": " ".join(command),
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }

    return {
        "error": f"Unsupported tool call: {tool_call.name}",
    }


def detect_planted_bug(response_content: str, _failure_signal: str) -> bool:
    normalized = response_content.lower()
    return any(pattern in normalized for pattern in BUG_ROOT_CAUSE_PATTERNS)


def extract_verdict(response_content: str) -> str:
    match = re.search(r"(?im)^## verdict\s*\n([A-Z]+)", response_content)
    if match:
        return match.group(1).strip()
    if "reject" in response_content.lower():
        return "REJECT"
    if "approve" in response_content.lower():
        return "APPROVE"
    return "UNCLEAR"


async def run_backend_review(
    backend: SwapDemoBackend,
    fixture: SwapDemoFixture,
) -> SwapDemoRunResult:
    messages = [
        Message(role="system", content=build_system_prompt()),
        Message(role="user", content=build_user_message(fixture)),
    ]
    transcript: list[ToolTranscriptEntry] = []
    tools = build_tool_definitions()
    response_content = ""
    nudges = 0

    for _ in range(MAX_REVIEW_ROUNDS):
        response = await backend.adapter.generate(
            messages=messages,
            tools=tools,
            required_capabilities=REQUIRED_CAPABILITIES,
        )
        response_content = response.content.strip()
        messages.append(
            Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            )
        )

        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = execute_tool_call(tool_call, fixture)
                transcript.append(
                    ToolTranscriptEntry(
                        tool_name=tool_call.name,
                        arguments=tool_call.arguments
                        if isinstance(tool_call.arguments, dict)
                        else {},
                        result=result,
                    )
                )
                messages.append(
                    Message(
                        role="tool",
                        tool_call_id=tool_call.id,
                        content=json.dumps(result, indent=2, sort_keys=True),
                    )
                )
            continue

        used_tools = {entry.tool_name for entry in transcript}
        missing_tools = sorted(REQUIRED_TOOLS - used_tools)
        if missing_tools and nudges < 2:
            nudges += 1
            messages.append(
                Message(
                    role="user",
                    content=(
                        "Your review is missing required tool evidence. "
                        f"Use these tools before your final verdict: {', '.join(missing_tools)}."
                    ),
                )
            )
            continue
        break
    else:
        raise RuntimeError(f"Review loop exceeded {MAX_REVIEW_ROUNDS} rounds for {backend.label}")

    used_tools = {entry.tool_name for entry in transcript}
    missing_tools = sorted(REQUIRED_TOOLS - used_tools)
    if missing_tools:
        raise RuntimeError(
            f"Review completed without required tools for {backend.label}: "
            f"{', '.join(missing_tools)}"
        )

    if not transcript:
        raise RuntimeError(f"Review completed without tool evidence for {backend.label}")

    bug_detected = detect_planted_bug(response_content, fixture.expected_failure_signal)
    verdict = extract_verdict(response_content)
    summary = (
        f"{backend.label} ({backend.manifest.model}, {backend.run_mode}) -> "
        f"{verdict}, bug_found={'yes' if bug_detected else 'no'}"
    )
    return SwapDemoRunResult(
        backend=backend,
        response_content=response_content,
        tool_transcript=transcript,
        bug_detected=bug_detected,
        evidence_summary=summary,
    )


def render_evidence_pack(
    result: SwapDemoRunResult,
    fixture: SwapDemoFixture,
    unsupported_error: str,
) -> str:
    transcript_sections: list[str] = []
    for index, entry in enumerate(result.tool_transcript, start=1):
        transcript_sections.append(
            "\n".join(
                [
                    f"### Tool {index}: `{entry.tool_name}`",
                    "",
                    "**Arguments**",
                    "",
                    "```json",
                    json.dumps(entry.arguments, indent=2, sort_keys=True),
                    "```",
                    "",
                    "**Result**",
                    "",
                    "```json",
                    json.dumps(entry.result, indent=2, sort_keys=True),
                    "```",
                ]
            )
        )

    return "\n".join(
        [
            f"# Evidence Pack: {result.backend.label}",
            "",
            f"- Provider: `{result.backend.manifest.provider}`",
            f"- Model: `{result.backend.manifest.model}`",
            f"- Run Mode: `{result.backend.run_mode}`",
            f"- Verdict: `{extract_verdict(result.response_content)}`",
            f"- Planted Bug Found: `{'yes' if result.bug_detected else 'no'}`",
            "",
            "## Review Target",
            "",
            f"- Fixture: `{fixture.fixture_path}`",
            f"- Test: `{fixture.test_path}`",
            f"- Planted Bug: {fixture.bug_summary}",
            "",
            "## Executed Check Summary",
            "",
            f"- Expected failure signal: `{fixture.expected_failure_signal}`",
            f"- Run summary: {result.evidence_summary}",
            "",
            "## Tool Transcript",
            "",
            "\n\n".join(transcript_sections),
            "",
            "## Reviewer Response",
            "",
            result.response_content,
            "",
            "## Guardrail Check",
            "",
            "Expected incompatible-manifest failure:",
            "",
            "```text",
            unsupported_error.strip(),
            "```",
            "",
        ]
    )


def write_evidence_pack(
    result: SwapDemoRunResult,
    fixture: SwapDemoFixture,
    unsupported_error: str,
) -> None:
    result.backend.output_path.parent.mkdir(parents=True, exist_ok=True)
    result.backend.output_path.write_text(
        render_evidence_pack(result, fixture, unsupported_error),
        encoding="utf-8",
    )


def run_unsupported_capability_check() -> str:
    manifest_map = load_manifest_map()
    try:
        resolve_single_manifest(manifest_map, DEMO_TOOL_LESS_MODEL, REQUIRED_CAPABILITIES)
    except UnsupportedCapabilityError as exc:
        return str(exc)
    raise RuntimeError("Expected incompatible manifest to fail capability validation")


async def run_demo_async(args: argparse.Namespace) -> tuple[list[SwapDemoRunResult], str]:
    mode = normalize_mode(args.mode)
    output_root = Path(args.output_root).resolve()
    fixture = prepare_fixture(output_root)
    manifest_map = load_manifest_map()

    claude_manifest = resolve_single_manifest(
        manifest_map, args.claude_model, REQUIRED_CAPABILITIES
    )
    codex_manifest = resolve_single_manifest(
        manifest_map, args.codex_model, REQUIRED_CAPABILITIES
    )

    effective_mode = mode
    if mode == "auto":
        live_ready = all(
            get_live_credentials(manifest)[0]
            for manifest in (claude_manifest, codex_manifest)
        )
        effective_mode = "live" if live_ready else "mock"

    backends = [
        create_backend(
            label="claude",
            manifest=claude_manifest,
            mode=effective_mode,
            output_root=output_root,
        ),
        create_backend(
            label="codex",
            manifest=codex_manifest,
            mode=effective_mode,
            output_root=output_root,
        ),
    ]

    unsupported_error = run_unsupported_capability_check()
    results: list[SwapDemoRunResult] = []
    for backend in backends:
        result = await run_backend_review(backend, fixture)
        write_evidence_pack(result, fixture, unsupported_error)
        results.append(result)
    return results, unsupported_error


def print_summary(results: list[SwapDemoRunResult], unsupported_error: str) -> None:
    print("Swap demo completed.")
    for result in results:
        print(f"- {result.evidence_summary}")
        print(f"  wrote {result.backend.output_path}")
    print("- guardrail: expected UnsupportedCapabilityError confirmed")
    print(f"  {unsupported_error}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results, unsupported_error = asyncio.run(run_demo_async(args))
    print_summary(results, unsupported_error)

    failed_runs = [
        result.backend.label
        for result in results
        if not result.bug_detected or extract_verdict(result.response_content) != "REJECT"
    ]
    if failed_runs:
        print(
            "One or more runs did not reject and explicitly identify the planted bug: "
            + ", ".join(failed_runs),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
