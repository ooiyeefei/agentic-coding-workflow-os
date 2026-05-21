from __future__ import annotations

import json
from pathlib import Path

import pytest
from spanweave.evidence import EvidencePack
from spanweave.workflow import load_workflow

from .artifacts import assert_run_artifact_completeness
from .conftest import IntegrationHarness


@pytest.mark.asyncio
async def test_full_speckit_loop_run_produces_expected_artifacts(
    mock_integration_harness: IntegrationHarness,
) -> None:
    result = await mock_integration_harness.run_full_workflow()
    workflow = load_workflow("speckit-loop")
    expected_stage_ids = [
        f"{index:03d}-{stage.id}"
        for index, stage in enumerate(workflow.stages, start=1)
    ]

    run_path = Path(".spanweave") / "runs" / result.run_id
    state = mock_integration_harness.read_state(result.run_id)
    verified_artifacts = assert_run_artifact_completeness(
        Path.cwd(),
        result.run_id,
        expected_stage_ids,
    )

    assert result.stage_ids == expected_stage_ids
    assert verified_artifacts
    assert f".spanweave/runs/{result.run_id}/.lock" in verified_artifacts
    assert f".spanweave/runs/{result.run_id}/audit.jsonl" in verified_artifacts
    assert (run_path / "run.md").is_file()
    assert (run_path / "workflow_state.yaml").is_file()
    assert state["status"] == "completed"
    assert result.approval_reasons.count("policy") == 2
    assert result.approval_reasons.count("gate") == 2

    for stage_id in expected_stage_ids:
        stage_path = run_path / "stages" / stage_id
        stage_md_path = stage_path / "stage.md"
        packet_path = stage_path / "packet.md"
        transcript_path = stage_path / "transcript.jsonl"
        evidence_md_path = stage_path / "evidence.md"
        evidence_json_path = stage_path / "evidence.json"

        assert stage_md_path.is_file()
        assert packet_path.is_file()
        assert transcript_path.is_file()
        assert evidence_md_path.is_file()
        assert evidence_json_path.is_file()
        assert (stage_path / ".complete").is_file()
        assert stage_id in stage_md_path.read_text(encoding="utf-8")
        assert "# Context Packet" in packet_path.read_text(encoding="utf-8")

        transcript_entries = [
            json.loads(line)
            for line in transcript_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert transcript_entries
        assert transcript_entries[0]["skill"]

        pack = EvidencePack.model_validate_json(evidence_json_path.read_text(encoding="utf-8"))
        assert pack.summary
        if stage_id.endswith("-uat"):
            assert transcript_entries[0]["persona"] == "uat"
            assert pack.reviewer_persona_id == "uat.integration"
            assert pack.summary == "UAT: 3/3 passed"
            assert pack.execution[0].command.startswith("mock-uat ")
        else:
            assert pack.reviewer_persona_id == "reviewer.integration"

    workflow_events = sorted(
        (Path(".spanweave") / "memory" / "workflow_events").glob("*.md")
    )
    assert workflow_events
    assert result.adr_paths
    assert all(path.is_file() for path in result.adr_paths)
    assert result.rebase_reports
    assert result.removed_worktrees
    assert not any(path.exists() for path in result.removed_worktrees)
