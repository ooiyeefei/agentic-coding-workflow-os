"""Derive a single SKILL.md rule from a SkillOutcome JSON entry."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any, cast

from spanweave.learning.rule_loader import RuleMatch, load_rules

# Repo-root-relative path to bundled rule library. Computed once at import time
# so the package stays portable: regardless of cwd, the lookup walks up from
# the spanweave package directory to its parent (the project root) and into
# .spanweave/defaults/feedback_rules/.
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _PACKAGE_ROOT.parent
KNOWN_RULES_DIR = _PROJECT_ROOT / ".spanweave" / "defaults" / "feedback_rules"

FALLBACK_RULE = (
    "When a failure is recorded, add one review rule that names the missed "
    "check explicitly and requires that same check on the next similar change."
)
APPEND_MARKER = "<!-- Added by spanweave.learning.feedback_loop -->"


def _resolve_rules_dir(rules_dir: Path | None) -> Path:
    return rules_dir.resolve() if rules_dir is not None else KNOWN_RULES_DIR


def _normalize_entry(entry: dict[str, Any]) -> tuple[str, str]:
    error_type = str(entry.get("error_type", "") or "").strip()
    error_message = str(entry.get("error_message", "") or "").strip()
    return error_type.lower(), error_message


def _explicit_rule_candidate(entry: dict[str, Any]) -> str | None:
    candidate = str(entry.get("learned_rule_candidate", "") or "").strip()
    if not candidate:
        return None
    if len(candidate) < 20:
        return None
    return " ".join(candidate.split())


def _choose_rule(
    error_type: str,
    error_message: str,
    rules: tuple[RuleMatch, ...],
) -> tuple[str, str, str | None]:
    """Pick the best matching rule.

    Returns (rule_text, rationale, matched_pattern_id). matched_pattern_id is
    None when no rule scored above zero (the fallback path).
    """

    matched_rule: RuleMatch | None = None
    best_score = 0
    for candidate in rules:
        score = 0
        if error_type and error_type in candidate.error_types:
            score += 2
        score += sum(
            1 for pattern in candidate.message_patterns if pattern.search(error_message)
        )
        if score > best_score:
            best_score = score
            matched_rule = candidate

    if matched_rule is not None and best_score > 0:
        return matched_rule.rule_text, matched_rule.rationale, matched_rule.id

    if error_message:
        summarized = " ".join(error_message.split())
        if len(summarized) > 140:
            summarized = summarized[:137].rstrip() + "..."
        return (
            f"{FALLBACK_RULE} Source failure: {summarized}",
            "Used a generic fallback because no known pattern matched strongly enough.",
            None,
        )
    return (
        FALLBACK_RULE,
        "Used a generic fallback because only error_type was available.",
        None,
    )


def derive_rule_from_outcome(
    entry: dict[str, Any],
    rules_dir: Path | None = None,
) -> dict[str, Any]:
    """Derive one concrete SKILL.md rule for a failure entry.

    Args:
        entry: SkillOutcome JSON, treated as a plain mapping. Recognized keys
            are ``error_type``, ``error_message``, and the optional
            ``learned_rule_candidate``.
        rules_dir: Optional override for the YAML rule library. Falls back to
            ``KNOWN_RULES_DIR`` when ``None``.

    Returns:
        ``{"rule_text", "rationale", "matched_pattern", "fallback"}``.
        ``matched_pattern`` is the YAML rule id when a known pattern matched
        or ``None`` when the result came from the explicit candidate or
        fallback paths. ``fallback`` is True only when no candidate or pattern
        match was found.
    """

    if not isinstance(entry, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("entry must be a mapping")

    error_type, error_message = _normalize_entry(entry)
    if not error_type and not error_message and not entry.get("learned_rule_candidate"):
        raise ValueError(
            "SkillOutcome entry must include error_type, error_message, or "
            "learned_rule_candidate"
        )

    candidate_rule = _explicit_rule_candidate(entry)
    if candidate_rule is not None:
        return {
            "rule_text": candidate_rule,
            "rationale": "Used explicit learned_rule_candidate from the SkillOutcome entry.",
            "matched_pattern": None,
            "fallback": False,
        }

    rules = load_rules(_resolve_rules_dir(rules_dir))
    rule_text, rationale, matched_id = _choose_rule(error_type, error_message, rules)
    return {
        "rule_text": rule_text,
        "rationale": rationale,
        "matched_pattern": matched_id,
        "fallback": matched_id is None,
    }


def read_entry(path: Path) -> dict[str, Any]:
    """Load a SkillOutcome JSON file into a dict."""

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"SkillOutcome JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"SkillOutcome JSON must be an object: {path}")
    raw_dict = cast(dict[object, object], loaded)
    return {str(key): value for key, value in raw_dict.items()}


def _render_rule_entry(rule_text: str, entry: dict[str, Any]) -> str:
    """Render the bullet + source-line pair for a single learned rule."""

    run_id = str(entry.get("run_id", "") or "").strip()
    error_type = str(entry.get("error_type", "") or "").strip()
    source_bits: list[str] = []
    if run_id:
        source_bits.append(f"run_id={run_id}")
    if error_type:
        source_bits.append(f"error_type={error_type}")
    source_line = (
        f"Source: {', '.join(source_bits)}"
        if source_bits
        else "Source: SkillOutcome feedback"
    )
    return f"- {rule_text}\n  {source_line}\n"


def build_rule_block(rule_text: str, entry: dict[str, Any]) -> str:
    """Render the markdown block appended to SKILL.md.

    The block opens with a blank line so concatenation onto an ``rstrip()``'d
    body still leaves a blank line before the ``## Learned Rules`` heading.
    """

    return (
        "\n\n"
        "## Learned Rules\n\n"
        f"{APPEND_MARKER}\n"
        f"{_render_rule_entry(rule_text, entry)}"
    )


def patch_skill_file(skill_text: str, rule_block: str) -> str:
    """Return SKILL.md text with the rule block applied.

    Idempotency is per-rule: applying the same rendered rule entry twice is a
    no-op, but a second *distinct* rule accumulates as another bullet under
    the existing ``## Learned Rules`` section.
    """

    if not skill_text.endswith("\n"):
        skill_text += "\n"

    rule_entry = _extract_rule_entry(rule_block)

    # Per-rule dedupe: if this exact rule entry is already in the file, no-op.
    if rule_entry and rule_entry in skill_text:
        return skill_text

    # If a Learned Rules section already exists, append just the bullet under
    # it rather than starting a second section with a duplicate marker/heading.
    if "## Learned Rules" in skill_text and rule_entry:
        if not skill_text.endswith("\n\n"):
            skill_text = skill_text.rstrip("\n") + "\n"
        return skill_text + rule_entry

    return skill_text.rstrip() + rule_block


def _extract_rule_entry(rule_block: str) -> str:
    """Pull the bullet + source-line pair out of a freshly built rule block."""

    marker_token = f"{APPEND_MARKER}\n"
    if marker_token in rule_block:
        return rule_block.split(marker_token, 1)[1]
    return ""


def render_diff(original: str, updated: str, path: Path) -> str:
    """Produce a unified diff between the original and updated SKILL.md texts."""

    diff = difflib.unified_diff(
        original.splitlines(),
        updated.splitlines(),
        fromfile=str(path),
        tofile=str(path),
        lineterm="",
    )
    return "\n".join(diff)


__all__ = [
    "APPEND_MARKER",
    "FALLBACK_RULE",
    "KNOWN_RULES_DIR",
    "build_rule_block",
    "derive_rule_from_outcome",
    "patch_skill_file",
    "read_entry",
    "render_diff",
]
