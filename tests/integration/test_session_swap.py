"""Integration coverage for the W28 Session Continuity layer.

The killer feature: a run started in one agent tool can be resumed cleanly in
another agent tool, with all decisions intact and the current stage cursor
preserved. These tests simulate the full async handoff:

    Codex captures decisions during a run
        |
        v
    `spanweave resume --agent claude-code --run <id>` formats them for Claude Code
        |
        v
    Output prompt contains every decision plus the run cursor.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from spanweave.adapters import CodexAdapter
from spanweave.memory import Decision, RejectedAlternative, ReviewFinding, write_record
from spanweave.session import generate_context, generate_prompt, resume

_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "adapters"
_CODEX_FIXTURE = (
    _FIXTURE_ROOT / "codex" / "sessions" / "2026" / "04" / "23" / "rollout-sample.jsonl"
)


def _seed_repo_with_codex_run(
    repo_root: Path,
    run_id: str,
    fixed_ulid_values: list[str],
) -> tuple[list[Decision], list[ReviewFinding], list[RejectedAlternative]]:
    """Seed a fixture run as if it were captured by the Codex adapter.

    The repo carries:
    * Tool-convention files for Claude Code AND Codex (both possible targets).
    * A run directory with one completed stage and one current stage.
    * Memory records: decisions and findings ingested from a Codex session.
    * Plus a manually-authored RejectedAlternative to verify the resume packet
      surfaces ALL record types.
    """

    (repo_root / ".claude" / "rules").mkdir(parents=True)
    (repo_root / "CLAUDE.md").write_text("# Claude rules\n", encoding="utf-8")
    (repo_root / ".claude" / "rules" / "swap.md").write_text(
        "# Session swap rules\n",
        encoding="utf-8",
    )
    (repo_root / "AGENTS.md").write_text("# Agent rules\n", encoding="utf-8")

    run_root = repo_root / ".spanweave" / "runs" / run_id

    # Completed plan stage with full artifacts so the compiler picks them up.
    plan_stage = run_root / "stages" / "001-plan"
    (plan_stage / "decisions").mkdir(parents=True)
    (plan_stage / "findings").mkdir()
    (plan_stage / ".complete").write_text("complete\n", encoding="utf-8")
    (plan_stage / "stage.md").write_text(
        "# Stage 001-plan\nPlan accepted.\n",
        encoding="utf-8",
    )
    (plan_stage / "evidence.md").write_text(
        "Stage plan evidence captured by Codex.\n",
        encoding="utf-8",
    )
    (plan_stage / "packet.md").write_text(
        "# Context Packet\nPlan packet content.\n",
        encoding="utf-8",
    )

    # Current implement stage with partial artifacts.
    impl_stage = run_root / "stages" / "002-implement"
    (impl_stage / "decisions").mkdir(parents=True)
    (impl_stage / "findings").mkdir()
    (impl_stage / "stage.md").write_text(
        "# Stage 002-implement\nImplement in progress.\n",
        encoding="utf-8",
    )
    (impl_stage / "evidence.md").write_text(
        "Implement evidence partially gathered by Codex.\n",
        encoding="utf-8",
    )

    # Pending review stage that must show up in the cursor.
    review_stage = run_root / "stages" / "003-review"
    (review_stage / "decisions").mkdir(parents=True)
    (review_stage / "findings").mkdir()
    (review_stage / "stage.md").write_text(
        "# Stage 003-review\nReview pending.\n",
        encoding="utf-8",
    )

    (run_root / "workflow_state.yaml").write_text(
        "workflow: speckit-loop\nstatus: running\nwaiting_reason: agent_tool\n",
        encoding="utf-8",
    )
    (run_root / "run.md").write_text(
        f"---\nrun_id: {run_id}\nissue_ref: issue #999\n---\n# Run\n",
        encoding="utf-8",
    )

    memory_root = repo_root / ".spanweave" / "memory"
    timestamp = datetime(2026, 4, 24, 0, 0, tzinfo=UTC)
    stage_id = f"stage_{fixed_ulid_values[1]}"

    decisions = [
        Decision(
            id=f"decision_{fixed_ulid_values[2]}",
            run_id=run_id,
            stage_id=stage_id,
            related_adrs=["ADR-0042"],
            timestamp=timestamp,
            source="codex:fixture",
            body=(
                "Use rollout JSONL as the canonical Codex transcript surface "
                "for cross-tool transfer."
            ),
        ),
        Decision(
            id=f"decision_{fixed_ulid_values[3]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=timestamp,
            source="codex:fixture",
            body=(
                "Treat AGENTS.md as the primary Codex convention file when "
                "formatting context packets."
            ),
        ),
        Decision(
            id=f"decision_{fixed_ulid_values[4]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=timestamp,
            source="codex:fixture",
            body="Include current run state in every formatted packet.",
        ),
    ]

    findings = [
        ReviewFinding(
            id=f"review_finding_{fixed_ulid_values[5]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=timestamp,
            source="codex:fixture",
            body=(
                "history.jsonl only stores user input and is not enough for "
                "full session replay."
            ),
        ),
    ]

    rejected = [
        RejectedAlternative(
            id=f"rejected_alternative_{fixed_ulid_values[6]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=timestamp,
            source="codex:fixture",
            body=(
                "Embed full transcripts inside the packet instead of memory records.\n"
                "Reason: would balloon the packet beyond any practical token budget."
            ),
        ),
    ]

    for record in [*decisions, *findings, *rejected]:
        write_record(record, memory_root)

    return decisions, findings, rejected


def test_resume_from_codex_run_to_claude_code_preserves_all_decisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """The killer feature — start in Codex, resume in Claude Code, lose nothing."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    decisions, findings, rejected = _seed_repo_with_codex_run(
        repo_root, fixed_run_id, fixed_ulid_values,
    )
    monkeypatch.chdir(repo_root)

    prompt = resume(fixed_run_id, "claude-code")

    # 1. Claude Code framing.
    assert prompt.startswith("# CLAUDE.md Context Packet")
    assert "Read `CLAUDE.md` before acting." in prompt
    assert ".claude/rules/" in prompt

    # 2. Every Codex-originated decision body appears verbatim in the resumed prompt.
    for decision in decisions:
        first_line = decision.body.splitlines()[0].strip()
        assert first_line in prompt, f"decision lost on swap: {first_line!r}"

    # 3. Findings and rejected alternatives also survive.
    for finding in findings:
        assert finding.body.splitlines()[0].strip() in prompt
    for rejected_record in rejected:
        assert rejected_record.body.splitlines()[0].strip() in prompt

    # 4. The current stage cursor is conveyed so the new agent picks up correctly.
    assert "Current stage: 002-implement" in prompt
    assert "Completed stages: 001-plan" in prompt
    assert "Pending stages: 003-review" in prompt

    # 5. Run identifier is preserved.
    assert fixed_run_id in prompt

    # 6. ADR references survive (one decision tagged ADR-0042).
    assert "ADR-0042" in prompt


