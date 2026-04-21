from __future__ import annotations

from pathlib import Path

import yaml

from atelier.workflow.schema import WorkflowDefinition

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKFLOWS_DIR = _REPO_ROOT / ".atelier" / "defaults" / "workflows"
USER_WORKFLOWS_DIR = Path(".atelier") / "workflows"


class WorkflowNotFoundError(FileNotFoundError):
    def __init__(self, name: str, searched: list[Path]) -> None:
        paths_text = ", ".join(str(p) for p in searched)
        super().__init__(f"Workflow {name!r} not found in: {paths_text}")
        self.workflow_name = name
        self.searched_paths = searched


def load_workflow(
    name: str,
    *,
    user_dir: Path | None = None,
    defaults_dir: Path | None = None,
) -> WorkflowDefinition:
    resolved_user_dir = (user_dir or USER_WORKFLOWS_DIR).resolve()
    resolved_defaults_dir = (defaults_dir or DEFAULT_WORKFLOWS_DIR).resolve()

    candidates = [
        resolved_user_dir / f"{name}.yaml",
        resolved_defaults_dir / f"{name}.yaml",
    ]

    for path in candidates:
        if path.is_file():
            return _load_from_path(path)

    raise WorkflowNotFoundError(name, [resolved_user_dir, resolved_defaults_dir])


def _load_from_path(path: Path) -> WorkflowDefinition:
    raw_text = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return WorkflowDefinition.model_validate(parsed)


__all__ = [
    "DEFAULT_WORKFLOWS_DIR",
    "USER_WORKFLOWS_DIR",
    "WorkflowNotFoundError",
    "load_workflow",
]
