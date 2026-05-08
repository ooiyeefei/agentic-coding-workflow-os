from __future__ import annotations

from pathlib import Path

from .base import (
    DEFAULT_ADAPTER_MANIFEST_DIR,
    ToolAdapter,
    ToolManifest,
    TranscriptEntry,
    extract_records_from_entries,
    load_shipped_manifest,
    load_tool_manifest,
    load_tool_manifests,
)
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .generic import GenericAdapter


def detect_active_adapter(repo_root: str | Path | None = None) -> ToolAdapter | None:
    resolved_root = Path(repo_root or Path.cwd())
    for adapter_class in (CodexAdapter, ClaudeCodeAdapter):
        adapter = adapter_class(repo_root=resolved_root)
        if adapter.detect():
            return adapter
    return None


__all__ = [
    "DEFAULT_ADAPTER_MANIFEST_DIR",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "GenericAdapter",
    "ToolAdapter",
    "ToolManifest",
    "TranscriptEntry",
    "detect_active_adapter",
    "extract_records_from_entries",
    "load_shipped_manifest",
    "load_tool_manifest",
    "load_tool_manifests",
]
