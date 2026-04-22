from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from atelier.cli.formatters import build_help_epilog, echo_json, pushd

_STATE_FILE = "workflow_state.yaml"


class RunRecordLoadError(Exception):
    """Raised when persisted run metadata cannot be read safely."""


@dataclass(frozen=True)
class StageRecord:
    stage_id: str
    status: str
    path: Path

    def to_payload(self) -> dict[str, str]:
        return {
            "stage_id": self.stage_id,
            "status": self.status,
            "path": str(self.path),
        }


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    issue_ref: str
    workflow: str
    status: str
    current_stage: str | None
    waiting_reason: str | None
    last_transition: str | None
    last_transition_reason: str | None
    retry_count: int
    run_path: Path
    stages: list[StageRecord]

    def to_payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "issue_ref": self.issue_ref,
            "workflow": self.workflow,
            "status": self.status,
            "current_stage": self.current_stage,
            "waiting_reason": self.waiting_reason,
            "last_transition": self.last_transition,
            "last_transition_reason": self.last_transition_reason,
            "retry_count": self.retry_count,
            "run_path": str(self.run_path),
            "stages": [stage.to_payload() for stage in self.stages],
        }


def _placeholder_deps() -> Any:
    from atelier.workflow.stages import StageExecutorDeps

    return StageExecutorDeps(
        persona_caller=object(),
        reviewer_caller=object(),
        evidence_writer=object(),
    )


def _normalize_issue_ref(issue: str) -> str:
    stripped = issue.strip()
    if stripped.isdigit():
        return f"issue #{stripped}"
    return stripped


def _state_path(repo_path: Path, run_id: str) -> Path:
    from atelier.util.paths import run_dir

    return repo_path / run_dir(run_id) / _STATE_FILE


def _run_path(repo_path: Path, run_id: str) -> Path:
    from atelier.util.paths import run_dir

    return repo_path / run_dir(run_id)


def _run_root(repo_path: Path) -> Path:
    return repo_path / ".atelier" / "runs"


def _list_run_ids(repo_path: Path) -> list[str]:
    from atelier.util.paths import run_dir

    run_root = _run_root(repo_path)
    if not run_root.exists():
        return []

    run_ids: list[str] = []
    for path in run_root.iterdir():
        if not path.is_dir():
            continue
        try:
            run_dir(path.name)
        except ValueError:
            continue
        run_ids.append(path.name)
    return sorted(run_ids, reverse=True)


def _read_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.is_file():
        return {}

    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RunRecordLoadError(f"Malformed YAML in {path}.") from exc

    if isinstance(parsed, dict):
        return parsed
    return {}


def _read_frontmatter(path: Path) -> dict[str, Any]:
    import yaml

    if not path.is_file():
        return {}

    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}

    _, _, remainder = raw.partition("---\n")
    frontmatter_text, _, _ = remainder.partition("\n---\n")

    try:
        parsed = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        raise RunRecordLoadError(f"Malformed frontmatter YAML in {path}.") from exc

    if isinstance(parsed, dict):
        return parsed
    return {}


def _stage_ids(repo_path: Path, run_id: str) -> list[str]:
    stages_root = _run_path(repo_path, run_id) / "stages"
    if not stages_root.exists():
        return []
    return sorted(path.name for path in stages_root.iterdir() if path.is_dir())


def _current_stage(repo_path: Path, run_id: str) -> str | None:
    from atelier.util.paths import run_dir

    for stage_id in _stage_ids(repo_path, run_id):
        if not (repo_path / run_dir(run_id) / "stages" / stage_id / ".complete").exists():
            return stage_id
    return None


def load_run_record(repo_path: Path, run_id: str) -> RunRecord:
    run_path = _run_path(repo_path, run_id)
    if not run_path.is_dir():
        raise FileNotFoundError(f"run not found: {run_id}")

    metadata = _read_frontmatter(run_path / "run.md")
    state = _read_yaml(_state_path(repo_path, run_id))
    current_stage = _current_stage(repo_path, run_id)

    stages: list[StageRecord] = []
    for stage_id in _stage_ids(repo_path, run_id):
        stage_path = run_path / "stages" / stage_id
        if (stage_path / ".complete").exists():
            stage_status = "completed"
        elif stage_id == current_stage:
            stage_status = state.get("status", "running")
        else:
            stage_status = "created"
        stages.append(StageRecord(stage_id=stage_id, status=stage_status, path=stage_path))

    status = state.get("status", "completed" if stages and current_stage is None else "running")
    workflow = state.get("workflow", "unknown")
    issue_ref = str(metadata.get("issue_ref", ""))

    return RunRecord(
        run_id=run_id,
        issue_ref=issue_ref,
        workflow=workflow,
        status=status,
        current_stage=current_stage,
        waiting_reason=state.get("waiting_reason"),
        last_transition=state.get("last_transition"),
        last_transition_reason=state.get("last_transition_reason"),
        retry_count=int(state.get("retry_count", 0)),
        run_path=run_path,
        stages=stages,
    )


def load_run_record_for_cli(repo_path: Path, run_id: str) -> RunRecord:
    from pydantic import ValidationError

    try:
        return load_run_record(repo_path, run_id)
    except (ValueError, ValidationError) as exc:
        raise click.ClickException(
            f"Invalid run_id '{run_id}'. Expected a value like 'run_<ULID>'."
        ) from exc
    except FileNotFoundError as exc:
        run_root = repo_path / ".atelier" / "runs"
        raise click.ClickException(
            f"Run {run_id} was not found under {run_root}. "
            f"Run 'atelier run list --repo {repo_path}' to inspect known runs."
        ) from exc
    except RunRecordLoadError as exc:
        raise click.ClickException(
            f"Run {run_id} has unreadable metadata. {exc}"
        ) from exc


