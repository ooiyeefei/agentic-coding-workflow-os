"""Loader for YAML-defined feedback rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml


@dataclass(frozen=True)
class RuleMatch:
    """A pattern-match rule for deriving SKILL.md guidance from a failure entry."""

    id: str
    error_types: tuple[str, ...]
    message_patterns: tuple[re.Pattern[str], ...]
    rule_text: str
    rationale: str


class RuleLoadError(ValueError):
    """Raised when a YAML rule file cannot be parsed into a RuleMatch."""


def _coerce_str_list(value: object, *, field: str, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RuleLoadError(f"{path}: '{field}' must be a list of strings")
    items: list[str] = []
    raw_list = cast(list[object], value)
    for entry in raw_list:
        if not isinstance(entry, str):
            raise RuleLoadError(f"{path}: '{field}' must contain only strings")
        stripped = entry.strip()
        if not stripped:
            raise RuleLoadError(f"{path}: '{field}' contains an empty string")
        items.append(stripped)
    return tuple(items)


def _normalize_text(value: object, *, field: str, path: Path) -> str:
    if not isinstance(value, str):
        raise RuleLoadError(f"{path}: '{field}' must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise RuleLoadError(f"{path}: '{field}' must be non-empty")
    return normalized


def parse_rule_document(document: object, path: Path) -> RuleMatch:
    """Convert a parsed YAML document into a RuleMatch."""

    if not isinstance(document, dict):
        raise RuleLoadError(f"{path}: rule document must be a YAML mapping")

    raw_doc = cast(dict[object, object], document)
    data: dict[str, object] = {str(key): value for key, value in raw_doc.items()}

    raw_id = data.get("id", path.stem)
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise RuleLoadError(f"{path}: 'id' must be a non-empty string")
    rule_id = raw_id.strip()

    error_types = _coerce_str_list(data.get("error_types"), field="error_types", path=path)
    if not error_types:
        raise RuleLoadError(f"{path}: 'error_types' must contain at least one entry")

    raw_patterns = data.get("message_patterns")
    if not isinstance(raw_patterns, list):
        raise RuleLoadError(f"{path}: 'message_patterns' must be a list of regex strings")
    patterns: list[re.Pattern[str]] = []
    raw_pattern_list = cast(list[object], raw_patterns)
    for raw in raw_pattern_list:
        if not isinstance(raw, str):
            raise RuleLoadError(f"{path}: 'message_patterns' must contain only strings")
        try:
            patterns.append(re.compile(raw, re.IGNORECASE))
        except re.error as exc:
            raise RuleLoadError(f"{path}: invalid regex {raw!r}: {exc}") from exc
    if not patterns:
        raise RuleLoadError(f"{path}: 'message_patterns' must contain at least one regex")

    rule_text = _normalize_text(data.get("rule_text"), field="rule_text", path=path)
    rationale = _normalize_text(data.get("rationale"), field="rationale", path=path)

    return RuleMatch(
        id=rule_id,
        error_types=error_types,
        message_patterns=tuple(patterns),
        rule_text=rule_text,
        rationale=rationale,
    )


def load_rules(rules_dir: Path) -> tuple[RuleMatch, ...]:
    """Load every YAML rule file in the directory, sorted by filename."""

    if not rules_dir.exists():
        raise FileNotFoundError(f"feedback rules directory not found: {rules_dir}")
    if not rules_dir.is_dir():
        raise NotADirectoryError(f"feedback rules path is not a directory: {rules_dir}")

    rules: list[RuleMatch] = []
    for path in sorted(rules_dir.glob("*.yaml")):
        if not path.is_file():
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        rules.append(parse_rule_document(document, path))
    return tuple(rules)


__all__ = ["RuleLoadError", "RuleMatch", "load_rules", "parse_rule_document"]
