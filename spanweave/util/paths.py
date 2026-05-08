from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .ulid import EntityPrefix, validate_prefixed_id

RUNS_ROOT = Path(".spanweave") / "runs"

_STRICT_STR = Field(strict=True, min_length=1)
_STAGE_SEQ = Field(strict=True, ge=1, le=999)


class _RunPathInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: Annotated[str, _STRICT_STR]

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return validate_prefixed_id(value, EntityPrefix.RUN)


class _StagePathInput(_RunPathInput):
    stage_seq: Annotated[int, _STAGE_SEQ]
    stage_name: Annotated[str, _STRICT_STR]

    @field_validator("stage_name")
    @classmethod
    def _normalize_stage_name(cls, value: str) -> str:
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError("stage_name must not contain path separators or traversal markers")

        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        if not slug:
            raise ValueError("stage_name must contain at least one alphanumeric character")

        return slug


def run_dir(run_id: str) -> Path:
    params = _RunPathInput(run_id=run_id)
    return RUNS_ROOT / params.run_id


def stage_dir(run_id: str, stage_seq: int, stage_name: str) -> Path:
    params = _StagePathInput(run_id=run_id, stage_seq=stage_seq, stage_name=stage_name)
    stage_label = f"{params.stage_seq:03d}-{params.stage_name}"
    return run_dir(params.run_id) / "stages" / stage_label


def _stage_file_path(file_name: str, run_id: str, stage_seq: int, stage_name: str) -> Path:
    return stage_dir(run_id, stage_seq, stage_name) / file_name


def packet_path(run_id: str, stage_seq: int, stage_name: str) -> Path:
    return _stage_file_path("packet.md", run_id, stage_seq, stage_name)


def evidence_md_path(run_id: str, stage_seq: int, stage_name: str) -> Path:
    return _stage_file_path("evidence.md", run_id, stage_seq, stage_name)


def evidence_json_path(run_id: str, stage_seq: int, stage_name: str) -> Path:
    return _stage_file_path("evidence.json", run_id, stage_seq, stage_name)


def transcript_path(run_id: str, stage_seq: int, stage_name: str) -> Path:
    return _stage_file_path("transcript.jsonl", run_id, stage_seq, stage_name)


def audit_log_path(run_id: str) -> Path:
    return run_dir(run_id) / "audit.jsonl"


__all__ = [
    "audit_log_path",
    "evidence_json_path",
    "evidence_md_path",
    "packet_path",
    "run_dir",
    "stage_dir",
    "transcript_path",
]
