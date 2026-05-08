from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from spanweave.util.paths import run_dir


def assert_run_artifact_completeness(
    repo_root: Path,
    run_id: str,
    stage_ids: Sequence[str],
) -> list[str]:
    resolved_repo_root = repo_root.resolve()
    run_path = resolved_repo_root / run_dir(run_id)
    verified_files: set[Path] = set()

    _require_directory(run_path)
    _require_directory(run_path / "stages")
    _require_file(run_path / ".lock", verified_files)
    _require_file(run_path / "audit.jsonl", verified_files)
    _require_file(run_path / "run.md", verified_files)
    _require_file(run_path / "workflow_state.yaml", verified_files)

    run_markdown = (run_path / "run.md").read_text(encoding="utf-8")
    if run_id not in run_markdown:
        raise AssertionError(f"{run_path / 'run.md'} did not include run_id {run_id}")

    for stage_id in stage_ids:
        stage_path = run_path / "stages" / stage_id
        _require_directory(stage_path)
        _require_directory(stage_path / "decisions")
        _require_directory(stage_path / "findings")
        _require_file(stage_path / ".complete", verified_files)
        _require_file(stage_path / "stage.md", verified_files)
        _require_file(stage_path / "packet.md", verified_files)
        _require_file(stage_path / "transcript.jsonl", verified_files)
        _require_file(stage_path / "evidence.md", verified_files)
        _require_file(stage_path / "evidence.json", verified_files)

        stage_markdown = (stage_path / "stage.md").read_text(encoding="utf-8")
        if stage_id not in stage_markdown:
            raise AssertionError(f"{stage_path / 'stage.md'} did not include stage_id {stage_id}")

        evidence_root = stage_path / ".evidence"
        _require_directory(evidence_root)
        current_link = evidence_root / "current"
        if not current_link.is_symlink():
            raise AssertionError(f"expected symlink at {current_link}")

        versions_dir = evidence_root / "versions"
        _require_directory(versions_dir)
        version_dirs = sorted(path for path in versions_dir.iterdir() if path.is_dir())
        if len(version_dirs) != 1:
            raise AssertionError(
                f"expected exactly one published evidence version for {stage_id}, "
                f"found {len(version_dirs)}"
            )

        version_dir = version_dirs[0]
        _require_file(version_dir / "evidence.md", verified_files)
        _require_file(version_dir / "evidence.json", verified_files)

    return sorted(str(path.relative_to(resolved_repo_root)) for path in verified_files)


def _require_directory(path: Path) -> None:
    if not path.is_dir():
        raise AssertionError(f"expected directory at {path}")


def _require_file(path: Path, verified_files: set[Path]) -> None:
    if not path.is_file():
        raise AssertionError(f"expected file at {path}")
    verified_files.add(path)
