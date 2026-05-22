"""Tests for the selective sharing feature: sharing.yaml policy, promote command, review routing."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner
from spanweave.cli.commands.promote import promote_command
from spanweave.cli.commands.review import review_command
from spanweave.sharing import (
    SharingPolicy,
    default_sharing_yaml,
    load_sharing_policy,
    should_auto_promote,
)


def _write_sharing_yaml(repo: Path, content: str) -> Path:
    path = repo / ".spanweave" / "sharing.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _scaffold_memory(repo: Path) -> Path:
    """Create the basic memory directory structure."""
    memory = repo / ".spanweave" / "memory"
    for subdir in (
        "decisions",
        "private/decisions",
        "private/findings",
        "private/reflections",
        "shared/decisions",
        "shared/findings",
        "pending/decisions",
    ):
        (memory / subdir).mkdir(parents=True, exist_ok=True)
    return memory


def _write_decision_file(directory: Path, record_id: str, **kwargs: object) -> Path:
    """Write a minimal decision file with frontmatter."""
    metadata = {
        "id": record_id,
        "type": "Decision",
        "version": 1,
        "run_id": "run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "stage_id": "stage_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "tags": [],
        "confidence": 0.5,
        "source": "coder",
        **kwargs,
    }
    frontmatter = yaml.safe_dump(metadata, sort_keys=False)
    content = f"---\n{frontmatter}---\nThis is the decision body.\n"
    filepath = directory / f"{record_id}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# --- Feature 4: Sharing policy loader tests ---


def test_load_sharing_policy_defaults(tmp_path: Path) -> None:
    """No sharing.yaml file -> returns all defaults."""
    policy = load_sharing_policy(tmp_path)
    assert policy.new_decisions == "private"
    assert policy.new_findings == "shared"
    assert policy.new_reflections == "private"
    assert "architecture" in policy.auto_promote_tags
    assert "breaking-change" in policy.auto_promote_tags
    assert "security" in policy.auto_promote_tags
    assert policy.require_confidence_above == 0.7
    assert "wip-*" in policy.private_patterns
    assert "personal-*" in policy.private_patterns


def test_load_sharing_policy_from_yaml(tmp_path: Path) -> None:
    """Parses sharing.yaml correctly when file exists."""
    content = """\
defaults:
  new_decisions: shared
  new_findings: private
  new_reflections: shared

promote:
  auto_promote_on_tags:
    - critical
    - deployment
  require_confidence_above: 0.9

private_patterns:
  - "draft-*"
