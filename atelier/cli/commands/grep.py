from __future__ import annotations

import re
from pathlib import Path

import click

from atelier.cli.formatters import build_help_epilog, echo_json, render_match_lines


def _iter_matches(
    root: Path,
    pattern: re.Pattern[str],
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    if not root.exists():
        return matches

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for line_number, line in enumerate(lines, start=1):
            if pattern.search(line):
                matches.append(
                    {
                        "path": str(path.relative_to(root.parent)),
                        "line": line_number,
                        "text": line,
                    }
                )
    return matches


@click.command(
    "grep",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "The pattern is treated as a Python regular expression and searches "
            "only under .atelier/.",
        ),
        examples=(
            "atelier grep 'issue #42' --repo .",
            "atelier grep 'waiting_reason: gate' --repo . --ignore-case --json",
        ),
    ),
)
@click.argument("pattern")
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root whose .atelier tree should be searched.",
)
@click.option(
    "--ignore-case",
    is_flag=True,
    help="Search case-insensitively.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def grep_command(pattern: str, repo: Path, ignore_case: bool, json_output: bool) -> None:
    """Search the local .atelier workspace with a regular expression."""

    flags = re.IGNORECASE if ignore_case else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        raise click.ClickException(f"Invalid regular expression: {exc}") from exc

    repo_path = repo.resolve()
    atelier_root = repo_path / ".atelier"
    matches = _iter_matches(atelier_root, compiled)

    if json_output:
        echo_json(
            {
                "pattern": pattern,
                "repo": str(repo_path),
                "match_count": len(matches),
                "matches": matches,
            }
        )
        return

    if not atelier_root.exists():
        click.echo(f"No .atelier workspace found under {repo_path}")
        return

    click.echo(render_match_lines(matches))
