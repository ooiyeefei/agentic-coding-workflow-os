"""CLI command: spanweave eval — dual-track recall-compare.

Buckets memory records by ``source:`` into Track A (agent native-curated,
``native-*``) vs Track B (gemma ``auto-extraction``), matches them by word
overlap, and reports ``recall = |A∩B| / |A|`` plus the A-only coverage gaps
and B-only extras.

Note: ``eval`` is a Python builtin, so the function is named ``eval_command``;
only the click command name is the bare string ``"eval"``.
"""

from __future__ import annotations

from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog, echo_json
from spanweave.eval import EvalRecord, RecallReport, run_eval

# How many example bodies to show per bucket in the human-readable report, and
# how many characters of each body to show before truncating.
_MAX_EXAMPLES = 5
_BODY_TRUNCATE = 160


def _truncate(body: str, limit: int = _BODY_TRUNCATE) -> str:
    """One-line, length-bounded preview of a record body."""
    flattened = " ".join(body.split())
    if len(flattened) <= limit:
        return flattened
    return flattened[: limit - 1].rstrip() + "…"


def _record_json(record: EvalRecord) -> dict[str, object]:
    return {
        "path": str(record.path),
        "source": record.source,
        "body": record.body,
    }


def _emit_json(report: RecallReport) -> None:
    echo_json(
        {
            "threshold": report.threshold,
            "track_a_size": report.track_a_size,
            "track_b_size": report.track_b_size,
            "recall": round(report.recall, 4),
            "counts": {
                "intersection": len(report.intersection),
                "a_only": len(report.a_only),
                "b_only": len(report.b_only),
            },
            "intersection": [_record_json(r) for r in report.intersection],
            "a_only": [_record_json(r) for r in report.a_only],
            "b_only": [_record_json(r) for r in report.b_only],
        }
    )


def _emit_empty_a_json(track_b_size: int) -> None:
    echo_json(
        {
            "threshold": None,
            "track_a_size": 0,
            "track_b_size": track_b_size,
            "recall": None,
            "counts": {"intersection": 0, "a_only": 0, "b_only": track_b_size},
            "message": (
                "No native-* records found — run `spanweave harvest` first to "
                "populate Track A."
            ),
        }
    )


def _echo_examples(label: str, records: list[EvalRecord]) -> None:
    click.echo(f"\n{label} ({len(records)}):")
    if not records:
        click.echo("  (none)")
        return
    for record in records[:_MAX_EXAMPLES]:
        click.echo(f"  - {_truncate(record.body)}")
    remaining = len(records) - _MAX_EXAMPLES
    if remaining > 0:
        click.echo(f"  … and {remaining} more")


def _emit_report(report: RecallReport) -> None:
    click.echo("Spanweave dual-track recall-compare")
    click.echo(f"  threshold              : {report.threshold}")
    click.echo(f"  Track A (native)       : {report.track_a_size}")
    click.echo(f"  Track B (auto-extract) : {report.track_b_size}")
    click.echo(
        f"  recall = |A∩B| / |A|   : {report.recall:.1%} "
        f"({len(report.intersection)}/{report.track_a_size})"
    )
    _echo_examples("A∩B  recalled (agent kept it, gemma also found it)", report.intersection)
    _echo_examples("A−B  coverage gaps (agent kept it, gemma missed it)", report.a_only)
    _echo_examples("B−A  extras (gemma found it, agent did not curate it)", report.b_only)


@click.command(
    "eval",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Track A = records the agent itself curated (source: native-*). "
            "Track B = gemma auto-extraction (source: auto-extraction).",
            "recall = |A∩B| / |A|: of what the agents kept, the fraction "
            "Spanweave's extraction also captured. No golden set needed — "
            "Track A is the reference.",
            "Populate Track A with `spanweave harvest` if it is empty.",
        ),
        examples=(
            "spanweave eval --repo .",
            "spanweave eval --repo . --threshold 0.6",
            "spanweave eval --repo . --no-include-pending --json",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
@click.option(
    "--threshold",
    default=0.5,
    show_default=True,
    type=click.FloatRange(0.0, 1.0),
    help="Word-overlap similarity at/above which an A record counts as recalled.",
)
@click.option(
    "--include-pending/--no-include-pending",
    "include_pending",
    default=True,
    show_default=True,
    help="Include not-yet-reviewed pending/ records (default: include).",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def eval_command(
    repo: Path,
    threshold: float,
    include_pending: bool,
    json_output: bool,
) -> None:
    """Compare gemma extraction (Track B) against agent native memory (Track A)."""
    repo_path = repo.resolve()
    result = run_eval(
        repo_path,
        threshold=threshold,
        include_pending=include_pending,
    )

    # Empty Track A: no native memory harvested yet. Helpful guidance, exit 0.
    if result.report is None:
        if json_output:
            _emit_empty_a_json(len(result.track_b))
        else:
            click.echo(
                "No native-* records found — run `spanweave harvest` first to "
                "populate Track A.\n"
                f"(Track B has {len(result.track_b)} auto-extraction record(s).)"
            )
        return

    if json_output:
        _emit_json(result.report)
        return

    _emit_report(result.report)


__all__ = ["eval_command"]
