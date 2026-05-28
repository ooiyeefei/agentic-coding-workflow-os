"""Extract engineering decisions from agent session transcripts using a local LLM.

Architecture:
    Session JSONL -> chunk into ~2000-token windows -> each chunk -> Ollama model
    -> structured JSON -> dedupe -> stage to .spanweave/memory/pending/decisions/
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

# Sentinel: when a caller passes model=None, resolve to the hardware-aware
# default (gemma4:e4b on GPU, qwen2.5:1.5b on CPU) at call time via
# default_model(). We avoid calling it at import to keep imports subprocess-free.

EXTRACTION_OPTIONS = {
    "temperature": 0.3,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 2048,
}

# Structured-output mode for extraction. "json" forces the model to emit
# syntactically valid JSON, which eliminates the bulk of the ~29% prose/fence
# parse-failures measured on small CPU models (qwen2.5:1.5b). The tolerant
# parser below then accepts whatever valid shape comes back — a bare array,
# an object wrapping the array (e.g. {"decisions": [...]}), or a single object.
# Swappable to a JSON-schema dict for schema-constrained output (Ollama >= 0.5).
EXTRACTION_FORMAT: str | dict[str, Any] = "json"

# Per-chunk HTTP timeout for extraction. The quality model (gemma4:e4b) can take
# ~120s for a large chunk on CPU; the default 120s timeout would spuriously fail
# those. Extraction runs detached, so a generous timeout costs nothing interactive.
EXTRACTION_TIMEOUT = 300.0

EXTRACTION_PROMPT = """\
You are a structured data extraction assistant. \
Read the conversation and extract engineering decisions.

Output ONLY a JSON object of the form {{"decisions": [ ... ]}}. \
No explanation, no commentary.

Each element of "decisions" is:
{{"type": "decision"|"rejected_alternative"|"finding", \
"body": "what was decided", "reasoning": "why", \
"tags": ["category"], "confidence": 0.0-1.0}}

Rules:
- Only definitive decisions actually made (not tentative/exploratory/proposed)
- Use {{"decisions": []}} if nothing was decided
- "body" must be a concrete decision, not a description of the conversation

