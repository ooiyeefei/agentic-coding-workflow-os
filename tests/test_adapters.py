from __future__ import annotations

from pathlib import Path

import pytest
from spanweave.adapters import (
    DEFAULT_ADAPTER_MANIFEST_DIR,
    ClaudeCodeAdapter,
    CodexAdapter,
    GenericAdapter,
    detect_active_adapter,
    load_tool_manifest,
    load_tool_manifests,
)
from spanweave.memory import (
    Decision,
    RejectedAlternative,
    ReviewFinding,
    list_records,
    write_record,
)

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

    memory_root = tmp_path / ".spanweave" / "memory"
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


def test_relevant_adrs_surfaces_disk_adrs_by_tag_match(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Regression for #73: ADRs on disk must surface even when no record
    carries a ``related_adrs`` back-reference, matched by the run's tags
    against the ADR frontmatter/title/drivers.
    """
    _seed_workflow_validation_adrs(tmp_path)
    stage_id = f"stage_{fixed_ulid_values[1]}"
    records = [
        RejectedAlternative(
            id=f"rejected_alternative_{fixed_ulid_values[2]}",
            run_id=fixed_run_id,
            stage_id=stage_id,
            related_adrs=[],
            tags=["workflow-validation", "artifact-minimization"],
            source="integration-harness",
            body="Keep workflow validation in memory only.",
        ),
    ]

    packet = ClaudeCodeAdapter(repo_root=tmp_path).format_context_packet(
        fixed_run_id,
        "resume",
        records,
    )

    adr_section = _section_body(packet, "## Relevant ADRs")
    assert "No ADRs referenced" not in adr_section
    assert "ADR-0001" in adr_section
    assert "ADR-0002" in adr_section
    assert "Workflow Validation" in adr_section
    # De-dupe: each ADR id appears at most once.
    assert adr_section.count("ADR-0001") == 1
    assert adr_section.count("ADR-0002") == 1


def test_relevant_adrs_keeps_related_adrs_backreference_and_dedupes(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """The explicit ``related_adrs`` path must keep working, and an ADR
    reachable both by back-reference and by tag match appears once.
    """
    _seed_workflow_validation_adrs(tmp_path)
    stage_id = f"stage_{fixed_ulid_values[1]}"
    records = [
        Decision(
            id=f"decision_{fixed_ulid_values[2]}",
            run_id=fixed_run_id,
            stage_id=stage_id,
            related_adrs=["ADR-0001"],
            tags=["workflow-validation"],
            source="integration-harness",
            body="Persist workflow evidence for 001-specify.",
        ),
    ]

    packet = ClaudeCodeAdapter(repo_root=tmp_path).format_context_packet(
        fixed_run_id,
        "resume",
        records,
    )

    adr_section = _section_body(packet, "## Relevant ADRs")
    # ADR-0001 is reachable both via related_adrs and via the tag match;
    # it must appear exactly once.
    assert adr_section.count("ADR-0001") == 1
    # ADR-0002 is reachable only via the tag match (workflow-validation).
    assert "ADR-0002" in adr_section


def test_relevant_adrs_reports_missing_referenced_file(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """A back-referenced ADR with no file on disk still reports the gap."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    stage_id = f"stage_{fixed_ulid_values[1]}"
    records = [
        Decision(
            id=f"decision_{fixed_ulid_values[2]}",
            run_id=fixed_run_id,
            stage_id=stage_id,
            related_adrs=["ADR-0099"],
            source="test",
            body="Reference a missing ADR.",
        ),
    ]

    packet = ClaudeCodeAdapter(repo_root=tmp_path).format_context_packet(
        fixed_run_id,
        "resume",
        records,
    )

    adr_section = _section_body(packet, "## Relevant ADRs")
    assert "ADR-0099" in adr_section
    assert "file not found" in adr_section


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


def _section_body(text: str, header: str) -> str:
    """Return the body of a ``## `` section up to the next ``## `` header."""
    start = text.index(header) + len(header)
    end = text.find("\n## ", start)
    if end == -1:
        end = len(text)
    return text[start:end]


def _seed_workflow_validation_adrs(repo_root: Path) -> None:
    """Write two MADR-style ADRs whose title/drivers match the dogfood run's
    tags (``workflow-validation``, ``artifact-minimization``) but whose source
    records carry empty ``related_adrs`` — the exact #73 shape.
    """
    adr_dir = repo_root / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    body = (
        "---\n"
        'status: "accepted"\n'
        "date: 2026-04-22\n"
        "decision-makers: integration-harness\n"
        "---\n\n"
        "# Workflow Validation\n\n"
        "## Context and Problem Statement\n\n"
        "The 001-specify stage stores packet, transcript, and evidence "
        "artifacts directly on disk for replay and inspection.\n\n"
        "## Decision Drivers\n\n"
        "* artifact-minimization\n"
        "* specify\n"
    )
    (adr_dir / "0001-workflow-validation.md").write_text(body, encoding="utf-8")
    (adr_dir / "0002-workflow-validation.md").write_text(body, encoding="utf-8")


def _seed_run_state(repo_root: Path, run_id: str) -> None:
    run_root = repo_root / ".spanweave" / "runs" / run_id
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
