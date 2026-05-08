from __future__ import annotations

import json

import pytest
from spanweave.evidence import EvidencePack, Verdict
from spanweave.rungraph import create_run, create_stage, list_stages
from spanweave.workflow import RunStatus, WorkflowEngine

from .conftest import IntegrationHarness


@pytest.mark.asyncio
async def test_compiler_packet_reaches_persona(
    integration_harness: IntegrationHarness,
) -> None:
    run_id = create_run("issue #24")
    create_stage(run_id, "specify")
    integration_harness.attach_run(run_id)

    persona_result = await integration_harness.persona_caller.call(
        "coder",
        integration_harness.workspace.issue_text,
        skill="speckit.specify",
        run_id=run_id,
    )

    stage_id = integration_harness.current_stage_id(run_id)
    packet_path = integration_harness.stage_path(run_id, stage_id) / "packet.md"
    transcript_path = integration_harness.stage_path(run_id, stage_id) / "transcript.jsonl"

    assert packet_path.read_text(encoding="utf-8").startswith("# Context Packet")
    assert "Rate limit failed `POST /login` attempts" in packet_path.read_text(encoding="utf-8")
    transcript_entries = [
        json.loads(line)
        for line in transcript_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert transcript_entries
    assert transcript_entries[0]["persona"] == "coder"
    assert transcript_entries[0]["skill"] == "speckit.specify"
    assert persona_result.content
    if integration_harness.persona_mode == "real":
        assert integration_harness.coder_persona.adapter.manifest.provider in {
            "openai",
            "anthropic",
        }
    else:
        assert integration_harness.coder_persona.adapter.manifest.provider == "mock"


@pytest.mark.asyncio
async def test_uat_persona_output_persists_runner_evidence_pack(
    mock_integration_harness: IntegrationHarness,
) -> None:
    run_id = create_run("issue #24")
    stage_id = create_stage(run_id, "uat")

    persona_result = await mock_integration_harness.persona_caller.call(
        "uat",
        mock_integration_harness.workspace.issue_text,
        skill="uat-test",
        run_id=run_id,
    )
    pack = mock_integration_harness.evidence_writer.write(
        run_id,
        stage_id,
        Verdict.APPROVED,
        persona_result,
    )

    evidence_json_path = mock_integration_harness.stage_path(run_id, stage_id) / "evidence.json"
    evidence_md_path = mock_integration_harness.stage_path(run_id, stage_id) / "evidence.md"
    loaded = EvidencePack.model_validate_json(evidence_json_path.read_text(encoding="utf-8"))

    assert loaded == pack
    assert evidence_md_path.is_file()
    assert loaded.reviewer_persona_id == "uat.integration"
    assert loaded.summary == "UAT: 3/3 passed"
    assert loaded.execution[0].command.startswith("mock-uat ")


@pytest.mark.asyncio
async def test_workflow_engine_advances_and_marks_rungraph(
    mock_integration_harness: IntegrationHarness,
) -> None:
    engine = WorkflowEngine(deps=mock_integration_harness.deps)
    run_id = engine.start("issue #24", context=mock_integration_harness.workspace.issue_text)
    mock_integration_harness.attach_run(run_id)

    for _ in range(3):
        result = await engine.advance(run_id)
        while result.run_status == RunStatus.WAITING_APPROVAL:
            result = await engine.resume(run_id, approved=True)

    stage_ids = list_stages(run_id)
    state = mock_integration_harness.read_state(run_id)

    assert stage_ids[:4] == ["001-specify", "002-clarify", "003-plan", "004-tasks"]
    assert state["cursor"] == 3
    assert state["status"] == "running"
    for stage_id in stage_ids[:3]:
        assert (mock_integration_harness.stage_path(run_id, stage_id) / ".complete").is_file()
    assert not (mock_integration_harness.stage_path(run_id, "004-tasks") / ".complete").exists()


@pytest.mark.asyncio
async def test_adr_synthesis_uses_memory_records_from_harness(
    mock_integration_harness: IntegrationHarness,
) -> None:
    run_id = create_run("issue #24")
    implement_stage = create_stage(run_id, "implement")
    uat_stage = create_stage(run_id, "uat")

    implement_result = await mock_integration_harness.persona_caller.call(
        "coder",
        mock_integration_harness.workspace.issue_text,
        skill="speckit.implement",
        run_id=run_id,
    )
    mock_integration_harness.evidence_writer.write(
        run_id,
        implement_stage,
        Verdict.APPROVED,
        implement_result,
    )
    uat_result = await mock_integration_harness.persona_caller.call(
        "uat",
        mock_integration_harness.workspace.issue_text,
        skill="uat-test",
        run_id=run_id,
    )
    mock_integration_harness.evidence_writer.write(
        run_id,
        uat_stage,
        Verdict.APPROVED,
        uat_result,
    )

    adr_paths = mock_integration_harness.synthesize_adrs(run_id)

    assert adr_paths
    adr_text = adr_paths[0].read_text(encoding="utf-8").lower()
    assert "workflow validation" in adr_text
    assert "decision-makers:" in adr_text
