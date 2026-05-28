"""Synthesize higher-order lessons from accumulated decisions using a local LLM.

Architecture:
    Read decisions from .spanweave/memory/ -> batch into context window
    -> send to model with thinking enabled -> structured reflection output
    -> stage as reflection records in .spanweave/memory/pending/reflections/
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from spanweave.learning.ollama_client import (
    OllamaNotAvailableError,
    call_ollama,
    default_model,
)

logger = logging.getLogger(__name__)

# Default model for reflection (benefits from reasoning, unlike extraction)
REFLECTION_MODEL = "gemma4:e4b"

REFLECTION_OPTIONS = {
    "temperature": 0.7,  # More creative than extraction (0.3) but not wild
    "top_p": 0.95,
    "top_k": 64,
    "num_predict": 4096,  # Reflections can be longer than extractions
}

REFLECTION_PROMPT = """\
<|think|>
You are analyzing a set of engineering decisions made during recent coding sessions.
Synthesize ONE high-level lesson or pattern from these decisions.

The lesson should be:
- Actionable (a future agent could apply it)
- Specific to this project (not generic advice)
- Grounded in the evidence below (cite which decisions support it)

Output JSON:
{{"lesson": "the synthesized insight", "supporting_decisions": ["id1", "id2"], \
"tags": ["relevant", "tags"], "confidence": 0.0-1.0, \
"applies_to": "description of when this lesson applies"}}

Decisions from recent sessions:
---
{decisions_text}
---"""


def reflect_on_decisions(
    *,
    repo_root: Path,
    model: str | None = None,
    min_decisions: int = 3,
    max_decisions: int = 20,
) -> dict[str, Any] | None:
    """Synthesize a lesson from accumulated decisions.

    Reads recent decisions from .spanweave/memory/ (both flat and shared/),
    sends them to the model with thinking enabled, and returns the
    structured reflection.

    ``model=None`` resolves to the hardware-aware default (gemma4:e4b on GPU,
    qwen2.5:1.5b on CPU).

    Returns None if fewer than min_decisions are available (not enough
    data to reflect on).
    """
    if model is None:
        model = default_model()
    decisions = _gather_recent_decisions(repo_root, max_count=max_decisions)

    if len(decisions) < min_decisions:
        return None

    decisions_text = _format_decisions_for_prompt(decisions)
    prompt = REFLECTION_PROMPT.format(decisions_text=decisions_text)

    response = call_ollama(prompt, model, options=REFLECTION_OPTIONS)
    return _parse_reflection_response(response, decisions)


def _gather_recent_decisions(repo_root: Path, max_count: int) -> list[dict[str, Any]]:
    """Read the most recent decisions from memory, sorted by timestamp."""
    decisions: list[dict[str, Any]] = []

    # Look in both confirmed decisions and shared decisions
    search_dirs = [
        repo_root / ".spanweave" / "memory" / "decisions",
        repo_root / ".spanweave" / "memory" / "shared" / "decisions",
    ]

    for decisions_dir in search_dirs:
        if not decisions_dir.exists():
            continue
        for path in decisions_dir.glob("*.md"):
            parsed = _parse_decision_file(path)
            if parsed is not None:
                decisions.append(parsed)

    # Sort by timestamp (most recent first), then limit
    decisions.sort(key=lambda d: d.get("timestamp", ""), reverse=True)
    return decisions[:max_count]


def _parse_decision_file(path: Path) -> dict[str, Any] | None:
    """Parse a decision markdown file with YAML frontmatter."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    # Simple YAML parsing (key: value lines)
    metadata: dict[str, Any] = {"id": path.stem, "body": body, "path": str(path)}
    for line in frontmatter_text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and value:
                metadata[key] = value

    return metadata


def _format_decisions_for_prompt(decisions: list[dict[str, Any]]) -> str:
    """Format decision records into text for the reflection prompt."""
    lines: list[str] = []
    for i, decision in enumerate(decisions, 1):
        decision_id = decision.get("id", f"decision_{i}")
        body = decision.get("body", "")
        reasoning = decision.get("reasoning", "")
        tags = decision.get("tags", "")
        timestamp = decision.get("timestamp", "")

        entry = f"[{decision_id}] {body}"
        if reasoning:
            entry += f"\n  Reasoning: {reasoning}"
        if tags:
            entry += f"\n  Tags: {tags}"
        if timestamp:
            entry += f"\n  When: {timestamp}"
        lines.append(entry)

    return "\n\n".join(lines)


def _parse_reflection_response(
    response: str, decisions: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Parse structured JSON from the model's reflection response."""
    # Try direct parse
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict) and "lesson" in parsed:
            return _validate_reflection(cast(dict[str, Any], parsed), decisions)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in response
    match = re.search(r"\{[^{}]*\"lesson\"[^{}]*\}", response, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and "lesson" in parsed:
                return _validate_reflection(cast(dict[str, Any], parsed), decisions)
        except json.JSONDecodeError:
            pass

    # Try a more permissive regex for nested structures
    match = re.search(r"\{.*\"lesson\".*\}", response, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and "lesson" in parsed:
                return _validate_reflection(cast(dict[str, Any], parsed), decisions)
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse reflection response as JSON")
    return None


def _validate_reflection(
    parsed: dict[str, Any], decisions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Normalize and validate parsed reflection fields."""
    return {
        "lesson": str(parsed.get("lesson", "")),
        "supporting_decisions": [
            sid
            for sid in parsed.get("supporting_decisions", [])
            if isinstance(sid, str)
        ],
        "tags": [t for t in parsed.get("tags", []) if isinstance(t, str)],
        "confidence": float(parsed.get("confidence", 0.5)),
        "applies_to": str(parsed.get("applies_to", "")),
    }


def stage_reflection(
    reflection: dict[str, Any],
    *,
    repo_root: Path,
    source: str = "auto-reflection",
) -> Path:
    """Write a reflection to .spanweave/memory/pending/reflections/.

    Uses the same frontmatter markdown format as other records.
    """
    pending_dir = repo_root / ".spanweave" / "memory" / "pending" / "reflections"
    pending_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).isoformat()
    tags = reflection.get("tags", [])
    tags_yaml = "\n".join(f"- {tag}" for tag in tags) if tags else ""
    tags_section = f"tags:\n{tags_yaml}" if tags_yaml else "tags: []"

    supporting = reflection.get("supporting_decisions", [])
    supporting_yaml = (
        "\n".join(f"- {sid}" for sid in supporting) if supporting else ""
    )
    supporting_section = (
        f"supporting_decisions:\n{supporting_yaml}"
        if supporting_yaml
        else "supporting_decisions: []"
    )

    frontmatter = f"""\
type: Reflection
source: {source}
confidence: {reflection.get('confidence', 0.5)}
applies_to: {reflection.get('applies_to', '')}
timestamp: {timestamp}
{tags_section}
{supporting_section}"""

    body = reflection.get("lesson", "")
    content = f"---\n{frontmatter}\n---\n{body}\n"

    # Generate filename
    safe_timestamp = timestamp.replace(":", "-").replace("+", "p")
    filename = f"reflection_{safe_timestamp}.md"
    filepath = pending_dir / filename
    filepath.write_text(content, encoding="utf-8")

    return filepath


__all__ = [
    "OllamaNotAvailableError",
    "REFLECTION_MODEL",
    "REFLECTION_OPTIONS",
    "REFLECTION_PROMPT",
    "reflect_on_decisions",
    "stage_reflection",
]