def list_run_records(repo_path: Path) -> list[RunRecord]:
    return [load_run_record(repo_path, run_id) for run_id in _list_run_ids(repo_path)]


def list_run_records_for_cli(repo_path: Path) -> list[RunRecord]:
    return [load_run_record_for_cli(repo_path, run_id) for run_id in _list_run_ids(repo_path)]


def get_repo_from_context(ctx: click.Context) -> Path:
    obj = ctx.ensure_object(dict)
    repo_path = obj.get("repo")
    if not isinstance(repo_path, Path):
        repo_path = Path(".").resolve()
        obj["repo"] = repo_path
    return repo_path


def _resume_gate_wait(repo_path: Path, run_id: str) -> RunRecord:
    from atelier.workflow.engine import WorkflowEngine

    with pushd(repo_path):
        engine = WorkflowEngine(deps=_placeholder_deps())
        asyncio.run(engine.resume(run_id, approved=True))

    return load_run_record_for_cli(repo_path, run_id)


def _add_subcommands(commands: Iterable[click.Command]) -> None:
    for command in commands:
        run_command.add_command(command)


def _register_subcommands() -> None:
    from atelier.cli.commands.list import list_command
    from atelier.cli.commands.show import show_command

    _add_subcommands((list_command, show_command))


@click.group(
    "run",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Invoke 'atelier run' directly to start a new workflow run. Use the "
            "subcommands to inspect existing runs.",
            "Human-readable output is the default. Add --json to supported commands for scripting.",
        ),
        examples=(
            "atelier run --issue 42 --repo .",
            "atelier run --issue issue-42 --workflow speckit-loop "
            "--context 'hotfix' --repo . --json",
            "atelier run list --repo .",
            "atelier run show run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
            "atelier run resume run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo . --approve",
        ),
    ),
    invoke_without_command=True,
)
@click.option("--issue", help="Issue reference or identifier to attach to the run.")
@click.option(
    "--workflow",
    default="speckit-loop",
    show_default=True,
    help="Workflow definition to start.",
)
@click.option(
    "--context",
    default="",
    show_default=False,
    help="Optional extra run context stored with the workflow state.",
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .atelier workspace.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_context
def run_command(
    ctx: click.Context,
    issue: str | None,
    workflow: str,
    context: str,
    repo: Path,
    json_output: bool,
) -> None:
    """Start a new workflow run or access the run inspection subcommands."""

    repo_path = repo.resolve()
    ctx.ensure_object(dict)
    ctx.obj["repo"] = repo_path

    if ctx.invoked_subcommand is not None:
        return

    if not issue:
        raise click.UsageError(
            "Missing option '--issue'. Use 'atelier run --issue <value>' or a nested subcommand."
        )

    from atelier.workflow.engine import WorkflowEngine

    with pushd(repo_path):
        engine = WorkflowEngine(deps=_placeholder_deps())
        run_id = engine.start(
            issue_ref=_normalize_issue_ref(issue),
            workflow_name=workflow,
            context=context,
        )

    record = load_run_record_for_cli(repo_path, run_id)
    payload = record.to_payload()

    if json_output:
        echo_json(payload)
        return

    click.echo(f"Started run {record.run_id}")
    click.echo(f"Issue: {record.issue_ref}")
    click.echo(f"Workflow: {record.workflow}")
    if record.current_stage:
        click.echo(f"Current stage: {record.current_stage}")


@run_command.command(
    "resume",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Without --approve this command only reports the current blocked state.",
            "CLI approval currently supports gate waits only; policy and council "
            "waits still need an execution backend.",
        ),
        examples=(
            "atelier run resume run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
            "atelier run resume run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo . --approve",
            "atelier run resume run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo . --approve --json",
        ),
    ),
)
@click.argument("run_id")
@click.option(
    "--approve",
    is_flag=True,
    help="Advance a run that is blocked on a completed gate approval.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_context
def resume_command(
    ctx: click.Context,
    run_id: str,
    approve: bool,
    json_output: bool,
) -> None:
    """Inspect a run resume point or approve a completed gate."""

    repo_path = get_repo_from_context(ctx)
    record = load_run_record_for_cli(repo_path, run_id)

    if approve:
        if record.status != "waiting_approval":
            raise click.ClickException(
                f"Run {run_id} is {record.status}; only waiting_approval runs can be approved."
            )
        if record.waiting_reason != "gate":
            raise click.ClickException(
                "Only completed gate approvals can be resumed from the CLI today. "
                "Policy-blocked or council-blocked stages still need an execution backend."
            )
        record = _resume_gate_wait(repo_path, run_id)

    payload = record.to_payload()
    if json_output:
        echo_json(payload)
        return

    if approve:
        click.echo(f"Approved gate and resumed {run_id}")
    else:
        click.echo(f"Run {run_id} is {record.status}")
    if record.current_stage:
        click.echo(f"Current stage: {record.current_stage}")
    if record.waiting_reason:
        click.echo(f"Waiting reason: {record.waiting_reason}")


_register_subcommands()
