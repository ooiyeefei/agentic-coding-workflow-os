from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from atelier.security.redaction import redact
from atelier.util.fs import safe_mkdir
from atelier.util.paths import audit_log_path

from .events import EVENT_SCHEMAS, AuditEvent, EventType

DAILY_AUDIT_ROOT = Path(".atelier") / "audit"


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _daily_log_path(day: date) -> Path:
    return DAILY_AUDIT_ROOT / f"{day.isoformat()}.jsonl"


def _redact_values(obj: object) -> object:
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: _redact_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_values(item) for item in obj]
    return obj


def _append_line(path: Path, line: str) -> None:
    safe_mkdir(path.parent)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def log(
    run_id: str,
    event_type: EventType,
    data: dict[str, Any],
    *,
    repo_root: str | Path = Path("."),
    _today: date | None = None,
) -> AuditEvent:
    schema_class = EVENT_SCHEMAS.get(event_type)
    if schema_class is None:
        raise ValueError(f"unknown event_type {event_type!r}")

    event = schema_class(run_id=run_id, **data)
    redacted_payload = _redact_values(event.model_dump(mode="json"))
    json_line = json.dumps(
        redacted_payload, separators=(",", ":"), sort_keys=True,
    ) + "\n"

    root = Path(repo_root)
    run_log = root / audit_log_path(run_id)
    day = _today or _today_utc()
    daily_log = root / _daily_log_path(day)

    _append_line(run_log, json_line)
    _append_line(daily_log, json_line)

    return event


__all__ = ["DAILY_AUDIT_ROOT", "log"]
