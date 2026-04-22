from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request

from atelier.audit.events import AuditEvent
from atelier.util.paths import audit_log_path


def format_sse_event(event: AuditEvent) -> dict[str, str]:
    return {
        "id": event.event_id,
        "event": event.event_type.value,
        "data": event.to_json_line(),
    }


async def stream_run_events(
    *,
    request: Request,
    repo_root: Path,
    run_id: str,
    poll_interval: float,
    limit: int | None = None,
) -> AsyncIterator[dict[str, str]]:
    path = repo_root / audit_log_path(run_id)
    offset = 0
    emitted = 0

    while True:
        if await request.is_disconnected():
            return

        if path.exists():
            with path.open(encoding="utf-8") as handle:
                handle.seek(offset)
                while True:
                    line = handle.readline()
                    if not line:
                        break
                    offset = handle.tell()
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        event = AuditEvent.from_json_line(stripped)
                    except ValueError as exc:
                        error_payload = json.dumps({"detail": str(exc)}, separators=(",", ":"))
                        yield {"event": "error", "data": error_payload}
                        return
                    yield format_sse_event(event)
                    emitted += 1
                    if limit is not None and emitted >= limit:
                        return

        await asyncio.sleep(poll_interval)


__all__ = ["format_sse_event", "stream_run_events"]
