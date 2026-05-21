from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import frontmatter
import pytest
import spanweave.memory.records as memory_records
from spanweave.memory import (
    Decision,
    ReviewFinding,
    SkillOutcome,
    WorkflowEvent,
    list_records,
    read_record,
    write_record,
)
from ulid import ULID


class _DeterministicULIDFactory:
    def __init__(self, values: list[str]) -> None:
        self._values: Iterator[str] = iter(values)

    def __call__(self) -> str:
        return next(self._values)

    @staticmethod
    def parse(value: str) -> ULID:
        return ULID.parse(value)


def test_write_and_read_round_trip_preserves_fields_and_markdown_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    monkeypatch.setattr(memory_records, "ULID", _DeterministicULIDFactory(fixed_ulid_values[1:]))

    stage_id = f"stage_{fixed_ulid_values[0]}"
    body = "# Decision\n\n- Preserve lists\n\n```python\nprint('ok')\n```\n\nTrailing line\n"
    record = Decision(
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=datetime(2026, 4, 20, 0, 0, tzinfo=UTC),
        related_issues=["#6"],
        related_adrs=["ADR-0001"],
        tags=["knowledge-plane", "safety-critical"],
        confidence=0.9,
        source="coder",
        body=body,
    )

    memory_root = tmp_path / ".spanweave" / "memory"
    written_path = write_record(record, memory_root)

    assert written_path == memory_root / "decisions" / f"{record.id}.md"
    assert written_path.exists()

    persisted = written_path.read_text(encoding="utf-8")
    parsed = frontmatter.loads(persisted)

    assert parsed.metadata["id"] == record.id
    assert parsed.metadata["type"] == "Decision"
    assert parsed.metadata["run_id"] == fixed_run_id

    loaded = read_record(written_path)

    assert loaded == record
    assert loaded.body == body