def test_resume_to_codex_uses_agents_md_framing_for_same_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Resuming the SAME Codex-captured run in Codex itself should still work."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    decisions, _, _ = _seed_repo_with_codex_run(
        repo_root, fixed_run_id, fixed_ulid_values,
    )
    monkeypatch.chdir(repo_root)

    prompt = resume(fixed_run_id, "codex")

    assert prompt.startswith("# AGENTS.md Context Packet")
    for decision in decisions:
        first_line = decision.body.splitlines()[0].strip()
        assert first_line in prompt
    assert "Current stage: 002-implement" in prompt


def test_resume_packets_for_claude_and_codex_differ_in_structure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Equivalent input -> divergent tool-convention framing per agent."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _seed_repo_with_codex_run(repo_root, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(repo_root)

    claude_prompt = resume(fixed_run_id, "claude-code")
    codex_prompt = resume(fixed_run_id, "codex")
    generic_prompt = resume(fixed_run_id, "generic")

    assert claude_prompt != codex_prompt
    assert claude_prompt != generic_prompt
    assert codex_prompt != generic_prompt

    assert "CLAUDE.md" in claude_prompt.splitlines()[0]
    assert "AGENTS.md" in codex_prompt.splitlines()[0]
    assert "Tool Context Packet" in generic_prompt


