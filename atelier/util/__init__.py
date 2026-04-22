from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "atomic_write": ("atelier.util.fs", "atomic_write"),
    "audit_log_path": ("atelier.util.paths", "audit_log_path"),
    "EntityPrefix": ("atelier.util.ulid", "EntityPrefix"),
    "evidence_json_path": ("atelier.util.paths", "evidence_json_path"),
    "evidence_md_path": ("atelier.util.paths", "evidence_md_path"),
    "new_action_id": ("atelier.util.ulid", "new_action_id"),
    "new_decision_id": ("atelier.util.ulid", "new_decision_id"),
    "new_evidence_id": ("atelier.util.ulid", "new_evidence_id"),
    "new_packet_id": ("atelier.util.ulid", "new_packet_id"),
    "new_run_id": ("atelier.util.ulid", "new_run_id"),
    "new_stage_id": ("atelier.util.ulid", "new_stage_id"),
    "packet_path": ("atelier.util.paths", "packet_path"),
    "run_dir": ("atelier.util.paths", "run_dir"),
    "safe_mkdir": ("atelier.util.fs", "safe_mkdir"),
    "stage_dir": ("atelier.util.paths", "stage_dir"),
    "transcript_path": ("atelier.util.paths", "transcript_path"),
}

__all__ = [
    "atomic_write",
    "audit_log_path",
    "EntityPrefix",
    "evidence_json_path",
    "evidence_md_path",
    "new_action_id",
    "new_decision_id",
    "new_evidence_id",
    "new_packet_id",
    "new_run_id",
    "new_stage_id",
    "packet_path",
    "run_dir",
    "safe_mkdir",
    "stage_dir",
    "transcript_path",
]


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
