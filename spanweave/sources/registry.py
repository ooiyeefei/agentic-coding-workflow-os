"""Registry of available source adapters.

Single source of truth for "which tools can spanweave read?". The CLI's
``--tool`` option and the auto-detection path both go through here so adding a
future adapter (e.g. Cursor) is a one-line change.
"""

from __future__ import annotations

from spanweave.sources.base import SessionSource
from spanweave.sources.claude_code import ClaudeCodeSource
from spanweave.sources.codex import CodexSource

# Registration order is also the auto-detection order. Claude Code first
# preserves historical single-tool behavior on Claude-only machines.
_SOURCE_CLASSES: tuple[type, ...] = (ClaudeCodeSource, CodexSource)

_SOURCES: dict[str, SessionSource] = {
    cls().name: cls() for cls in _SOURCE_CLASSES  # type: ignore[abstract]
}


def all_sources() -> list[SessionSource]:
    """Every registered adapter, in detection order.

    Returns fresh references to the shared singletons (cheap, stateless).
    """
    return list(_SOURCES.values())


def get_source(name: str) -> SessionSource:
    """Look up one adapter by its ``name`` (e.g. ``"codex"``).

    Raises ``KeyError`` with the list of known names if ``name`` is unknown, so
    the CLI can surface a clear error for a bad ``--tool`` value.
    """
    try:
        return _SOURCES[name]
    except KeyError as exc:
        known = ", ".join(sorted(_SOURCES)) or "<none>"
        raise KeyError(f"unknown source {name!r}; known sources: {known}") from exc


__all__ = ["all_sources", "get_source"]
