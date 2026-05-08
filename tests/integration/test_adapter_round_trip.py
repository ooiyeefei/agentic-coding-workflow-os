"""Integration coverage for the W27 Tool Adapter Layer.

These tests exercise the full ingest -> persist -> format round trip:

* Read a fixture Claude Code JSONL session with the Claude Code adapter.
* Persist the extracted typed memory records to ``.spanweave/memory/`` on disk.
* Reload the persisted records and feed them through both the Claude Code and
  the Codex adapters.
* Assert (a) the decisions and findings survive the round trip without loss,
  and (b) the two formatted Context Packets DIFFER in tool conventions while
  carrying the same captured content.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from spanweave.adapters import (
    ClaudeCodeAdapter,
    CodexAdapter,
    GenericAdapter,
    detect_active_adapter,
)
from spanweave.memory import (
    Decision,
    MemoryRecord,
    RejectedAlternative,
    ReviewFinding,
    list_records,
    write_record,
)

_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "adapters"
_CLAUDE_FIXTURE = (
    _FIXTURE_ROOT / "claude" / "projects" / "sample-project" / "session.jsonl"
)
_CODEX_FIXTURE = (
    _FIXTURE_ROOT / "codex" / "sessions" / "2026" / "04" / "23" / "rollout-sample.jsonl"
)


def _record_bodies(records: Sequence[MemoryRecord]) -> set[str]:
    return {record.body.strip() for record in records}


def _extract_section(packet: str, heading: str) -> str:
    """Return the slice of ``packet`` from ``heading`` until the next ``## `` header."""

    start = packet.index(heading)
    after_heading = start + len(heading)
    end = packet.find("\n## ", after_heading)
    if end == -1:
        return packet[start:]
    return packet[start:end]