Conversation:
---
{chunk}
---"""

# String confidence labels gemma occasionally emits instead of a number.
# Case-insensitive lookup; values match the numeric scale callers expect.
_CONFIDENCE_LABEL_MAP: dict[str, float] = {
    "high": 0.9,
    "highest": 0.9,
    "medium": 0.5,
    "med": 0.5,
    "low": 0.2,
}


def _coerce_confidence(value: Any) -> float:
    """Coerce a raw model confidence value into a clamped ``[0.0, 1.0]`` float.

    Small models (gemma in particular) sometimes emit a string label (``"High"``)
    or a quoted number (``"0.85"``) instead of a numeric confidence. The previous
    ``float(value)`` call raised ``ValueError`` on labels and dropped the whole
    chunk's decisions. This helper:

    - returns numerics directly (clamped to ``[0.0, 1.0]``),
    - maps known case-insensitive labels (``"high"``/``"low"``/``"medium"``/etc.),
    - attempts ``float()`` on other strings (handles ``"0.85"``),
    - falls back to ``0.5`` for anything else (None, dict, list, junk strings).
    """
    # bool is a subclass of int — exclude it here so True/False don't silently
    # turn into 1.0/0.0 (probably a model bug worth defaulting away from).
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        label = _CONFIDENCE_LABEL_MAP.get(value.strip().lower())
        if label is not None:
            return label
        try:
            return max(0.0, min(1.0, float(value)))
        except (ValueError, TypeError):
            return 0.5
    return 0.5


# Re-export for backward compatibility
from spanweave.learning.ollama_client import (  # noqa: E402
    OllamaNotAvailableError,
    call_ollama,
    default_model,
)


def _call_ollama(prompt: str, model: str) -> str:
    """Send a prompt to the Ollama API and return the response text.

    Delegates to the shared ollama_client module, requesting structured JSON
    output (``EXTRACTION_FORMAT``) so the model can't answer with prose/fences.
    """
    return call_ollama(
        prompt,
        model,
        options=EXTRACTION_OPTIONS,
        format=EXTRACTION_FORMAT,
        timeout=EXTRACTION_TIMEOUT,
    )


def chunk_session(session_path: Path, max_tokens: int = 2000) -> list[str]:
    """Split a session JSONL into conversation chunks for extraction.

    Reads the JSONL, extracts user + assistant text messages, groups them
    into chunks of roughly max_tokens size (estimated at 4 chars/token).
    """
    if not session_path.exists():
        raise FileNotFoundError(f"Session file not found: {session_path}")

    messages: list[str] = []
    for line in session_path.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg_type = entry.get("type", "")
        message = entry.get("message", "")
        if msg_type in ("user", "assistant") and message:
            messages.append(f"[{msg_type}]: {message}")

    if not messages:
        return []

    # Group messages into chunks based on approximate token count
    max_chars = max_tokens * 4  # ~4 chars per token
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for msg in messages:
        msg_length = len(msg)
        if current_length + msg_length > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(msg)
        current_length += msg_length

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def _strip_code_fences(text: str) -> str:
    """Strip a single wrapping ```lang ... ``` markdown fence, if present."""
    fence = re.match(r"\s*```[a-zA-Z0-9]*\n(.*?)\n?```\s*$", text, re.DOTALL)
    return fence.group(1) if fence else text


def _coerce_to_decision_list(parsed: Any) -> list[dict[str, Any]] | None:
    """Coerce a parsed JSON value into a list of decision dicts (or None).

    Small models under forced-JSON return one of several shapes; normalize them:
    - a bare array -> itself
    - a single decision object (has "body") -> wrapped in a one-item list
    - an object that wraps the array under some key ({"decisions": [...]}) ->
      the first list-of-objects value
    Returns None when the value isn't a usable JSON container, so the caller
    can fall through to substring extraction.
    """
    if isinstance(parsed, list):
        return cast("list[dict[str, Any]]", parsed)
    if isinstance(parsed, dict):
        obj = cast("dict[str, Any]", parsed)
        # A single decision object takes priority over its own inner lists
        # (e.g. its "tags" array), which a naive value-scan would grab.
        if "body" in obj:
            return [obj]
        for value in obj.values():
            if isinstance(value, list) and (not value or isinstance(value[0], dict)):
                return cast("list[dict[str, Any]]", value)
        return []
    return None


def _parse_json_from_response(response: str) -> list[dict[str, Any]]:
    """Parse a list of decision objects from a model response, tolerantly.

    Handles the shapes small models emit even under forced JSON: a bare array,
    an object wrapping the array under a key, a single decision object, and
    ```json``` fences. Returns [] when nothing usable is found.
    """
    text = _strip_code_fences(response).strip()

    # Direct parse of the de-fenced text.
    try:
        coerced = _coerce_to_decision_list(json.loads(text))
        if coerced is not None:
            return coerced
    except json.JSONDecodeError:
        pass

    # Fall back to locating a JSON array, then object, substring in free text.
    for pattern in (r"\[.*\]", r"\{.*\}"):
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            continue
        try:
            coerced = _coerce_to_decision_list(json.loads(match.group(0)))
        except json.JSONDecodeError:
            continue
        if coerced:
            return coerced

    return []


def extract_decisions_from_chunk(
    chunk: str,
    *,
    model: str | None = None,
    provider: str = "ollama",
) -> list[dict[str, Any]]:
    """Send a conversation chunk to the model and parse structured decision JSON.

    The extraction prompt asks the model to output JSON array of decisions.
    Each decision has: type, body, reasoning, tags, confidence.

    ``model=None`` resolves to the hardware-aware default (gemma4:e4b on GPU,
    qwen2.5:1.5b on CPU).

    Falls back gracefully if:
    - Ollama is not running (raises OllamaNotAvailableError)
    - Model output is not valid JSON (returns empty list + logs warning)
    """
    if model is None:
        model = default_model()
    prompt = EXTRACTION_PROMPT.format(chunk=chunk)
    response = _call_ollama(prompt, model)

    results = _parse_json_from_response(response)
    if not results:
        # Empty either because the model emitted no decisions (often correct —
        # e.g. a noisy/tool-output chunk) or, rarely under forced JSON, output we
        # couldn't parse. Either way: stage nothing for this chunk.
        logger.debug("No decisions parsed from chunk (len=%d)", len(chunk))
        return []

    # Validate each decision has required fields
    validated: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            continue
        if "body" not in item:
            continue
        # Normalize fields with defaults
        validated.append({
            "type": item.get("type", "decision"),
            "body": item["body"],
            "reasoning": item.get("reasoning", ""),
            "tags": item.get("tags", []),
            "confidence": _coerce_confidence(item.get("confidence", 0.5)),
        })

    return validated


def dedupe_against_existing(
    candidates: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[dict[str, Any]]:
    """Filter out decisions that already exist in memory.

    Simple heuristic: if a candidate's body text overlaps >80% with any
    existing decision's body (normalized, lowercase, stripped), skip it.
    """
    decisions_dir = repo_root / ".spanweave" / "memory" / "decisions"
    if not decisions_dir.exists():
        return candidates

    # Load existing decision bodies
    existing_bodies: list[str] = []
    for path in decisions_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        # Extract body after frontmatter
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip().lower()
        else:
            body = content.strip().lower()
        if body:
            existing_bodies.append(body)

    if not existing_bodies:
        return candidates

    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_body = candidate.get("body", "").strip().lower()
        if not candidate_body:
            continue

        is_duplicate = False
        for existing_body in existing_bodies:
            overlap = _compute_overlap(candidate_body, existing_body)
            if overlap > 0.8:
                is_duplicate = True
                break

        if not is_duplicate:
            filtered.append(candidate)

    return filtered


def _compute_overlap(text_a: str, text_b: str) -> float:
    """Compute character-level overlap ratio between two texts."""
    if not text_a or not text_b:
        return 0.0
    # Use set-based word overlap for efficiency
    words_a = set(text_a.split())
    words_b = set(text_b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    smaller = min(len(words_a), len(words_b))
    return len(intersection) / smaller


def dedupe_within_batch(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse near-identical decisions extracted within a single session.

    ``dedupe_against_existing`` only compares candidates to already-confirmed
    decisions, so two chunks that surface the same decision both survive (the
    measured 'run extract-latest' duplicate). This compares candidates against
    each other with the same >0.8 word-overlap heuristic, keeping the first
    occurrence and dropping empty-bodied items.
    """
    kept: list[dict[str, Any]] = []
    kept_norms: list[str] = []
    for candidate in candidates:
        body = candidate.get("body", "").strip().lower()
        if not body:
            continue
        if any(_compute_overlap(body, norm) > 0.8 for norm in kept_norms):
            continue
        kept.append(candidate)
        kept_norms.append(body)
    return kept