"""
    _write_sharing_yaml(tmp_path, content)
    policy = load_sharing_policy(tmp_path)
    assert policy.new_decisions == "shared"
    assert policy.new_findings == "private"
    assert policy.new_reflections == "shared"
    assert policy.auto_promote_tags == ["critical", "deployment"]
    assert policy.require_confidence_above == 0.9
    assert policy.private_patterns == ["draft-*"]


def test_should_auto_promote_by_tag() -> None:
    """Decision tagged with 'architecture' should auto-promote."""
    policy = SharingPolicy()
    record = {"id": "decision_ABC123", "tags": ["architecture", "cleanup"], "confidence": 0.3}
    assert should_auto_promote(record, policy) is True


def test_should_auto_promote_by_confidence() -> None:
    """Decision with confidence 0.9 (above 0.7 threshold) should auto-promote."""
    policy = SharingPolicy()
    record = {"id": "decision_ABC123", "tags": ["minor-fix"], "confidence": 0.9}
    assert should_auto_promote(record, policy) is True


def test_should_not_promote_low_confidence() -> None:
    """Decision with confidence 0.3 and no matching tags should NOT auto-promote."""
    policy = SharingPolicy()
    record = {"id": "decision_ABC123", "tags": ["minor-fix"], "confidence": 0.3}
    assert should_auto_promote(record, policy) is False


def test_should_not_promote_private_pattern() -> None:
    """Decision whose ID matches a private_pattern should never auto-promote."""
    policy = SharingPolicy()
    record = {"id": "wip-draft", "tags": ["architecture"], "confidence": 0.95}
    assert should_auto_promote(record, policy) is False


# --- Feature 3: Promote command tests ---


def test_promote_command_moves_file(tmp_path: Path) -> None:
    """Verify promote moves a file from private/ to shared/."""
    memory = _scaffold_memory(tmp_path)
    record_id = "decision_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    _write_decision_file(memory / "private" / "decisions", record_id)

    runner = CliRunner()
    result = runner.invoke(promote_command, [record_id, "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "Promoted" in result.output
    assert "shared/" in result.output
    assert not (memory / "private" / "decisions" / f"{record_id}.md").exists()
    assert (memory / "shared" / "decisions" / f"{record_id}.md").exists()


def test_promote_idempotent(tmp_path: Path) -> None:
    """Already in shared/ -> no-op with message."""
    memory = _scaffold_memory(tmp_path)
    record_id = "decision_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    _write_decision_file(memory / "shared" / "decisions", record_id)

    runner = CliRunner()
    result = runner.invoke(promote_command, [record_id, "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "Already in shared/" in result.output
    assert (memory / "shared" / "decisions" / f"{record_id}.md").exists()


def test_promote_all_pending(tmp_path: Path) -> None:
    """--all-pending promotes records matching auto-promote criteria."""
    memory = _scaffold_memory(tmp_path)
    # One with matching tag
    _write_decision_file(
        memory / "private" / "decisions",
        "decision_01ARZ3NDEKTSV4RRFFQ69G5F01",
        tags=["architecture"],
    )
    # One without matching criteria
    _write_decision_file(
        memory / "private" / "decisions",
        "decision_01ARZ3NDEKTSV4RRFFQ69G5F02",
        tags=["minor"],
        confidence=0.3,
    )
    # Write a default sharing.yaml
    _write_sharing_yaml(tmp_path, default_sharing_yaml())

    runner = CliRunner()
    result = runner.invoke(promote_command, ["--all-pending", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    # First one promoted
    assert (memory / "shared" / "decisions" / "decision_01ARZ3NDEKTSV4RRFFQ69G5F01.md").exists()
    # Second one NOT promoted
    assert (memory / "private" / "decisions" / "decision_01ARZ3NDEKTSV4RRFFQ69G5F02.md").exists()


# --- Feature 5: Review routing tests ---


def test_review_routes_to_private_by_default(tmp_path: Path) -> None:
    """Accepted decision with no matching criteria goes to private/."""
    memory = _scaffold_memory(tmp_path)
    record_id = "decision_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    _write_decision_file(
        memory / "pending" / "decisions",
        record_id,
        tags=["minor-fix"],
        confidence=0.3,
    )
    _write_sharing_yaml(tmp_path, default_sharing_yaml())

    runner = CliRunner()
    result = runner.invoke(review_command, ["--auto-accept", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "private/" in result.output
    assert (memory / "private" / "decisions" / f"{record_id}.md").exists()
    assert not (memory / "pending" / "decisions" / f"{record_id}.md").exists()


def test_review_auto_promotes_architecture_tagged(tmp_path: Path) -> None:
    """Decision tagged 'architecture' goes to shared/ during review."""
    memory = _scaffold_memory(tmp_path)
    record_id = "decision_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    _write_decision_file(
        memory / "pending" / "decisions",
        record_id,
        tags=["architecture"],
        confidence=0.5,
    )
    _write_sharing_yaml(tmp_path, default_sharing_yaml())

    runner = CliRunner()
    result = runner.invoke(review_command, ["--auto-accept", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "shared/" in result.output
    assert "auto-promoted" in result.output
    assert (memory / "shared" / "decisions" / f"{record_id}.md").exists()
    assert not (memory / "pending" / "decisions" / f"{record_id}.md").exists()
