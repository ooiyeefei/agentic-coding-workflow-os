from __future__ import annotations

from pathlib import Path

import click

from atelier.cli.formatters import build_help_epilog, echo_json
from atelier.defaults import DEFAULT_WORKFLOWS_DIR

_DEFAULT_WORKFLOW = DEFAULT_WORKFLOWS_DIR / "speckit-loop.yaml"
_README_CONTENT = (
    "# Atelier Workspace\n\n"
    "This directory stores workflow state, audit logs, and user-editable workflow overrides.\n"
)


def _ensure_directory(path: Path) -> bool:
    if path.exists():
        return False
    path.mkdir(parents=True, exist_ok=True)
    return True


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


@click.command(
    "init",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "This command is idempotent and does not overwrite existing workspace files.",
        ),
        examples=(
            "atelier init --repo .",
            "atelier init --repo /path/to/repo --json",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root where .atelier/ should be scaffolded.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def init_command(repo: Path, json_output: bool) -> None:
    """Scaffold the local .atelier workspace in the target repository."""

    repo_path = repo.resolve()
    atelier_root = repo_path / ".atelier"

    created_dirs: list[str] = []
    created_files: list[str] = []

    for directory in (
        atelier_root,
        atelier_root / "workflows",
        atelier_root / "runs",
        atelier_root / "audit",
        atelier_root / "daemon",
        atelier_root / "memory" / "decisions",
        atelier_root / "memory" / "findings",
        atelier_root / "memory" / "rejected_alternatives",
        atelier_root / "memory" / "skill_outcomes",
        atelier_root / "memory" / "council_reports",
    ):
        if _ensure_directory(directory):
            created_dirs.append(str(directory.relative_to(repo_path)))

    if _write_if_missing(atelier_root / "README.md", _README_CONTENT):
        created_files.append(".atelier/README.md")

    workflow_target = atelier_root / "workflows" / "speckit-loop.yaml"
    if _DEFAULT_WORKFLOW.is_file() and _write_if_missing(
        workflow_target,
        _DEFAULT_WORKFLOW.read_text(encoding="utf-8"),
    ):
        created_files.append(str(workflow_target.relative_to(repo_path)))

    payload = {
        "repo": str(repo_path),
        "atelier_root": str(atelier_root),
        "created_dirs": created_dirs,
        "created_files": created_files,
        "changed": bool(created_dirs or created_files),
    }

    if json_output:
        echo_json(payload)
        return

    if payload["changed"]:
        click.echo(f"Initialized Atelier workspace at {atelier_root}")
        for path in [*created_dirs, *created_files]:
            click.echo(f"- {path}")
        return

    click.echo(f"Atelier workspace already initialized at {atelier_root}")
