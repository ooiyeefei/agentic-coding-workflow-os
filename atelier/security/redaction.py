from __future__ import annotations

import re
from collections.abc import Iterable

_ENV_ASSIGNMENT_RE = re.compile(
    r"(?im)\b([A-Z][A-Z0-9_]*(?:API_KEY|SECRET|PASSWORD|TOKEN|PRIVATE_KEY|DATABASE_URL))\b"
    r"\s*=\s*([^\s\"']+)"
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\b(Bearer)\s+([A-Za-z0-9._-]+)")
_OPENAI_KEY_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]+)\b")


def redact(text: str, extra_patterns: Iterable[str] | None = None) -> str:
    """Redact secret-like substrings before content is persisted."""

    redacted = _ENV_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}=[REDACTED:env-var]",
        text,
    )
    redacted = _BEARER_TOKEN_RE.sub(
        lambda match: f"{match.group(1)} [REDACTED:bearer-token]",
        redacted,
    )
    redacted = _OPENAI_KEY_RE.sub("[REDACTED:openai-key]", redacted)

    for index, pattern in enumerate(extra_patterns or (), start=1):
        redacted = re.compile(pattern).sub(f"[REDACTED:extra-pattern-{index}]", redacted)

    return redacted


__all__ = ["redact"]
