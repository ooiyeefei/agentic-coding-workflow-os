from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from spanweave.cli.main import main
from spanweave.compiler import estimate_tokens
from spanweave.memory import (
    Decision,
    RejectedAlternative,
    ReviewFinding,
    list_records,
    write_record,
)
from spanweave.session import generate_context, generate_prompt, ingest_transcript, resume


def test_resume_formats_same_run_context_for_claude_and_codex(
    tmp_path: Path,
    monkeypatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(tmp_path)

    claude = resume(fixed_run_id, "claude-code")
    codex = resume(fixed_run_id, "codex")

    assert claude != codex
    assert "# CLAUDE.md Context Packet" in claude
    assert "# AGENTS.md Context Packet" in codex
    for packet in (claude, codex):
        assert "Persist session continuity decisions in memory." in packet
        assert "Evidence captured tests that still need to run." in packet
        assert "Current stage: 002-implement" in packet
        assert "Completed stages: 001-specify" in packet
        assert "Pending stages: 003-review" in packet


def test_resume_packet_embeds_recent_stage_briefings(
    tmp_path: Path,
    monkeypatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    _seed_rich_stage_packets(tmp_path, fixed_run_id)
    monkeypatch.chdir(tmp_path)

    packet = resume(fixed_run_id, "claude-code")

    # The killer-demo pass criterion: a fresh agent reading this packet
    # must learn the substantive choice from the specify stage, not just
    # that "specify completed".
    assert "rate limit threshold of 5 attempts per 60-second" in packet, (
        "Resume packet did not embed substantive specify-stage content. "
        "A fresh agent cannot answer 'what was decided in specify?' from "
        "this packet alone."
    )
    # The briefing section should be discoverable by header.
    assert "## Recent Stage Context" in packet or "Stage Briefings" in packet


def test_resume_packet_briefings_survive_oversized_stage_packets(
    tmp_path: Path,
    monkeypatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Reproduces the original #66 scenario: stage packets large enough
    to exceed the session budget would previously cause the compiler to
    fall back to must-have sources only and drop all stage content.
    The briefing path must still surface the substantive content under
    those conditions.
    """
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    _seed_oversized_stage_packets(tmp_path, fixed_run_id)
    monkeypatch.chdir(tmp_path)

    packet = resume(fixed_run_id, "claude-code")

    assert "rate limit threshold of 5 attempts per 60-second" in packet, (
        "Resume packet dropped substantive specify-stage content when "
        "stage packets exceeded the session budget. A fresh agent "
        "cannot answer 'what was decided in specify?' from this packet."
    )
    assert "## Recent Stage Context" in packet or "Stage Briefings" in packet


def test_generate_prompt_adds_role_specific_protocols(
    tmp_path: Path,
    monkeypatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(tmp_path)

    coder = generate_prompt(fixed_run_id, "coder", "codex")
    reviewer = generate_prompt(fixed_run_id, "reviewer", "claude-code")

    assert "Implementation-focused protocol" in coder
    assert "Inspect the existing implementation before editing" in coder
    assert "# AGENTS.md Context Packet" in coder

    assert "Review-focused protocol" in reviewer
    assert "Execution is mandatory" in reviewer
    assert "findings ordered by severity" in reviewer
    assert "# CLAUDE.md Context Packet" in reviewer


def test_generate_prompt_does_not_duplicate_role_protocol_in_prior_decisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Regression for #67: the role protocol is injected as a Decision so the
    compiler can carry it, but it must render only once — as the leading
    directive, not again as a bullet inside ``## Prior Decisions``.
    """
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(tmp_path)

    coder = generate_prompt(fixed_run_id, "coder", "codex")

    # The protocol must still lead the prompt.
    assert "## Implementation-focused protocol" in coder
    assert "Inspect the existing implementation before editing" in coder

    # ...but it must not be repeated as a Decision bullet in Prior Decisions.
    prior_decisions = _section_body(coder, "## Prior Decisions")
    assert "Implementation-focused protocol" not in prior_decisions, (
        "Role protocol leaked into the Prior Decisions section; #67 regressed."
    )
    # The genuine decision seeded by the fixture must still survive the filter.
    assert "Persist session continuity decisions in memory." in prior_decisions

    # The protocol must not render as a human-readable directive twice. It may
    # still appear once more inside the Compiled Run Context as a provenance-
    # tracked source (see the provenance test), so we assert against the two
    # directive surfaces specifically rather than a global string count.
    assert coder.count("## Implementation-focused protocol") == 1


def test_resume_packet_links_disk_adrs_by_tag_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Regression for #73: the resume packet must surface ADRs on disk that
    match the run's tags even when no record carries a ``related_adrs``
    back-reference.
    """
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    _seed_tagged_record(tmp_path, fixed_run_id, fixed_ulid_values)
    _seed_workflow_validation_adrs(tmp_path)
    monkeypatch.chdir(tmp_path)

    packet = resume(fixed_run_id, "claude-code")

    adr_section = _section_body(packet, "## Relevant ADRs")
    assert "No ADRs referenced" not in adr_section, (
        "Resume packet failed to link workflow-validation ADRs on disk; #73 regressed."
    )
    assert "ADR-0001" in adr_section
    assert "ADR-0002" in adr_section


def test_generate_context_is_standalone_and_budgeted(
    tmp_path: Path,
    monkeypatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(tmp_path)

    context = generate_context("chatgpt", 4000)

    assert "Standalone Spanweave memory context for chatgpt" in context
    assert "Persist session continuity decisions in memory." in context
    assert estimate_tokens(context) <= 4000


def test_ingest_transcript_persists_extracted_memory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transcript = tmp_path / "transcript.md"
    transcript.write_text(
        (
            "# User\n"
            "We need continuity.\n\n"
            "# Assistant\n"
            "Decision: Store resume prompts as paste-ready stdout.\n"
            "Finding: Clipboard-only output would block piping.\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    records = ingest_transcript(transcript, "generic")
    persisted = list_records(tmp_path / ".spanweave" / "memory")

    assert len(records) == 2
    assert len(persisted) == 2
    assert any(record.body == "Store resume prompts as paste-ready stdout." for record in persisted)


def test_ingest_transcript_recognizes_natural_language_decisions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transcript = tmp_path / "transcript.md"
    transcript.write_text(
        (
            "# User\n"
            "We need a durable database.\n\n"
            "# Assistant\n"
            "We decided to use PostgreSQL because session continuity needs "
            "queryable durable state across tools.\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    records = ingest_transcript(transcript, "generic")
    persisted = list_records(tmp_path / ".spanweave" / "memory")

    assert len(records) == 1
    assert len(persisted) == 1
    assert isinstance(persisted[0], Decision)
    assert (
        persisted[0].body
        == "Use PostgreSQL because session continuity needs queryable durable state across tools."
    )


def test_role_protocol_prompt_provenance_is_marked_in_memory_not_persisted(
    tmp_path: Path,
    monkeypatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(tmp_path)

    coder = generate_prompt(fixed_run_id, "coder", "codex")
    protocol_block = _source_block_containing(coder, "role-protocol")

    assert "Persistence: in-memory session prompt" in protocol_block
    assert "_Source: sample_doc" in protocol_block
    assert "| -_" in protocol_block
    assert ".spanweave/memory/" not in protocol_block


def test_session_cli_commands_support_json(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    transcript = tmp_path / "transcript.md"
    transcript.write_text(
        "# Assistant\nDecision: Ingest manual transcript decisions.\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    resume_result = runner.invoke(
        main,
        ["resume", "--repo", str(tmp_path), "--agent", "codex", "--run", fixed_run_id, "--json"],
    )
    assert resume_result.exit_code == 0
    assert json.loads(resume_result.output)["prompt"].startswith("# AGENTS.md Context Packet")

    prompt_result = runner.invoke(
        main,
        [
            "prompt",
            "--repo",
            str(tmp_path),
            "--role",
            "reviewer",
            "--agent",
            "claude-code",
            "--run",
            fixed_run_id,
            "--json",
        ],
    )
    assert prompt_result.exit_code == 0
    assert "Execution is mandatory" in json.loads(prompt_result.output)["prompt"]

    context_result = runner.invoke(
        main,
        ["context", "--repo", str(tmp_path), "--for", "chatgpt", "--limit", "4000", "--json"],
    )
    assert context_result.exit_code == 0
    context_payload = json.loads(context_result.output)
    assert context_payload["estimated_tokens"] <= 4000

    ingest_result = runner.invoke(
        main,
        ["ingest", "--repo", str(tmp_path), "--from", str(transcript), "--json"],
    )
    assert ingest_result.exit_code == 0
    assert json.loads(ingest_result.output)["record_count"] == 1


def _source_block_containing(text: str, needle: str) -> str:
    needle_index = text.index(needle)
    start = text.rfind("\n## ", 0, needle_index)
    end = text.find("\n## ", needle_index)
    if start == -1:
        start = 0
    if end == -1:
        end = len(text)
    return text[start:end]


def _section_body(text: str, header: str) -> str:
    """Return the body of a ``## `` section up to the next ``## `` header."""
    start = text.index(header) + len(header)
    end = text.find("\n## ", start)
    if end == -1:
        end = len(text)
    return text[start:end]


def _seed_repo(repo_root: Path, run_id: str, fixed_ulid_values: list[str]) -> None:
    _seed_tool_files(repo_root)
    _seed_run(repo_root, run_id)
    _seed_memory(repo_root, run_id, fixed_ulid_values)


def _seed_tool_files(repo_root: Path) -> None:
    (repo_root / ".claude" / "rules").mkdir(parents=True)
    (repo_root / "CLAUDE.md").write_text("# Claude rules\n", encoding="utf-8")
    (repo_root / ".claude" / "rules" / "session.md").write_text(
        "# Session rules\n",
        encoding="utf-8",
    )
    (repo_root / "AGENTS.md").write_text("# Agent rules\n", encoding="utf-8")


def _seed_run(repo_root: Path, run_id: str) -> None:
    run_root = repo_root / ".spanweave" / "runs" / run_id
    (run_root / "stages" / "001-specify" / "decisions").mkdir(parents=True)
    (run_root / "stages" / "001-specify" / "findings").mkdir()
    (run_root / "stages" / "001-specify" / ".complete").write_text(
        "complete\n",
        encoding="utf-8",
    )
    (run_root / "stages" / "001-specify" / "stage.md").write_text(
        "# Stage 001\nSpecification completed.\n",
        encoding="utf-8",
    )
    (run_root / "stages" / "001-specify" / "evidence.md").write_text(
        "Evidence captured accepted scope.\n",
        encoding="utf-8",
    )

    (run_root / "stages" / "002-implement" / "decisions").mkdir(parents=True)
    (run_root / "stages" / "002-implement" / "findings").mkdir()
    (run_root / "stages" / "002-implement" / "stage.md").write_text(
        "# Stage 002\nImplementation in progress.\n",
        encoding="utf-8",
    )
    (run_root / "stages" / "002-implement" / "evidence.md").write_text(
        "Evidence captured tests that still need to run.\n",
        encoding="utf-8",
    )
    (run_root / "stages" / "002-implement" / "decisions" / "session.md").write_text(
        "Decision: Keep resume and prompt commands separate.\n",
        encoding="utf-8",
    )

    (run_root / "stages" / "003-review" / "decisions").mkdir(parents=True)
    (run_root / "stages" / "003-review" / "findings").mkdir()
    (run_root / "stages" / "003-review" / "stage.md").write_text(
        "# Stage 003\nReview pending.\n",
        encoding="utf-8",
    )
    (run_root / "workflow_state.yaml").write_text(
        "workflow: speckit-loop\nstatus: running\nwaiting_reason: gate\n",
        encoding="utf-8",
    )
    (run_root / "run.md").write_text(
        f"---\nrun_id: {run_id}\nissue_ref: issue #52\n---\n# Run\n",
        encoding="utf-8",
    )


def _seed_rich_stage_packets(repo_root: Path, run_id: str) -> None:
    """Write substantive packet.md content to seeded stages.

    Mirrors the real-run shape where each stage has a ~200-line packet.md
    capturing the issue text, acceptance criteria, and clarified constraints.
    """
    run_root = repo_root / ".spanweave" / "runs" / run_id
    specify_packet = run_root / "stages" / "001-specify" / "packet.md"
    specify_packet.write_text(
        (
            "# Context Packet\n\n"
            "## Objective\n"
            "_Source: objective | objective | -_\n\n"
            "Specify the rate limit feature for the demo app.\n\n"
            "## Demo App: Rate limit failed POST /login attempts\n"
            "_Source: issue_text | demo-issue | demo/issue.md_\n\n"
            "Decided rate limit threshold of 5 attempts per 60-second rolling "
            "window per IP. Retry-After is rounded up to the next integer "
            "and never returns 0 while the IP is still blocked.\n\n"
            "## Acceptance Criteria\n\n"
            "1. Failed login attempts 1-5 process normally; attempt 6 returns 429.\n"
            "2. Retry-After header is required on every 429.\n"
        ),
        encoding="utf-8",
    )
    implement_packet = run_root / "stages" / "002-implement" / "packet.md"
    implement_packet.write_text(
        (
            "# Context Packet\n\n"
            "## Objective\n"
            "_Source: objective | objective | -_\n\n"
            "Implement the rate-limit middleware behind FastAPI.\n"
        ),
        encoding="utf-8",
    )


def _seed_oversized_stage_packets(repo_root: Path, run_id: str) -> None:
    """Mirror the real-run shape: each stage carries a ~14k-token packet.md
    that, in aggregate, exceeds the default session budget. This forces the
    compiler's must-only fallback path and exposes the bug from issue #66.
    """
    run_root = repo_root / ".spanweave" / "runs" / run_id
    filler = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 200
    specify_packet = run_root / "stages" / "001-specify" / "packet.md"
    specify_packet.write_text(
        (
            "# Context Packet\n\n"
            "## Objective\n"
            "_Source: objective | objective | -_\n\n"
            "Specify the rate limit feature for the demo app.\n\n"
            "## Demo App: Rate limit failed POST /login attempts\n"
            "_Source: issue_text | demo-issue | demo/issue.md_\n\n"
            "Decided rate limit threshold of 5 attempts per 60-second rolling "
            "window per IP. Retry-After is rounded up to the next integer.\n\n"
            f"## Filler context that pushes the packet past the budget\n\n{filler}\n"
        ),
        encoding="utf-8",
    )
    implement_packet = run_root / "stages" / "002-implement" / "packet.md"
    implement_packet.write_text(
        (
            "# Context Packet\n\n"
            "## Objective\n"
            "_Source: objective | objective | -_\n\n"
            "Implement the rate-limit middleware behind FastAPI.\n\n"
            f"## Filler context\n\n{filler}\n"
        ),
        encoding="utf-8",
    )
    review_packet = run_root / "stages" / "003-review" / "packet.md"
    review_packet.write_text(
        (
            "# Context Packet\n\n"
            "## Objective\n"
            "_Source: objective | objective | -_\n\n"
            "Review the rate-limit implementation.\n\n"
            f"## Filler context\n\n{filler}\n"
        ),
        encoding="utf-8",
    )


def _seed_memory(repo_root: Path, run_id: str, fixed_ulid_values: list[str]) -> None:
    memory_root = repo_root / ".spanweave" / "memory"
    timestamp = datetime(2026, 4, 24, 0, 0, tzinfo=UTC)
    run_stage_id = f"stage_{fixed_ulid_values[1]}"
    other_run_id = f"run_{fixed_ulid_values[8]}"
    other_stage_id = f"stage_{fixed_ulid_values[9]}"
    records = [
        Decision(
            id=f"decision_{fixed_ulid_values[2]}",
            run_id=run_id,
            stage_id=run_stage_id,
            timestamp=timestamp,
            source="test",
            body="Persist session continuity decisions in memory.",
        ),
        ReviewFinding(
            id=f"review_finding_{fixed_ulid_values[3]}",
            run_id=run_id,
            stage_id=run_stage_id,
            timestamp=timestamp,
            source="test",
            body="Resume command must include done versus pending work.",
        ),
        Decision(
            id=f"decision_{fixed_ulid_values[4]}",
            run_id=other_run_id,
            stage_id=other_stage_id,
            timestamp=timestamp,
            source="test",
            body="Use durable memory as cross-run context.",
        ),
    ]
    for record in records:
        write_record(record, memory_root)


def _seed_tagged_record(repo_root: Path, run_id: str, fixed_ulid_values: list[str]) -> None:
    """Seed a record whose tags match the workflow-validation ADRs but whose
    ``related_adrs`` is empty — the #73 shape."""
    memory_root = repo_root / ".spanweave" / "memory"
    write_record(
        RejectedAlternative(
            id=f"rejected_alternative_{fixed_ulid_values[20]}",
            run_id=run_id,
            stage_id=f"stage_{fixed_ulid_values[1]}",
            timestamp=datetime(2026, 4, 24, 0, 0, tzinfo=UTC),
            related_adrs=[],
            tags=["workflow-validation", "artifact-minimization"],
            source="integration-harness",
            body="Keep workflow validation in memory only.",
        ),
        memory_root,
    )


def _seed_workflow_validation_adrs(repo_root: Path) -> None:
    adr_dir = repo_root / "docs" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
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
