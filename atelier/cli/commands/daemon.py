from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import click

from atelier.cli.formatters import build_help_epilog, echo_json, render_daemon_status
from atelier.util.fs import atomic_write, safe_mkdir

_STATE_TEXT = "HTTP daemon arrives in W16. Current commands track placeholder daemon control state."


def _state_path(repo_path: Path) -> Path:
    return repo_path / ".atelier" / "daemon" / "state.json"


def _read_state(repo_path: Path) -> dict[str, object]:
    path = _state_path(repo_path)
    if not path.is_file():
        return {
            "state": "stopped",
            "mode": "placeholder",
            "state_path": str(path),
            "note": _STATE_TEXT,
        }

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload.setdefault("state_path", str(path))
        payload.setdefault("note", _STATE_TEXT)
        return payload
    return {
        "state": "stopped",
        "mode": "placeholder",
        "state_path": str(path),
        "note": _STATE_TEXT,
    }


def _write_state(repo_path: Path, state: str) -> dict[str, object]:
    import json

    path = _state_path(repo_path)
    safe_mkdir(path.parent)
    payload = {
        "state": state,
        "mode": "placeholder",
        "updated_at": datetime.now(UTC).isoformat(),
        "state_path": str(path),
        "note": _STATE_TEXT,
    }
    atomic_write(path, json.dumps(payload, indent=2) + "\n")
    return payload


@click.group(
    "daemon",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "These commands manage the placeholder daemon state until the HTTP "
            "daemon lands in W16.",
        ),
        examples=(
            "atelier daemon start --repo .",
            "atelier daemon status --repo . --json",
            "atelier daemon stop --repo .",
        ),
    ),
)
def daemon_group() -> None:
    """Control the placeholder daemon state until the HTTP server lands in W16."""


@daemon_group.command(
    "start",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "This records placeholder state only. It does not launch a "
            "background HTTP process yet.",
        ),
        examples=(
            "atelier daemon start --repo .",
            "atelier daemon start --repo . --json",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root where daemon state should be recorded.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def daemon_start(repo: Path, json_output: bool) -> None:
    """Mark the local daemon control state as running."""

    repo_path = repo.resolve()
    payload = _read_state(repo_path)
    if payload.get("state") != "running":
        payload = _write_state(repo_path, "running")

    if json_output:
        echo_json(payload)
        return

    click.echo(render_daemon_status(payload))


@daemon_group.command(
    "stop",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "This clears the placeholder running state. It does not signal a real daemon yet.",
        ),
        examples=(
            "atelier daemon stop --repo .",
            "atelier daemon stop --repo . --json",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root where daemon state should be recorded.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def daemon_stop(repo: Path, json_output: bool) -> None:
    """Mark the local daemon control state as stopped."""

    repo_path = repo.resolve()
    payload = _write_state(repo_path, "stopped")

    if json_output:
        echo_json(payload)
        return

    click.echo(render_daemon_status(payload))


@daemon_group.command(
    "status",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Status is read from .atelier/daemon/state.json until the real daemon lands in W16.",
        ),
        examples=(
            "atelier daemon status --repo .",
            "atelier daemon status --repo . --json",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root where daemon state should be recorded.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def daemon_status(repo: Path, json_output: bool) -> None:
    """Show the current local daemon control state."""

    repo_path = repo.resolve()
    payload = _read_state(repo_path)

    if json_output:
        echo_json(payload)
        return

    click.echo(render_daemon_status(payload))
