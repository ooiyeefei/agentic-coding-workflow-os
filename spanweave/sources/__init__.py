"""Source adapters: tool-agnostic access to agent session transcripts.

Spanweave's "ambient memory" thesis is that decisions captured from one coding
agent should survive into the next — regardless of which tool produced them.
The extraction pipeline (chunk -> local LLM -> stage) is identical across tools;
only *finding* the latest transcript and *parsing* its message schema differ.

This package isolates those two tool-specific concerns behind a single
``SessionSource`` protocol so ``extract-latest`` can read Claude Code AND Codex
(and, later, Cursor/others) through one uniform interface.

Public API:
    SessionSource    -- the protocol every adapter implements
    ClaudeCodeSource -- ~/.claude/projects/<encoded-cwd>/*.jsonl
    CodexSource      -- ~/.codex/sessions/**/rollout-*.jsonl (matched by cwd)
    get_source(name) -- look up one adapter by its ``name``
    all_sources()    -- every registered adapter (auto-detection order)
"""

from __future__ import annotations

from spanweave.sources.base import SessionSource
from spanweave.sources.claude_code import ClaudeCodeSource
from spanweave.sources.codex import CodexSource
from spanweave.sources.registry import all_sources, get_source

__all__ = [
    "ClaudeCodeSource",
    "CodexSource",
    "SessionSource",
    "all_sources",
    "get_source",
]
