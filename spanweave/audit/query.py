from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from spanweave.util.paths import audit_log_path

from .events import AuditEvent, EventType
from .writer import DAILY_AUDIT_ROOT


def _parse_events(path: Path) -> list[AuditEvent]:
    if not path.exists():
        return []
    events: list[AuditEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = AuditEvent.from_json_line(stripped)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid audit line in {path} at line {line_number}") from exc
            events.append(event)
    return events


def events_for_run(
    run_id: str,
    *,
    repo_root: str | Path = Path("."),
) -> list[AuditEvent]:
    path = Path(repo_root) / audit_log_path(run_id)
    return _parse_events(path)


def events_by_type(
    event_type: EventType,
    since: datetime | None = None,
    *,
    repo_root: str | Path = Path("."),
    day: date | None = None,
) -> list[AuditEvent]:
    root = Path(repo_root)
    resolved_day = day or datetime.now(UTC).date()
    path = root / DAILY_AUDIT_ROOT / f"{resolved_day.isoformat()}.jsonl"
    all_events = _parse_events(path)

    filtered = [e for e in all_events if e.event_type == event_type]
    if since is not None:
        aware_since = since if since.tzinfo else since.replace(tzinfo=UTC)
        filtered = [e for e in filtered if e.timestamp >= aware_since]
    return filtered


def sum_cost_for_run(
    run_id: str,
    *,
    repo_root: str | Path = Path("."),
) -> float:
    path = Path(repo_root) / audit_log_path(run_id)
    if not path.exists():
        return 0.0
    total = 0.0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {path} at line {line_number}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"expected JSON object in {path} at line {line_number}")
            cost = payload.get("cost_usd")
            if cost is not None and isinstance(cost, int | float):
                if cost < 0:
                    raise ValueError(f"negative cost in {path} at line {line_number}")
                total += cost
    return total


__all__ = ["events_by_type", "events_for_run", "sum_cost_for_run"]
