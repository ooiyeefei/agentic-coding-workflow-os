from __future__ import annotations

from atelier.util.paths import run_dir

from .tree import list_stages


def next_stage_to_execute(run_id: str) -> str | None:
    for stage_id in list_stages(run_id):
        if not (run_dir(run_id) / "stages" / stage_id / ".complete").exists():
            return stage_id
    return None


__all__ = ["next_stage_to_execute"]