def stage_pending_decisions(
    decisions: list[dict[str, Any]],
    *,
    repo_root: Path,
    source: str = "auto-extraction",
) -> list[Path]:
    """Write extracted decisions to .spanweave/memory/pending/decisions/.

    Each decision becomes a markdown file with YAML frontmatter, using a
    similar format to spanweave/memory/records.py Decision type -- but placed
    in pending/ instead of decisions/ (pending = not yet confirmed).

    Returns paths of written files.
    """
    pending_dir = repo_root / ".spanweave" / "memory" / "pending" / "decisions"
    pending_dir.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    timestamp = datetime.now(UTC).isoformat()

    for i, decision in enumerate(decisions):
        tags_yaml = "\n".join(f"- {tag}" for tag in decision.get("tags", []))
        tags_section = f"tags:\n{tags_yaml}" if tags_yaml else "tags: []"

        frontmatter = f"""\
type: {decision.get('type', 'decision')}
source: {source}
confidence: {decision.get('confidence', 0.5)}
reasoning: {decision.get('reasoning', '')}
timestamp: {timestamp}
{tags_section}"""

        body = decision.get("body", "")
        content = f"---\n{frontmatter}\n---\n{body}\n"

        # Generate a filename based on timestamp and index
        safe_timestamp = timestamp.replace(":", "-").replace("+", "p")
        filename = f"pending_{safe_timestamp}_{i:03d}.md"
        filepath = pending_dir / filename
        filepath.write_text(content, encoding="utf-8")
        written_paths.append(filepath)

    return written_paths


def extract_from_session(
    session_path: Path,
    *,
    model: str | None = None,
    provider: str = "ollama",
    repo_root: Path | None = None,
    recent_chunks: int | None = None,
) -> list[dict[str, Any]]:
    """Extract decisions from a session transcript JSONL file.

    Reads the session file, chunks conversations into manageable windows,
    sends each chunk to the configured model for structured extraction,
    deduplicates results, and stages them to .spanweave/memory/pending/decisions/.

    ``model=None`` resolves to the hardware-aware default (gemma4:e4b on GPU,
    qwen2.5:1.5b on CPU).

    ``recent_chunks`` bounds work to the last N chunks — used by the Stop-hook
    path so a huge/compacted transcript can't trigger a multi-hour run. Because
    the hook fires every session end and dedup handles overlap, the most recent
    window is what each run needs; None (the default) processes the whole file
    (manual `extract`, first-time backfill).

    Returns the list of extracted (but not yet confirmed) decision dicts.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    if model is None:
        model = default_model()

    chunks = chunk_session(session_path)
    if recent_chunks is not None and recent_chunks > 0:
        chunks = chunks[-recent_chunks:]
    if not chunks:
        return []

    all_decisions: list[dict[str, Any]] = []
    for chunk in chunks:
        try:
            extracted = extract_decisions_from_chunk(chunk, model=model, provider=provider)
            all_decisions.extend(extracted)
        except OllamaNotAvailableError:
            raise
        except Exception:
            logger.warning("Failed to extract from chunk, skipping", exc_info=True)
            continue

    if not all_decisions:
        return []

    # First collapse duplicates surfaced across chunks within THIS session, then
    # drop any that duplicate an already-confirmed decision.
    batch_unique = dedupe_within_batch(all_decisions)
    unique_decisions = dedupe_against_existing(batch_unique, repo_root=repo_root)

    if not unique_decisions:
        return []

    # Stage to pending
    stage_pending_decisions(unique_decisions, repo_root=repo_root)

    return unique_decisions


__all__ = [
    "OllamaNotAvailableError",
    "chunk_session",
    "dedupe_against_existing",
    "dedupe_within_batch",
    "extract_decisions_from_chunk",
    "extract_from_session",
    "stage_pending_decisions",
]
