from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from atelier.council.schema import CouncilReport

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COUNCIL_MEMORY_DIR = REPO_ROOT / ".atelier" / "memory" / "council_reports"


def write_council_report(
    report: CouncilReport,
    directory: str | Path = DEFAULT_COUNCIL_MEMORY_DIR,
) -> CouncilReport:
    memory_dir = Path(directory)
    memory_dir.mkdir(parents=True, exist_ok=True)

    stored_report = report.model_copy(update={"memory_path": None})
    record_path = memory_dir / f"{stored_report.id}.md"
    metadata = {
        "id": stored_report.id,
        "type": "council_report",
        "created_at": stored_report.created_at.isoformat(),
        "final_verdict": stored_report.final_verdict.value,
        "models": stored_report.models,
    }
    record_path.write_text(_serialize_report(stored_report, metadata), encoding="utf-8")
    return stored_report.model_copy(update={"memory_path": str(record_path)})


def _render_report_body(report: CouncilReport) -> str:
    vote_lines = [
        (
            f"- `{vote.model}` (`{vote.provider}`): `{vote.verdict.value}` "
            f"(response_id={vote.response_id or 'n/a'}, "
            f"input_tokens={vote.usage.input_tokens}, "
            f"output_tokens={vote.usage.output_tokens}, "
            f"total_usd={vote.cost.total_usd or 0.0:.6f})"
        )
        for vote in report.votes
    ]
    votes_block = "\n".join(vote_lines)
    return (
        "## Positions\n\n"
        "### Position A (`COMPATIBLE_WITH_CODER`)\n\n"
        f"{report.coder_position}\n\n"
        "### Position B (`COMPATIBLE_WITH_REVIEWER`)\n\n"
        f"{report.reviewer_position}\n\n"
        "## Context\n\n"
        f"{report.context}\n\n"
        "## Votes\n\n"
        f"{votes_block}\n\n"
        "## Final Verdict\n\n"
        f"`{report.final_verdict.value}`\n"
    )


def _serialize_report(report: CouncilReport, metadata: Mapping[str, object]) -> str:
    rendered_metadata = yaml.safe_dump(metadata, sort_keys=False).strip()
    return f"---\n{rendered_metadata}\n---\n\n{_render_report_body(report)}"


__all__ = ["DEFAULT_COUNCIL_MEMORY_DIR", "write_council_report"]
