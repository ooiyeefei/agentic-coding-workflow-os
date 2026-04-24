from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from atelier.cli.main import main
from atelier.compiler import estimate_tokens
from atelier.memory import Decision, ReviewFinding, list_records, write_record
from atelier.session import generate_context, generate_prompt, ingest_transcript, resume
from click.testing import CliRunner


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


def test_generate_context_is_standalone_and_budgeted(
    tmp_path: Path,
    monkeypatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    _seed_repo(tmp_path, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(tmp_path)

    context = generate_context("chatgpt", 4000)

    assert "Standalone Atelier memory context for chatgpt" in context
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
    persisted = list_records(tmp_path / ".atelier" / "memory")

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
    persisted = list_records(tmp_path / ".atelier" / "memory")

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
    assert ".atelier/memory/" not in protocol_block


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
    run_root = repo_root / ".atelier" / "runs" / run_id
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


def _seed_memory(repo_root: Path, run_id: str, fixed_ulid_values: list[str]) -> None:
    memory_root = repo_root / ".atelier" / "memory"
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
