from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from atelier.util import audit_log_path

_ZERO_COST = Decimal("0")
_COST_CANDIDATE_PATHS: tuple[tuple[str, ...], ...] = (
    ("cost_usd",),
    ("total_usd",),
    ("cost",),
    ("cost", "total_usd"),
    ("data", "cost_usd"),
    ("data", "total_usd"),
    ("data", "cost"),
    ("data", "cost", "total_usd"),
)


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _to_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float | str):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    return None


def _mapping_get(value: object, key: str) -> object | None:
    if not isinstance(value, dict):
        return None
    return cast("dict[str, object]", value).get(key)


def _resolve_path_value(payload: Mapping[str, object], path: Iterable[str]) -> object | None:
    current: object = payload
    for segment in path:
        next_value = _mapping_get(current, segment)
        if next_value is None:
            return None
        current = next_value
    return current


def _extract_cost(payload: Mapping[str, object]) -> Decimal | None:
    for path in _COST_CANDIDATE_PATHS:
        cost = _to_decimal(_resolve_path_value(payload, path))
        if cost is not None:
            return cost
    return None


class CostTracker:
    def __init__(
        self,
        *,
        repo_root: str | Path = Path("."),
        today_provider: Callable[[], date] = _today_utc,
    ) -> None:
        self.repo_root = Path(repo_root)
        self._today_provider = today_provider

    def sum_run_cost(self, run_id: str) -> Decimal:
        return self._sum_file_cost(self.run_audit_log_path(run_id))

    def sum_day_cost(self, day: date | None = None) -> Decimal:
        resolved_day = day or self._today_provider()
        return self._sum_file_cost(self.daily_audit_log_path(resolved_day))

    def run_audit_log_path(self, run_id: str) -> Path:
        return self.repo_root / audit_log_path(run_id)

    def daily_audit_log_path(self, day: date) -> Path:
        return self.repo_root / ".atelier" / "audit" / f"{day.isoformat()}.jsonl"

    def _sum_file_cost(self, path: Path) -> Decimal:
        if not path.exists():
            return _ZERO_COST
        return sum(self._iter_costs(path), start=_ZERO_COST)

    def _iter_costs(self, path: Path) -> Iterator[Decimal]:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {path} line {line_number}") from exc
                if not isinstance(payload, dict):
                    raise ValueError(f"Expected JSON object in {path} line {line_number}")
                cost = _extract_cost(cast("dict[str, object]", payload))
                if cost is not None:
                    if cost < _ZERO_COST:
                        raise ValueError(f"Negative cost in {path} line {line_number}")
                    yield cost


__all__ = ["CostTracker"]
