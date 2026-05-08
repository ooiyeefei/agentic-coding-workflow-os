from __future__ import annotations

from enum import StrEnum

from ulid import ULID


class EntityPrefix(StrEnum):
    RUN = "run"
    STAGE = "stage"
    PACKET = "packet"
    ACTION = "action"
    EVIDENCE = "evidence"
    DECISION = "decision"


def _new_prefixed_id(prefix: EntityPrefix) -> str:
    return f"{prefix.value}_{ULID()}"


def validate_prefixed_id(value: str, prefix: EntityPrefix) -> str:
    prefix_text = f"{prefix.value}_"
    if not value.startswith(prefix_text):
        raise ValueError(f"expected {prefix.value!r} ID, got {value!r}")

    try:
        ULID.parse(value.removeprefix(prefix_text))
    except ValueError as exc:
        raise ValueError(f"invalid ULID payload in {value!r}") from exc

    return value


def new_run_id() -> str:
    return _new_prefixed_id(EntityPrefix.RUN)


def new_stage_id() -> str:
    return _new_prefixed_id(EntityPrefix.STAGE)


def new_packet_id() -> str:
    return _new_prefixed_id(EntityPrefix.PACKET)


def new_action_id() -> str:
    return _new_prefixed_id(EntityPrefix.ACTION)


def new_evidence_id() -> str:
    return _new_prefixed_id(EntityPrefix.EVIDENCE)


def new_decision_id() -> str:
    return _new_prefixed_id(EntityPrefix.DECISION)


__all__ = [
    "EntityPrefix",
    "new_action_id",
    "new_decision_id",
    "new_evidence_id",
    "new_packet_id",
    "new_run_id",
    "new_stage_id",
    "validate_prefixed_id",
]
