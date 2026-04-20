from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from atelier.util.fs import atomic_write, safe_mkdir
from atelier.util.paths import RUNS_ROOT, run_dir, stage_dir
from atelier.util.ulid import new_run_id

from .lock import run_lock

_STAGE_ID_PATTERN = re.compile(r"^(?P<sequence>\d{3})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$")
_RUN_MARKDOWN_NAME = "run.md"
_STAGE_MARKDOWN_NAME = "stage.md"
_COMPLETION_MARKER_NAME = ".complete"
_LOCK_FILE_NAME = ".lock"


def create_run(issue_ref: str) -> str:
    run_id = _allocate_run_id()
    run_path = run_dir(run_id)

    safe_mkdir(run_path)
    safe_mkdir(run_path / "stages")

    atomic_write(run_path / _RUN_MARKDOWN_NAME, _markdown_document(
        {"run_id": run_id, "issue_ref": issue_ref},
        f"Run {run_id}",
    ))
    atomic_write(run_path / "audit.jsonl", "")
    atomic_write(run_path / _LOCK_FILE_NAME, "")
    return run_id


def create_stage(run_id: str, stage_name: str) -> str:
    with run_lock(run_id):
        run_path = _existing_run_path(run_id)
        stages_path = safe_mkdir(run_path / "stages")
        stage_sequence = _next_stage_sequence(stages_path)
        stage_path = stage_dir(run_id, stage_sequence, stage_name)
        stage_id = stage_path.name

        if stage_path.exists():
            raise FileExistsError(f"stage already exists: {stage_id}")

        safe_mkdir(stage_path)
        safe_mkdir(stage_path / "decisions")
        safe_mkdir(stage_path / "findings")

        atomic_write(stage_path / _STAGE_MARKDOWN_NAME, _markdown_document(
            {
                "run_id": run_id,
                "stage_id": stage_id,
                "sequence": stage_sequence,
                "stage_name": stage_name,
            },
            f"Stage {stage_id}",
        ))
        atomic_write(stage_path / "packet.md", _markdown_document(
            {"run_id": run_id, "stage_id": stage_id, "kind": "packet"},
            f"Packet {stage_id}",
        ))
        atomic_write(stage_path / "transcript.jsonl", "")
        atomic_write(stage_path / "evidence.md", _markdown_document(
            {"run_id": run_id, "stage_id": stage_id, "kind": "evidence"},
            f"Evidence {stage_id}",
        ))
        atomic_write(
            stage_path / "evidence.json",
            json.dumps({"run_id": run_id, "stage_id": stage_id}, indent=2) + "\n",
        )
        return stage_id


def mark_stage_complete(run_id: str, stage_id: str) -> None:
    with run_lock(run_id):
        stage_path = _stage_path(run_id, stage_id)
        if not stage_path.is_dir():
            raise FileNotFoundError(f"stage not found: {stage_id}")
        atomic_write(stage_path / _COMPLETION_MARKER_NAME, "complete\n")


def list_runs() -> list[str]:
    if not RUNS_ROOT.exists():
        return []

    run_ids = [
        path.name
        for path in RUNS_ROOT.iterdir()
        if path.is_dir() and _is_valid_run_id(path.name)
    ]
    return sorted(run_ids)


def list_stages(run_id: str) -> list[str]:
    stages_path = _existing_run_path(run_id) / "stages"
    if not stages_path.exists():
        return []

    stage_ids = [
        path.name
        for path in stages_path.iterdir()
        if path.is_dir() and _STAGE_ID_PATTERN.fullmatch(path.name)
    ]
    return sorted(stage_ids)


def _allocate_run_id() -> str:
    while True:
        candidate = new_run_id()
        if not run_dir(candidate).exists():
            return candidate


def _existing_run_path(run_id: str) -> Path:
    path = run_dir(run_id)
    if not path.is_dir():
        raise FileNotFoundError(f"run not found: {run_id}")
    return path


def _next_stage_sequence(stages_path: Path) -> int:
    highest_sequence = 0

    for path in stages_path.iterdir():
        if not path.is_dir():
            continue
        match = _STAGE_ID_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        highest_sequence = max(highest_sequence, int(match.group("sequence")))

    next_sequence = highest_sequence + 1
    if next_sequence > 999:
        raise ValueError("stage sequence exceeds supported range")
    return next_sequence


def _stage_path(run_id: str, stage_id: str) -> Path:
    _existing_run_path(run_id)
    if _STAGE_ID_PATTERN.fullmatch(stage_id) is None:
        raise ValueError(f"invalid stage ID: {stage_id!r}")
    return run_dir(run_id) / "stages" / stage_id


def _is_valid_run_id(value: str) -> bool:
    try:
        run_dir(value)
    except ValueError:
        return False
    return True


def _markdown_document(metadata: dict[str, Any], title: str) -> str:
    frontmatter = yaml.safe_dump(metadata, sort_keys=False).strip()
    return f"---\n{frontmatter}\n---\n# {title}\n"


__all__ = [
    "create_run",
    "create_stage",
    "list_runs",
    "list_stages",
    "mark_stage_complete",
]
