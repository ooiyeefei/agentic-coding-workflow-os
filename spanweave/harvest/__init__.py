"""Harvest coding agents' native memory into Spanweave's shared layer.

Each supported tool curates its own memory store. This package reads those
native stores and imports them into ``.spanweave/memory/pending/`` with a
``source: native-<tool>`` provenance field, so every tool can see what the
others remembered. Imported records flow through the same review → promote
pipeline as auto-extracted decisions.

Public surface:

- :data:`SUPPORTED_TOOLS` — canonical tool names accepted by ``--tool``.
- :func:`available_tools` — which of those have a native store present.
- :func:`harvest_tool` — read + stage one tool's native memory.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from spanweave.harvest.claude import claude_memory_dir, harvest_claude_memory
from spanweave.harvest.codex import codex_memory_dir, harvest_codex_memory

__all__ = [
    "SUPPORTED_TOOLS",
    "HarvestResult",
    "available_tools",
    "harvest_tool",
]

#: Canonical tool identifiers, used by the ``--tool`` option.
SUPPORTED_TOOLS: tuple[str, ...] = ("claude-code", "codex")

# Per-tool harvesters and native-store locators. The locator takes the repo
# root and returns the directory whose existence means "this tool has a native
# store here" — used for default tool discovery. (Codex memory is global, so its
# locator ignores the repo root.)
_HARVESTERS: dict[str, Callable[[Path], list[Path]]] = {
    "claude-code": harvest_claude_memory,
    "codex": harvest_codex_memory,
}

_STORE_LOCATORS: dict[str, Callable[[Path], Path]] = {
    "claude-code": claude_memory_dir,
    "codex": lambda _repo: codex_memory_dir(),
}


@dataclass(frozen=True)
class HarvestResult:
    """Outcome of harvesting a single tool's native memory."""

    tool: str
    staged: list[Path]
    store_present: bool

    @property
    def count(self) -> int:
        return len(self.staged)


def _store_present(tool: str, repo_root: Path) -> bool:
    return _STORE_LOCATORS[tool](repo_root).is_dir()


def available_tools(repo_root: Path) -> list[str]:
    """Return supported tools that have a native memory store present."""
    return [tool for tool in SUPPORTED_TOOLS if _store_present(tool, repo_root)]


def harvest_tool(
    tool: str, repo_root: Path, *, all_projects: bool = False
) -> HarvestResult:
    """Harvest a single tool's native memory into the pending queue.

    ``all_projects`` only affects ``codex``: Codex keeps a single global memory
    store, so by default its harvest is scoped to ``repo_root`` (only summaries
    whose ``cwd`` matches the repo). Pass ``all_projects=True`` to import every
    project's Codex memory. The Claude harvester is already per-repo and ignores
    the flag.

    Raises ``KeyError`` for an unknown tool name; the CLI validates the name via
    a Click ``Choice`` before calling this.
    """
    if tool == "codex":
        staged = harvest_codex_memory(repo_root, all_projects=all_projects)
    else:
        staged = _HARVESTERS[tool](repo_root)
    return HarvestResult(
        tool=tool, staged=staged, store_present=_store_present(tool, repo_root)
    )