def _source_repos(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / ".claude" / "rules").mkdir(parents=True)
    (repo_root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    (repo_root / ".claude" / "rules" / "session.md").write_text(
        "# Session rules\n",
        encoding="utf-8",
    )
    (repo_root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    return repo_root


def test_claude_code_round_trip_persists_and_reformats_for_codex(
    tmp_path: Path,
) -> None:
    """Round-trip: Claude Code JSONL -> memory records on disk -> packets per tool."""

    repo_root = _source_repos(tmp_path)
    memory_root = repo_root / ".spanweave" / "memory"

    claude_adapter = ClaudeCodeAdapter(repo_root=repo_root)
    ingested = claude_adapter.ingest_transcript(_CLAUDE_FIXTURE)

    assert ingested, "Claude Code adapter should extract records from fixture"
    decisions_in = [record for record in ingested if isinstance(record, Decision)]
    findings_in = [record for record in ingested if isinstance(record, ReviewFinding)]
    assert len(decisions_in) >= 3
    assert findings_in, "Fixture should contain at least one review finding"

    for record in ingested:
        assert record.source.startswith("claude-code:"), (
            "ingested records must be tagged with the source adapter name"
        )
        write_record(record, memory_root)

    persisted = list_records(memory_root)
    assert len(persisted) == len(ingested)
    assert _record_bodies(persisted) == _record_bodies(ingested)

    run_id = ingested[0].run_id

    claude_packet = claude_adapter.format_context_packet(
        run_id,
        "coder",
        persisted,
    )
    codex_adapter = CodexAdapter(repo_root=repo_root)
    codex_packet = codex_adapter.format_context_packet(
        run_id,
        "coder",
        persisted,
    )

    # 1. Decisions and findings survive the round trip — both packets reference them.
    for record in [*decisions_in, *findings_in]:
        body_summary = record.body.splitlines()[0].strip()
        assert body_summary in claude_packet, (
            f"claude packet missing record body summary: {body_summary!r}"
        )
        assert body_summary in codex_packet, (
            f"codex packet missing record body summary: {body_summary!r}"
        )

    # 2. The packets DIFFER in their tool-specific framing.
    assert claude_packet != codex_packet
    assert claude_packet.startswith("# CLAUDE.md Context Packet")
    assert codex_packet.startswith("# AGENTS.md Context Packet")

    # The Tool Convention Files block is the canonical structural divergence:
    # Claude Code instructs the user to read CLAUDE.md + .claude/rules; Codex
    # instructs the user to read AGENTS.md only. Capture the block per packet.
    claude_convention = _extract_section(claude_packet, "## Tool Convention Files")
    codex_convention = _extract_section(codex_packet, "## Tool Convention Files")

    assert "CLAUDE.md" in claude_convention
    assert ".claude/rules/" in claude_convention
    assert "AGENTS.md" not in claude_convention

    assert "AGENTS.md" in codex_convention
    assert "CLAUDE.md" not in codex_convention
    assert ".claude/rules/" not in codex_convention

    # 3. Both packets carry the structural sections from the base packet builder.
    for packet in (claude_packet, codex_packet):
        assert "## Prior Decisions" in packet
        assert "## Open Findings" in packet
        assert "## Rejected Alternatives" in packet
        assert "## Relevant ADRs" in packet
        assert "## Current Run State" in packet


def test_round_trip_is_idempotent_under_repeated_ingest(tmp_path: Path) -> None:
    """Re-reading the same fixture must not corrupt or duplicate persisted state."""

    repo_root = _source_repos(tmp_path)
    memory_root = repo_root / ".spanweave" / "memory"
    adapter = ClaudeCodeAdapter(repo_root=repo_root)

    first_pass = adapter.ingest_transcript(_CLAUDE_FIXTURE)
    for record in first_pass:
        write_record(record, memory_root)
    initial_paths = sorted(path.name for path in memory_root.rglob("*.md"))

    # Second ingest produces a fresh batch with new ULIDs but the same bodies.
    second_pass = adapter.ingest_transcript(_CLAUDE_FIXTURE)
    assert _record_bodies(second_pass) == _record_bodies(first_pass)

    for record in second_pass:
        write_record(record, memory_root)
    second_paths = sorted(path.name for path in memory_root.rglob("*.md"))

    # Initial files are still present (filenames are deterministic per record id).
    assert set(initial_paths).issubset(set(second_paths))

    # Reading back must succeed and contain ALL bodies from both passes.
    persisted = list_records(memory_root)
    persisted_bodies = _record_bodies(persisted)
    assert _record_bodies(first_pass).issubset(persisted_bodies)
    assert _record_bodies(second_pass).issubset(persisted_bodies)


def test_codex_round_trip_preserves_decisions_for_claude_code_handoff(
    tmp_path: Path,
) -> None:
    """A Codex-originated session must surface intact when the user resumes in Claude Code."""

    repo_root = _source_repos(tmp_path)
    memory_root = repo_root / ".spanweave" / "memory"

    codex_adapter = CodexAdapter(repo_root=repo_root)
    codex_records = codex_adapter.ingest_transcript(_CODEX_FIXTURE)

    assert codex_records, "Codex adapter should extract records from fixture"
    assert all(record.source.startswith("codex:") for record in codex_records)

    for record in codex_records:
        write_record(record, memory_root)

    persisted = list_records(memory_root)
    assert _record_bodies(persisted) == _record_bodies(codex_records)

    # Verify expected fixture content is preserved.
    decision_bodies = {
        record.body.strip()
        for record in persisted
        if isinstance(record, Decision)
    }
    assert any(
        "rollout JSONL" in body or "AGENTS.md" in body or "current run state" in body.lower()
        for body in decision_bodies
    ), f"expected at least one Codex decision body, got: {decision_bodies}"

    # Now hand off to Claude Code: the packet should advertise CLAUDE.md but
    # carry the Codex-originated decisions verbatim.
    claude_adapter = ClaudeCodeAdapter(repo_root=repo_root)
    run_id = codex_records[0].run_id
    handoff_packet = claude_adapter.format_context_packet(
        run_id,
        "coder",
        persisted,
    )

    assert "# CLAUDE.md Context Packet" in handoff_packet
    for record in persisted:
        if isinstance(record, Decision | ReviewFinding):
            first_line = record.body.splitlines()[0].strip()
            assert first_line in handoff_packet, (
                f"Claude Code handoff dropped Codex-originated content: {first_line!r}"
            )


def test_detect_active_adapter_disambiguates_three_environments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adapter auto-detection should distinguish Claude Code, Codex, and unknown."""

    claude_root = tmp_path / "claude_workspace"
    claude_root.mkdir()
    (claude_root / ".claude").mkdir()
    (claude_root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")

    codex_root = tmp_path / "codex_workspace"
    codex_root.mkdir()
    (codex_root / "AGENTS.md").write_text("# Codex\n", encoding="utf-8")

    neutral_root = tmp_path / "neutral_workspace"
    neutral_root.mkdir()

    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CODEX_CI", raising=False)
    monkeypatch.delenv("CODEX_MANAGED_BY_NPM", raising=False)

    monkeypatch.setenv("CODEX_THREAD_ID", "fixture-thread")
    assert isinstance(detect_active_adapter(codex_root), CodexAdapter)

    monkeypatch.delenv("CODEX_THREAD_ID")
    assert isinstance(detect_active_adapter(claude_root), ClaudeCodeAdapter)

    assert detect_active_adapter(neutral_root) is None
    assert isinstance(GenericAdapter(repo_root=neutral_root), GenericAdapter)


def test_claude_jsonl_fixture_shape_is_well_formed() -> None:
    """Sanity check the upstream fixture so failures here are upstream-fixture bugs."""

    lines = [
        line
        for line in _CLAUDE_FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    payloads = [json.loads(line) for line in lines]
    user_messages = [
        payload
        for payload in payloads
        if isinstance(payload.get("message"), dict)
        and payload["message"].get("role") == "user"
    ]
    assistant_messages = [
        payload
        for payload in payloads
        if isinstance(payload.get("message"), dict)
        and payload["message"].get("role") == "assistant"
    ]

    assert user_messages, "fixture must include at least one user turn"
    assert assistant_messages, "fixture must include at least one assistant turn"


def test_round_trip_preserves_rejected_alternatives_when_present(
    tmp_path: Path,
) -> None:
    """Manually seed a RejectedAlternative and verify both packets surface it."""

    repo_root = _source_repos(tmp_path)
    memory_root = repo_root / ".spanweave" / "memory"

    claude_adapter = ClaudeCodeAdapter(repo_root=repo_root)
    ingested = claude_adapter.ingest_transcript(_CLAUDE_FIXTURE)
    for record in ingested:
        write_record(record, memory_root)

    base_record = next(record for record in ingested if isinstance(record, Decision))
    rejected = RejectedAlternative(
        run_id=base_record.run_id,
        stage_id=base_record.stage_id,
        tags=["round-trip"],
        confidence=0.55,
        source="round-trip-fixture",
        body=(
            "Skip persisted memory and rebuild context from transcripts each run.\n"
            "Reason: would force every adapter to re-parse session files on resume."
        ),
    )
    write_record(rejected, memory_root)

    persisted = list_records(memory_root)
    rejected_bodies = {
        record.body.splitlines()[0].strip()
        for record in persisted
        if isinstance(record, RejectedAlternative)
    }
    assert "Skip persisted memory and rebuild context from transcripts each run." in rejected_bodies

    run_id = base_record.run_id
    claude_packet = claude_adapter.format_context_packet(run_id, "coder", persisted)
    codex_packet = CodexAdapter(repo_root=repo_root).format_context_packet(
        run_id, "coder", persisted,
    )

    rejected_summary = "Skip persisted memory and rebuild context from transcripts each run."
    assert rejected_summary in claude_packet
    assert rejected_summary in codex_packet
    # Both packets must place the rejected alternative under the matching section.
    for packet in (claude_packet, codex_packet):
        rejected_section_index = packet.index("## Rejected Alternatives")
        next_section_index = packet.find("\n## ", rejected_section_index + 1)
        rejected_block = packet[
            rejected_section_index : next_section_index if next_section_index != -1 else len(packet)
        ]
        assert rejected_summary in rejected_block, (
            "rejected alternative body must appear inside its dedicated section"
        )
