"""Spanweave eval: dual-track recall-compare.

Buckets decision records by their ``source:`` frontmatter into two tracks and
measures how well Track B (gemma auto-extraction) recalls Track A (the coding
agents' own native-memory curation):

- **Track A** — ``source`` starts with ``native-`` (e.g. ``native-claude``,
  ``native-codex``): sparse, high-precision, what the agent itself judged
  worth remembering. This is the *reference*.
- **Track B** — ``source == "auto-extraction"``: comprehensive, machine-inferred
  by Spanweave's local LLM. This is *what we're measuring*.

The headline metric is ``recall = |A∩B| / |A|`` — of the things the agents
thought mattered, what fraction did Spanweave's extraction also capture.
"""

from __future__ import annotations

from spanweave.eval.recall import (
    EvalRecord,
    RecallReport,
    bucket_records,
    compare_tracks,
    load_records,
    run_eval,
)

__all__ = [
    "EvalRecord",
    "RecallReport",
    "bucket_records",
    "compare_tracks",
    "load_records",
    "run_eval",
]
