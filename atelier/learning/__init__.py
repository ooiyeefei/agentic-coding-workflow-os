"""Atelier learning module: feedback loops that turn failures into SKILL.md rules."""

from __future__ import annotations

from atelier.learning.feedback_loop import (
    APPEND_MARKER,
    FALLBACK_RULE,
    KNOWN_RULES_DIR,
    build_rule_block,
    derive_rule_from_outcome,
    patch_skill_file,
    read_entry,
    render_diff,
)
from atelier.learning.rule_loader import RuleLoadError, RuleMatch, load_rules

__all__ = [
    "APPEND_MARKER",
    "FALLBACK_RULE",
    "KNOWN_RULES_DIR",
    "RuleLoadError",
    "RuleMatch",
    "build_rule_block",
    "derive_rule_from_outcome",
    "load_rules",
    "patch_skill_file",
    "read_entry",
    "render_diff",
]
