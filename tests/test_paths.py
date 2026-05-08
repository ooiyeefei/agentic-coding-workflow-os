from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError
from spanweave.util import (
    audit_log_path,
    evidence_json_path,
    evidence_md_path,
    packet_path,
    run_dir,
    stage_dir,
    transcript_path,
)


def test_run_dir_returns_canonical_path(fixed_run_id: str) -> None:
    run_id = fixed_run_id
    path = run_dir(run_id)

    assert isinstance(path, Path)
    assert path == Path(".spanweave") / "runs" / run_id


def test_stage_dir_zero_pads_and_slugifies(fixed_run_id: str) -> None:
    run_id = fixed_run_id

    path = stage_dir(run_id, 1, "Spec Review!")

    assert isinstance(path, Path)
    assert path == Path(".spanweave") / "runs" / run_id / "stages" / "001-spec-review"


@pytest.mark.parametrize(
    ("helper", "expected_name"),
    [
        (packet_path, "packet.md"),
        (evidence_md_path, "evidence.md"),
        (evidence_json_path, "evidence.json"),
        (transcript_path, "transcript.jsonl"),
    ],
)
def test_stage_file_helpers_return_expected_locations(
    fixed_run_id: str,
    helper: Callable[[str, int, str], Path],
    expected_name: str,
) -> None:
    run_id = fixed_run_id

    path = helper(run_id, 12, "Implement")

    assert isinstance(path, Path)
    assert path == Path(".spanweave") / "runs" / run_id / "stages" / "012-implement" / expected_name


def test_audit_log_path_returns_run_scoped_path(fixed_run_id: str) -> None:
    run_id = fixed_run_id

    path = audit_log_path(run_id)

    assert isinstance(path, Path)
    assert path == Path(".spanweave") / "runs" / run_id / "audit.jsonl"


@pytest.mark.parametrize(
    "run_id",
    [
        "packet_01KPMC0QTJ07Q0AXVMPWCCZJT2",
        "run_not-a-ulid",
    ],
)
def test_invalid_run_ids_are_rejected(run_id: str) -> None:
    with pytest.raises(ValidationError):
        run_dir(run_id)


@pytest.mark.parametrize("stage_seq", [0, 1000])
def test_invalid_stage_sequences_are_rejected(stage_seq: int) -> None:
    with pytest.raises(ValidationError):
        stage_dir("run_01ARZ3NDEKTSV4RRFFQ69G5FAV", stage_seq, "specify")


@pytest.mark.parametrize("stage_name", ["../escape", r"plan\review", "!!!"])
def test_invalid_stage_names_are_rejected(stage_name: str) -> None:
    with pytest.raises(ValidationError):
        stage_dir("run_01ARZ3NDEKTSV4RRFFQ69G5FAV", 1, stage_name)
