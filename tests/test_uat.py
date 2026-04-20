from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from atelier.evidence import EvidencePack
from atelier.llm import (
    CapabilityManifest,
    CapabilityRequirements,
    Cost,
    LLMAdapter,
    Message,
    Response,
    Usage,
)
from atelier.personas import UAT, AgentResponse, uat_runner
from atelier.personas.uat_runner import (
    UATExecutionError,
    UATRequest,
    UATTimeoutError,
    run_uat,
)


class FakeAdapter(LLMAdapter):
    def __init__(self, manifest: CapabilityManifest, response: Response | None = None) -> None:
        super().__init__(manifest)
        self.calls: list[dict[str, Any]] = []
        self._response = response or Response(
            provider=manifest.provider,
            model=manifest.model,
            content="Verify the login flow and any visible error states.",
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[Any] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
    ) -> Response:
        self.ensure_supported(required_capabilities)
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "required_capabilities": required_capabilities,
            }
        )
        return self._response


@pytest.fixture
def fake_skill_script(tmp_path: Path) -> Path:
    path = tmp_path / "mock-uat.sh"
    path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_uat_routes_to_first_compatible_shipped_manifest() -> None:
    persona = UAT()

    assert persona.name == "uat"
    assert persona.llm_adapter_name == "gpt-5"
    assert persona.required_capabilities.tool_use is True
    assert persona.required_capabilities.structured_outputs is True


@pytest.mark.asyncio
async def test_uat_respond_returns_agent_response_with_evidence_metadata(
    fixed_ulid_values: list[str],
) -> None:
    adapter = FakeAdapter(
        make_manifest(model="uat-model", tool_use=True, structured_outputs=True),
        response=Response(
            provider="openai",
            model="uat-model",
            content="1. Sign in with the demo account.\n2. Verify the primary happy path.",
            usage=Usage(input_tokens=11, output_tokens=13),
            cost=Cost(input_usd=0.001, output_usd=0.002),
        ),
    )

    def runner(request: UATRequest, *, test_plan: str | None = None) -> EvidencePack:
        assert request.app_path == "demo/app"
        assert "Sign in with the demo account" in (test_plan or "")
        return make_evidence_pack(summary="UAT: 2/2 passed", audit_id=fixed_ulid_values[0])

    persona = UAT(adapter=adapter, runner=runner)

    result = await persona.respond(
        {
            "app_path": "demo/app",
            "test_password": "secret-password",
            "notes": 'Use TEST_PASSWORD="hunter2" if login asks again',
        }
    )

    assert isinstance(result, AgentResponse)
    assert result.persona == "uat"
    assert result.adapter_name == "uat-model"
    assert result.model == "uat-model"
    assert result.metadata["evidence_pack"]["summary"] == "UAT: 2/2 passed"
    assert "UAT: 2/2 passed" in result.content
    assert "secret-password" not in adapter.calls[0]["messages"][1].content
    assert "hunter2" not in adapter.calls[0]["messages"][1].content
    assert "[REDACTED:secret]" in adapter.calls[0]["messages"][1].content


def test_run_uat_maps_report_to_evidence_pack_and_redacts_credentials(
    fake_skill_script: Path,
) -> None:
    captured: dict[str, Any] = {}

    def subprocess_runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout=(
                "UAT: 1/3 passed\n"
                "PASS: Login page loads\n"
                "FAIL: Password hunter2 triggered a server error\n"
                "WARN: Retry-After header missing\n"
            ),
            stderr="TEST_PASSWORD=hunter2\n",
        )

    evidence = run_uat(
        UATRequest(
            app_path="demo/app",
            skill_path=str(fake_skill_script),
            test_user="demo@atelier.dev",
            test_password="hunter2",
        ),
        subprocess_runner=subprocess_runner,
    )

    assert evidence.summary == "UAT: 1/3 passed"
    assert evidence.verdict == "REJECTED"
    assert [finding.severity for finding in evidence.findings] == ["RED", "YELLOW"]
    assert evidence.findings[0].description == "Password [REDACTED:secret] triggered a server error"
    assert evidence.findings[1].description == "Retry-After header missing"
    assert "hunter2" not in evidence.execution[0].stdout
    assert "hunter2" not in evidence.execution[0].stderr
    assert captured["kwargs"]["env"]["TEST_USER"] == "demo@atelier.dev"
    assert captured["kwargs"]["env"]["TEST_PASSWORD"] == "hunter2"
    assert Path(captured["command"][-1]).name == "app"