def test_list_records_filters_by_type_and_tags(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    stage_id = f"stage_{fixed_ulid_values[1]}"
    timestamp = datetime(2026, 4, 20, 0, 0, tzinfo=UTC)

    decision_match = Decision(
        id=f"decision_{fixed_ulid_values[2]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=timestamp,
        tags=["safety-critical", "memory"],
        source="coder",
        body="Ship typed memory records.\n",
    )
    decision_other = Decision(
        id=f"decision_{fixed_ulid_values[3]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=timestamp,
        tags=["routine"],
        source="coder",
        body="Non-critical follow-up.\n",
    )
    finding = ReviewFinding(
        id=f"review_finding_{fixed_ulid_values[4]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=timestamp,
        tags=["safety-critical"],
        source="reviewer",
        body="Missing redaction would be a release blocker.\n",
    )

    for record in (decision_match, decision_other, finding):
        write_record(record, memory_root)

    results = list_records(memory_root, type="Decision", tags=["safety-critical"])

    assert results == [decision_match]


def test_skill_outcome_round_trip_supports_feedback_learning(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    record = SkillOutcome(
        id=f"skill_outcome_{fixed_ulid_values[5]}",
        run_id=fixed_run_id,
        stage_id=f"stage_{fixed_ulid_values[1]}",
        timestamp=datetime(2026, 4, 25, 22, 0, tzinfo=UTC),
        tags=["pr-rescue", "self-improvement"],
        source="reviewer",
        selected_skill_id="spanweave-pr-rescue",
        skill_version="baseline",
        task_text="Review and rescue PR #101.",
        result_summary="Missed the highest-risk changed execution path.",
        success_score=0.42,
        feedback=-0.72,
        error_type="missed_regression",
        error_message="Missed a user-visible null dereference.",
        applied_rules=[
            "Before low-severity comments, identify the highest-risk changed path.",
        ],
        body="Baseline PR rescue missed a null dereference in the response path.\n",
    )

    written_path = write_record(record, memory_root)

    assert record.id.startswith("skill_outcome_")
    assert written_path == memory_root / "skill_outcomes" / f"{record.id}.md"
    assert read_record(written_path) == record
    assert list_records(
        memory_root,
        type="SkillOutcome",
        selected_skill_id="spanweave-pr-rescue",
        error_type="missed_regression",
    ) == [record]


def test_write_record_redacts_secret_like_body_content(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    record = Decision(
        id=f"decision_{fixed_ulid_values[1]}",
        run_id=fixed_run_id,
        stage_id=f"stage_{fixed_ulid_values[2]}",
        timestamp=datetime(2026, 4, 20, 0, 0, tzinfo=UTC),
        tags=["safety-critical"],
        source="coder",
        body="OPENAI_API_KEY=sk-xxx\n",
    )

    written_path = write_record(record, memory_root)
    persisted = written_path.read_text(encoding="utf-8")

    assert "sk-xxx" not in persisted
    assert "[REDACTED:" in persisted


def test_read_record_rejects_missing_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / ".spanweave" / "memory" / "decisions" / "decision_invalid.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Not frontmatter\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing valid YAML frontmatter"):
        read_record(path)


def test_read_record_rejects_unsupported_record_type(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    path = tmp_path / ".spanweave" / "memory" / "decisions" / "decision_invalid.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "---\n"
            f"id: decision_{fixed_ulid_values[1]}\n"
            "type: UnknownRecord\n"
            "version: 1\n"
            f"run_id: {fixed_run_id}\n"
            f"stage_id: stage_{fixed_ulid_values[2]}\n"
            "timestamp: '2026-04-20T00:00:00Z'\n"
            "related_issues: []\n"
            "related_adrs: []\n"
            "tags: []\n"
            "confidence: null\n"
            "source: reviewer\n"
            "---\n"
            "Unsupported type body.\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported record type"):
        read_record(path)


def test_list_records_raises_on_malformed_markdown_file_in_tree(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    valid = Decision(
        id=f"decision_{fixed_ulid_values[1]}",
        run_id=fixed_run_id,
        stage_id=f"stage_{fixed_ulid_values[2]}",
        timestamp=datetime(2026, 4, 20, 0, 0, tzinfo=UTC),
        tags=["memory"],
        source="reviewer",
        body="Valid record.\n",
    )
    write_record(valid, memory_root)

    malformed = memory_root / "decisions" / "000_invalid.md"
    malformed.write_text("# malformed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing valid YAML frontmatter"):
        list_records(memory_root)


def test_workflow_event_round_trip_preserves_fields(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    record = WorkflowEvent(
        id=f"workflow_event_{fixed_ulid_values[1]}",
        run_id=fixed_run_id,
        stage_id=f"stage_{fixed_ulid_values[2]}",
        timestamp=datetime(2026, 4, 20, 0, 0, tzinfo=UTC),
        tags=["workflow-validation", "specify"],
        confidence=0.9,
        source="integration-harness",
        body=(
            "# Persist workflow evidence for 001-specify\n\n"
            "The 001-specify stage stores packet and evidence on disk.\n"
        ),
    )

    written_path = write_record(record, memory_root)

    assert record.id.startswith("workflow_event_")
    assert written_path == memory_root / "workflow_events" / f"{record.id}.md"
    assert written_path.exists()

    loaded = read_record(written_path)
    assert loaded == record
    assert loaded.type == "WorkflowEvent"
    assert loaded.collection_name == "workflow_events"


def test_workflow_event_listed_by_type_filter(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    stage_id = f"stage_{fixed_ulid_values[1]}"
    timestamp = datetime(2026, 4, 20, 0, 0, tzinfo=UTC)

    event = WorkflowEvent(
        id=f"workflow_event_{fixed_ulid_values[2]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=timestamp,
        tags=["workflow-validation"],
        source="integration-harness",
        body="Stage evidence persisted.\n",
    )
    decision = Decision(
        id=f"decision_{fixed_ulid_values[3]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=timestamp,
        tags=["real-decision"],
        source="coder",
        body="Use typed records for all memory.\n",
    )

    write_record(event, memory_root)
    write_record(decision, memory_root)

    # Only WorkflowEvents
    events_only = list_records(memory_root, type="WorkflowEvent")
    assert events_only == [event]

    # Only Decisions
    decisions_only = list_records(memory_root, type="Decision")
    assert decisions_only == [decision]

    # All records
    all_records = list_records(memory_root)
    assert len(all_records) == 2


def test_workflow_event_has_correct_id_prefix_validation(
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """WorkflowEvent rejects IDs with wrong prefix."""
    with pytest.raises(ValueError, match="expected 'workflow_event' ID"):
        WorkflowEvent(
            id=f"decision_{fixed_ulid_values[1]}",
            run_id=fixed_run_id,
            stage_id=f"stage_{fixed_ulid_values[2]}",
            source="test",
            body="body\n",
        )
