"""Sharing policy: controls private vs shared routing for memory records."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

_DEFAULT_SHARING_YAML = """\
# Spanweave sharing policy
# Controls where new decisions land and what auto-promotes to shared/

defaults:
  new_decisions: private
  new_findings: shared
  new_reflections: private

promote:
  auto_promote_on_tags:
    - architecture
    - breaking-change
    - security
  require_confidence_above: 0.7

private_patterns:
  - "wip-*"
  - "personal-*"
"""


@dataclass(frozen=True)
class SharingPolicy:
    """Parsed sharing policy from .spanweave/sharing.yaml."""

    new_decisions: str = "private"  # "private" | "shared"
    new_findings: str = "shared"
    new_reflections: str = "private"
    auto_promote_tags: list[str] = field(
        default_factory=lambda: ["architecture", "breaking-change", "security"]
    )
    require_confidence_above: float = 0.7
    private_patterns: list[str] = field(default_factory=lambda: ["wip-*", "personal-*"])


def load_sharing_policy(repo_root: Path) -> SharingPolicy:
    """Load sharing policy from .spanweave/sharing.yaml, falling back to defaults."""
    policy_path = repo_root / ".spanweave" / "sharing.yaml"
    if not policy_path.is_file():
        return SharingPolicy()

    raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return SharingPolicy()

    data = cast(dict[str, Any], raw)
    defaults: dict[str, Any] = data.get("defaults") or {}
    promote_cfg: dict[str, Any] = data.get("promote") or {}
    private_patterns = data.get("private_patterns", None)

    return SharingPolicy(
        new_decisions=str(defaults.get("new_decisions", "private")),
        new_findings=str(defaults.get("new_findings", "shared")),
        new_reflections=str(defaults.get("new_reflections", "private")),
        auto_promote_tags=list(promote_cfg.get("auto_promote_on_tags") or []),
        require_confidence_above=float(promote_cfg.get("require_confidence_above", 0.7)),
        private_patterns=(
            list(private_patterns) if private_patterns is not None else ["wip-*", "personal-*"]
        ),
    )


def should_auto_promote(record: dict[str, Any], policy: SharingPolicy) -> bool:
    """Check if a record should auto-promote based on tags and confidence.

    Returns True if:
    - Any of the record's tags match policy.auto_promote_tags, OR
    - The record's confidence exceeds policy.require_confidence_above

    Returns False if the record's ID matches any private_patterns.
    """
    record_id = record.get("id", "")
    for pattern in policy.private_patterns:
        if fnmatch.fnmatch(record_id, pattern):
            return False

    tags = record.get("tags", [])
    if any(tag in policy.auto_promote_tags for tag in tags):
        return True

    confidence = record.get("confidence")
    if confidence is not None and confidence > policy.require_confidence_above:
        return True

    return False


def default_sharing_yaml() -> str:
    """Return the default sharing.yaml content for init scaffolding."""
    return _DEFAULT_SHARING_YAML


__all__ = [
    "SharingPolicy",
    "default_sharing_yaml",
    "load_sharing_policy",
    "should_auto_promote",
]
