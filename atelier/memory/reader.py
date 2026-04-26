from __future__ import annotations

from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import cast

import frontmatter

from .records import RECORD_TYPES, MemoryRecord, Record

DEFAULT_MEMORY_ROOT = Path(".atelier/memory")
_LIST_FILTER_KEYS = {
    "confidence",
    "confidence_min",
    "id",
    "related_adrs",
    "related_issues",
    "run_id",
    "source",
    "stage_id",
    "tags",
    "version",
    "selected_skill_id",
    "skill_version",
    "success_score",
    "feedback",
    "error_type",
}


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} is missing valid YAML frontmatter")

    offset = len(lines[0])
    for line in lines[1:]:
        if line.strip() == "---":
            metadata_text = text[len(lines[0]) : offset]
            body = text[offset + len(line) :]
            return metadata_text, body
        offset += len(line)

    raise ValueError(f"{path} is missing valid YAML frontmatter")


def _build_record(metadata: Mapping[str, object], body: str) -> Record:
    record_type = metadata.get("type")
    if not isinstance(record_type, str):
        raise ValueError("record frontmatter is missing string 'type'")

    try:
        record_model = RECORD_TYPES[record_type]
    except KeyError as exc:
        raise ValueError(f"unsupported record type {record_type!r}") from exc

    payload = dict(metadata)
    payload["body"] = body
    return cast(Record, record_model.model_validate(payload))


def read_record(path: str | PathLike[str]) -> Record:
    record_path = Path(path)
    raw_text = record_path.read_text(encoding="utf-8")
    _, body = _split_frontmatter(raw_text, record_path)
    post = frontmatter.loads(raw_text)
    return _build_record(post.metadata, body)


def _normalize_filters(
    filters: Mapping[str, object] | None,
    criteria: Mapping[str, object],
) -> dict[str, object]:
    merged = dict(filters or {})
    merged.update(criteria)
    unknown = sorted(set(merged) - _LIST_FILTER_KEYS)
    if unknown:
        raise ValueError(f"unsupported record filters: {', '.join(unknown)}")
    return merged


def _is_subset_filter(expected: object, actual: list[str]) -> bool:
    if not isinstance(expected, list):
        raise ValueError("list-based filters must use list values")

    normalized: list[str] = []
    for item in cast(list[object], expected):
        if not isinstance(item, str):
            raise ValueError("list-based filters must contain only strings")
        normalized.append(item)

    return set(normalized).issubset(set(actual))


def _coerce_float(value: object) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError("confidence_min filter must be numeric")
    return float(value)


def _matches(record: MemoryRecord, filters: Mapping[str, object]) -> bool:
    for key, expected in filters.items():
        if key == "confidence_min":
            if record.confidence is None or record.confidence < _coerce_float(expected):
                return False
            continue

        actual = getattr(record, key)
        if key in {"related_adrs", "related_issues", "tags"}:
            if not _is_subset_filter(expected, cast(list[str], actual)):
                return False
            continue

        if actual != expected:
            return False

    return True


def list_records(
    path: str | PathLike[str] = DEFAULT_MEMORY_ROOT,
    *,
    type: str | None = None,
    filters: Mapping[str, object] | None = None,
    **criteria: object,
) -> list[Record]:
    """List typed records from the filesystem and apply metadata filters."""

    root = Path(path)
    if not root.exists():
        return []

    normalized_filters = _normalize_filters(filters, criteria)
    records: list[Record] = []
    for record_path in sorted(root.rglob("*.md")):
        record = read_record(record_path)
        if type is not None and record.type != type:
            continue
        if _matches(record, normalized_filters):
            records.append(record)

    return records


__all__ = ["DEFAULT_MEMORY_ROOT", "list_records", "read_record"]