def test_run_uat_parses_stderr_findings_even_when_stdout_is_non_empty(
    fake_skill_script: Path,
) -> None:
    def subprocess_runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="PASS: login page loads\n",
            stderr="FAIL: checkout button crashes\n",
        )

    evidence = run_uat(
        UATRequest(
            app_path="demo/app",
            skill_path=str(fake_skill_script),
            test_user="demo@atelier.dev",
            test_password="demo1234",
        ),
        subprocess_runner=subprocess_runner,
    )

    assert evidence.summary == "UAT: 1/2 passed"
    assert evidence.verdict == "REJECTED"
    assert len(evidence.findings) == 1
    assert evidence.findings[0].severity == "RED"
    assert evidence.findings[0].description == "checkout button crashes"


def test_run_uat_loads_credentials_from_env_file(
    fake_skill_script: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("TEST_USER=file-user\nTEST_PASSWORD=file-pass\n", encoding="utf-8")
    monkeypatch.setattr(uat_runner, "DEFAULT_ENV_FILE", env_file)
    monkeypatch.delenv("TEST_USER", raising=False)
    monkeypatch.delenv("TEST_PASSWORD", raising=False)

    captured_env: dict[str, str] = {}

    def subprocess_runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_env.update(kwargs["env"])
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="PASS: Login works\n",
            stderr="",
        )

    evidence = run_uat(
        UATRequest(app_path="demo/app", skill_path=str(fake_skill_script)),
        subprocess_runner=subprocess_runner,
    )

    assert evidence.summary == "UAT: 1/1 passed"
    assert evidence.verdict == "APPROVED"
    assert captured_env["TEST_USER"] == "file-user"
    assert captured_env["TEST_PASSWORD"] == "file-pass"


def test_run_uat_raises_clear_error_for_invalid_skill_path() -> None:
    with pytest.raises(UATExecutionError) as excinfo:
        run_uat(
            UATRequest(
                app_path="demo/app",
                skill_path="/tmp/does-not-exist-uat-skill",
                test_user="demo@atelier.dev",
                test_password="demo1234",
            )
        )

    assert "ATELIER_UAT_SKILL_PATH" in str(excinfo.value)
    assert "/tmp/does-not-exist-uat-skill" in str(excinfo.value)


def test_run_uat_raises_timeout_error(
    fake_skill_script: Path,
) -> None:
    def subprocess_runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs["timeout"])

    with pytest.raises(UATTimeoutError) as excinfo:
        run_uat(
            UATRequest(
                app_path="demo/app",
                skill_path=str(fake_skill_script),
                test_user="demo@atelier.dev",
                test_password="demo1234",
                timeout_seconds=5,
            ),
            subprocess_runner=subprocess_runner,
        )

    assert "timed out" in str(excinfo.value)
    assert "5s" in str(excinfo.value)


def make_manifest(
    *,
    provider: str = "openai",
    model: str = "test-model",
    tool_use: bool = True,
    structured_outputs: bool = False,
    parallel_tool_use: bool = False,
    long_context: int = 0,
    code_execution: bool = False,
    cost_per_mtok_in: float = 1.0,
    cost_per_mtok_out: float = 1.0,
) -> CapabilityManifest:
    return CapabilityManifest.model_validate(
        {
            "provider": provider,
            "model": model,
            "offers": {
                "tool_use": tool_use,
                "parallel_tool_use": parallel_tool_use,
                "long_context": long_context,
                "code_execution": code_execution,
                "structured_outputs": structured_outputs,
            },
            "cost_per_mtok_in": cost_per_mtok_in,
            "cost_per_mtok_out": cost_per_mtok_out,
        }
    )


def make_evidence_pack(*, summary: str, audit_id: str) -> EvidencePack:
    return EvidencePack(
        verdict="APPROVED",
        confidence=1.0,
        summary=summary,
        findings=[],
        execution=[],
        audit_chain=[audit_id],
        timestamp=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
        reviewer_persona_id="uat",
    )
