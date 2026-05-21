"""Spanweave learning module: feedback loops that turn failures into SKILL.md rules."""

from __future__ import annotations

from spanweave.learning.extractor import (
    OllamaNotAvailableError,
    chunk_session,
    dedupe_against_existing,
    extract_decisions_from_chunk,
    extract_from_session,
    stage_pending_decisions,
)
from spanweave.learning.feedback_loop import (
    APPEND_MARKER,
    FALLBACK_RULE,
    KNOWN_RULES_DIR,
    build_rule_block,
    derive_rule_from_outcome,
    patch_skill_file,
    read_entry,
    render_diff,
)
from spanweave.learning.rule_loader import RuleLoadError, RuleMatch, load_rules

__all__ = [
    "APPEND_MARKER",
    "FALLBACK_RULE",
    "KNOWN_RULES_DIR",
    "OllamaNotAvailableError",
    "RuleLoadError",
    "RuleMatch",
    "build_rule_block",
    "chunk_session",
    "dedupe_against_existing",
    "derive_rule_from_outcome",
    "extract_decisions_from_chunk",
    "extract_from_session",
    "load_rules",
    "patch_skill_file",
    "read_entry",
    "render_diff",
    "stage_pending_decisions",
]
