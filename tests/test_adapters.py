from __future__ import annotations

from pathlib import Path

import pytest
from atelier.adapters import (
    DEFAULT_ADAPTER_MANIFEST_DIR,
    ClaudeCodeAdapter,
    CodexAdapter,
    GenericAdapter,
    detect_active_adapter,
    load_tool_manifest,
    load_tool_manifests,
)
from atelier.memory import Decision, RejectedAlternative, ReviewFinding, list_records, write_record

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "adapters"


def test_load_tool_manifests_reads_shipped_yaml_files() -> None:
    manifests = load_tool_manifests(DEFAULT_ADAPTER_MANIFEST_DIR)

    assert len(manifests) == 2

    claude_manifest = load_tool_manifest(DEFAULT_ADAPTER_MANIFEST_DIR / "claude-code.yaml")
    codex_manifest = load_tool_manifest(DEFAULT_ADAPTER_MANIFEST_DIR / "codex.yaml")

    assert claude_manifest.session_format == "jsonl"
    assert "mcp" in claude_manifest.capabilities
    assert codex_manifest.config_paths == ["AGENTS.md", "codex.md"]


def test_claude_code_adapter_ingests_fixture_and_records_can_be_written(
    tmp_path: Path,
) -> None:
    adapter = ClaudeCodeAdapter(repo_root=tmp_path)
    session_path = FIXTURE_ROOT / "claude" / "projects" / "sample-project" / "session.jsonl"

    records = adapter.ingest_transcript(session_path)

    decisions = [record for record in records if isinstance(record, Decision)]
    findings = [record for record in records if isinstance(record, ReviewFinding)]

    assert len(decisions) >= 3
    assert findings

    memory_root = tmp_path / ".atelier" / "memory"
    for record in records:
        write_record(record, memory_root)

    persisted = list_records(memory_root)
    assert len(persisted) == len(records)


def test_codex_adapter_ingests_rollout_fixture(tmp_path: Path) -> None:
    adapter = CodexAdapter(repo_root=tmp_path)
    session_path = (
        FIXTURE_ROOT
        / "codex"
        / "sessions"
        / "2026"
        / "04"
        / "23"
        / "rollout-sample.jsonl"
    )

    records = adapter.ingest_transcript(session_path)

    decisions = [record for record in records if isinstance(record, Decision)]
    findings = [record for record in records if isinstance(record, ReviewFinding)]

    assert len(decisions) >= 3
    assert len(findings) == 1
    assert all(record.source.startswith("codex:") for record in records)


def test_generic_adapter_ingests_markdown_fixture(tmp_path: Path) -> None:
    adapter = GenericAdapter(repo_root=tmp_path)
    session_path = FIXTURE_ROOT / "generic" / "transcript.md"

    records = adapter.ingest_transcript(session_path)

    assert any(isinstance(record, Decision) for record in records)
    assert any(isinstance(record, RejectedAlternative) for record in records)


def test_claude_and_codex_packets_include_decisions_adrs_and_run_state(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    _seed_tool_repo(tmp_path)
    _seed_run_state(tmp_path, fixed_run_id)
    memory_records = _sample_memory_records(fixed_run_id, fixed_ulid_values)

    claude_packet = ClaudeCodeAdapter(repo_root=tmp_path).format_context_packet(
        fixed_run_id,
        "coder",
        memory_records,
    )
    codex_packet = CodexAdapter(repo_root=tmp_path).format_context_packet(
        fixed_run_id,
        "coder",
        memory_records,
    )

    assert "CLAUDE.md" in claude_packet
    assert ".claude/rules/" in claude_packet
    assert "## Prior Decisions" in claude_packet
    assert "## Relevant ADRs" in claude_packet
    assert "ADR-0001" in claude_packet
    assert "## Current Run State" in claude_packet
    assert "Workflow: speckit-loop" in claude_packet
    assert "002-implement [current]" in claude_packet

    assert "AGENTS.md" in codex_packet
    assert "## Prior Decisions" in codex_packet
    assert "## Relevant ADRs" in codex_packet
    assert "## Current Run State" in codex_packet


def test_detection_distinguishes_claude_codex_and_generic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claude_root = tmp_path / "claude"
    claude_root.mkdir()
    (claude_root / ".claude").mkdir()

    codex_root = tmp_path / "codex"
    codex_root.mkdir()
    (codex_root / "AGENTS.md").write_text("# Codex rules\n", encoding="utf-8")

    neutral_root = tmp_path / "neutral"
    neutral_root.mkdir()

    monkeypatch.setenv("CODEX_THREAD_ID", "thread-fixture")

    assert ClaudeCodeAdapter(repo_root=claude_root).detect() is True
    assert CodexAdapter(repo_root=codex_root).detect() is True
    assert GenericAdapter(repo_root=neutral_root).detect() is False

    active = detect_active_adapter(codex_root)
    assert isinstance(active, CodexAdapter)

    monkeypatch.delenv("CODEX_THREAD_ID")
    monkeypatch.delenv("CODEX_CI", raising=False)
    monkeypatch.delenv("CODEX_MANAGED_BY_NPM", raising=False)
    assert CodexAdapter(repo_root=codex_root).detect() is False


def _sample_memory_records(
    run_id: str,
    fixed_ulid_values: list[str],
) -> list[Decision | ReviewFinding]:
    stage_id = f"stage_{fixed_ulid_values[1]}"
    return [
        Decision(
            id=f"decision_{fixed_ulid_values[2]}",
            run_id=run_id,
            stage_id=stage_id,
            related_adrs=["ADR-0001"],
            source="claude-code:fixture",
            body="Use heuristic extraction for phase 0.",
        ),
        Decision(
            id=f"decision_{fixed_ulid_values[3]}",
            run_id=run_id,
            stage_id=stage_id,
            related_adrs=["ADR-0001"],
            source="codex:fixture",
            body="Treat rollout JSONL as the Codex transcript source.",
        ),
        ReviewFinding(
            id=f"review_finding_{fixed_ulid_values[4]}",
            run_id=run_id,
            stage_id=stage_id,
            source="codex:fixture",
            body="history.jsonl only stores user input history.",
        ),
    ]


def _seed_tool_repo(repo_root: Path) -> None:
    (repo_root / ".claude" / "rules").mkdir(parents=True)
    (repo_root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    (repo_root / ".claude" / "rules" / "adapter.md").write_text(
        "# Adapter rules\n",
        encoding="utf-8",
    )
    (repo_root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    adr_dir = repo_root / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-context-transfer.md").write_text(
        "---\nstatus: accepted\n---\n# Context Transfer\n",
        encoding="utf-8",
    )


def _seed_run_state(repo_root: Path, run_id: str) -> None:
    run_root = repo_root / ".atelier" / "runs" / run_id
    (run_root / "stages" / "001-specify").mkdir(parents=True)
    (run_root / "stages" / "001-specify" / ".complete").write_text(
        "complete\n",
        encoding="utf-8",
    )
    (run_root / "stages" / "002-implement").mkdir(parents=True)
    (run_root / "workflow_state.yaml").write_text(
        (
            "workflow: speckit-loop\n"
            "status: running\n"
            "waiting_reason: gate\n"
        ),
        encoding="utf-8",
    )
    (run_root / "run.md").write_text(
        (
            "---\n"
            f"run_id: {run_id}\n"
            "issue_ref: issue #51\n"
            "---\n"
            "# Run\n"
        ),
        encoding="utf-8",
    )