def test_resume_with_codex_session_file_decisions_carry_forward(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
) -> None:
    """End-to-end: ingest the Codex session fixture, then resume in Claude Code."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".claude" / "rules").mkdir(parents=True)
    (repo_root / "CLAUDE.md").write_text("# Claude rules\n", encoding="utf-8")
    (repo_root / "AGENTS.md").write_text("# Agent rules\n", encoding="utf-8")

    monkeypatch.chdir(repo_root)

    codex_adapter = CodexAdapter(repo_root=repo_root)
    codex_records = codex_adapter.ingest_transcript(_CODEX_FIXTURE)
    assert codex_records
    memory_root = repo_root / ".spanweave" / "memory"
    for record in codex_records:
        write_record(record, memory_root)

    # Seed minimal run state so the resume command knows the cursor.
    run_root = repo_root / ".spanweave" / "runs" / fixed_run_id
    plan_stage = run_root / "stages" / "001-specify"
    (plan_stage / "decisions").mkdir(parents=True)
    (plan_stage / "findings").mkdir()
    (plan_stage / ".complete").write_text("complete\n", encoding="utf-8")
    (plan_stage / "stage.md").write_text("# Stage 001\nDone.\n", encoding="utf-8")

    impl_stage = run_root / "stages" / "002-implement"
    (impl_stage / "decisions").mkdir(parents=True)
    (impl_stage / "findings").mkdir()
    (impl_stage / "stage.md").write_text("# Stage 002\nIn progress.\n", encoding="utf-8")

    (run_root / "workflow_state.yaml").write_text(
        "workflow: speckit-loop\nstatus: waiting_agent_tool\nwaiting_reason: agent_tool\n",
        encoding="utf-8",
    )
    (run_root / "run.md").write_text(
        f"---\nrun_id: {fixed_run_id}\nissue_ref: issue #999\n---\n# Run\n",
        encoding="utf-8",
    )

    prompt = resume(fixed_run_id, "claude-code")

    # Every Codex-originated decision must appear in the Claude Code prompt.
    decision_records = [
        record for record in codex_records if isinstance(record, Decision)
    ]
    assert decision_records
    for decision in decision_records:
        first_line = decision.body.splitlines()[0].strip()
        assert first_line in prompt, (
            f"Codex-originated decision dropped during cross-tool swap: {first_line!r}"
        )

    assert "Current stage: 002-implement" in prompt
    assert "Completed stages: 001-specify" in prompt


def test_role_specific_prompt_routes_persona_through_session_continuity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """`spanweave prompt --role coder` and `--role reviewer` produce distinct prompts."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _seed_repo_with_codex_run(repo_root, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(repo_root)

    coder_prompt = generate_prompt(fixed_run_id, "coder", "claude-code")
    reviewer_prompt = generate_prompt(fixed_run_id, "reviewer", "claude-code")

    assert coder_prompt != reviewer_prompt
    assert "Implementation-focused protocol" in coder_prompt
    assert "Review-focused protocol" in reviewer_prompt
    # Both prompts ride on the SAME Claude Code packet base.
    assert "# CLAUDE.md Context Packet" in coder_prompt
    assert "# CLAUDE.md Context Packet" in reviewer_prompt
    # And both include the same captured decisions.
    for line in (
        "Use rollout JSONL as the canonical Codex transcript surface",
        "Treat AGENTS.md as the primary Codex convention file when",
        "Include current run state in every formatted packet.",
    ):
        assert line in coder_prompt
        assert line in reviewer_prompt


def test_context_summary_for_external_tool_stays_under_token_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """`spanweave context --for chatgpt` produces a self-contained, budgeted summary."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    decisions, _, _ = _seed_repo_with_codex_run(
        repo_root, fixed_run_id, fixed_ulid_values,
    )
    monkeypatch.chdir(repo_root)

    summary = generate_context("chatgpt", token_limit=4000)

    # Heuristic estimate (used inside the compiler): len * 4/3 tokens.
    estimated_tokens = max(len(summary) // 4, 1)
    assert estimated_tokens <= 4000

    # The summary should reference at least one captured decision.
    captured_a_decision = any(
        decision.body.splitlines()[0].strip() in summary for decision in decisions
    )
    assert captured_a_decision, (
        "context summary should surface at least one captured decision"
    )

    # And it should be self-describing for the target tool.
    assert "chatgpt" in summary.lower()


def test_session_resume_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Calling ``resume`` twice in a row produces the same prompt content."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _seed_repo_with_codex_run(repo_root, fixed_run_id, fixed_ulid_values)
    monkeypatch.chdir(repo_root)

    first = resume(fixed_run_id, "claude-code")
    second = resume(fixed_run_id, "claude-code")

    assert first == second, "resume must be deterministic for the same run state"
