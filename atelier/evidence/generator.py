from __future__ import annotations

import html
import os
import re
import shutil
import tempfile
from contextlib import suppress
from datetime import UTC
from pathlib import Path
from typing import Annotated

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from atelier.util import new_evidence_id, run_dir, safe_mkdir

from .schema import EvidencePack, Severity

_STAGE_ID = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
_MARKDOWN_SPECIAL_CHARS = re.compile(r"([\\`*_{}\[\]()#+|>])")
_BACKTICK_RUN_PATTERN = re.compile(r"`+")
_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).with_name("templates")),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
_SEVERITY_ORDER = [Severity.RED, Severity.ORANGE, Severity.YELLOW]
_EVIDENCE_ROOT_NAME = ".evidence"
_VERSIONS_DIR_NAME = "versions"
_CURRENT_LINK_NAME = "current"
_PUBLIC_ARTIFACTS = ("evidence.json", "evidence.md")
_ENV_ASSIGNMENT_PATTERN = re.compile(r"\b([A-Z][A-Z0-9_]*)\s*=\s*([^\s]+)")
_SECRET_NAME_MARKERS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD")
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._-]+")
_PREFIX_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9]{8,}"), "OPENAI_KEY"),
    (re.compile(r"pk_[A-Za-z0-9]{8,}"), "PUBLISHABLE_KEY"),
    (re.compile(r"ghp_[A-Za-z0-9]{8,}"), "GITHUB_TOKEN"),
    (re.compile(r"xoxb-[A-Za-z0-9-]{8,}"), "SLACK_TOKEN"),
]


class _GeneratorInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    stage_id: _STAGE_ID

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return str(run_dir(value).name)


def _markdown_text(value: object) -> str:
    text = _normalize_text(value)
    text = html.escape(text, quote=False)
    text = _MARKDOWN_SPECIAL_CHARS.sub(r"\\\1", text)
    return text.replace("\n", "<br>\n")


def _markdown_inline_code(value: object) -> str:
    text = _normalize_text(value).replace("\n", " ")
    fence = _inline_code_fence(text)
    if text.startswith("`") or text.endswith("`"):
        text = f" {text} "
    return f"{fence}{text}{fence}"


def _markdown_code_block(value: object, language: str = "text") -> str:
    text = _normalize_text(value)
    fence = "`" * max(3, _max_backtick_run(text) + 1)
    return f"{fence}{language}\n{text}\n{fence}"


def _normalize_text(value: object) -> str:
    return str(value).replace("\r\n", "\n").replace("\r", "\n")


def _inline_code_fence(text: str) -> str:
    return "`" * (_max_backtick_run(text) + 1 or 1)


def _max_backtick_run(text: str) -> int:
    return max((len(match.group(0)) for match in _BACKTICK_RUN_PATTERN.finditer(text)), default=0)


_TEMPLATE_ENV.filters["md_text"] = _markdown_text
_TEMPLATE_ENV.filters["md_inline_code"] = _markdown_inline_code
_TEMPLATE_ENV.filters["md_code_block"] = _markdown_code_block


def generate(run_id: str, stage_id: str, pack: EvidencePack) -> tuple[Path, Path]:
    params = _GeneratorInput(run_id=run_id, stage_id=stage_id)
    stage_path = run_dir(params.run_id) / "stages" / params.stage_id
    json_path = stage_path / "evidence.json"
    md_path = stage_path / "evidence.md"

    rendered_pack = _redact_pack(pack)
    json_payload = rendered_pack.model_dump_json(indent=2) + "\n"
    markdown_payload = _render_markdown(params.run_id, params.stage_id, rendered_pack)

    _publish_evidence_version(
        stage_path,
        {
            "evidence.json": json_payload,
            "evidence.md": markdown_payload,
        },
    )
    return json_path, md_path


def _render_markdown(run_id: str, stage_id: str, pack: EvidencePack) -> str:
    template = _TEMPLATE_ENV.get_template("evidence.md.j2")
    grouped_findings = {
        severity.value: [finding for finding in pack.findings if finding.severity == severity]
        for severity in _SEVERITY_ORDER
    }
    rendered = template.render(
        run_id=run_id,
        stage_id=stage_id,
        pack=pack,
        grouped_findings=grouped_findings,
        severity_order=[severity.value for severity in _SEVERITY_ORDER],
        timestamp_text=pack.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        confidence_percent=f"{pack.confidence:.0%}",
    )
    return rendered if rendered.endswith("\n") else f"{rendered}\n"


def _redact_pack(pack: EvidencePack) -> EvidencePack:
    redacted_execution = [
        command_output.model_copy(
            update={
                "stdout": _redact_text(command_output.stdout),
                "stderr": _redact_text(command_output.stderr),
            }
        )
        for command_output in pack.execution
    ]
    return pack.model_copy(update={"execution": redacted_execution})


def _redact_text(value: str) -> str:
    redacted = _ENV_ASSIGNMENT_PATTERN.sub(_redact_env_assignment, value)
    redacted = _BEARER_PATTERN.sub("Bearer [REDACTED:BEARER_TOKEN]", redacted)
    for pattern, label in _PREFIX_PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{label}]", redacted)
    return redacted


def _redact_env_assignment(match: re.Match[str]) -> str:
    variable_name = match.group(1)
    if not any(marker in variable_name for marker in _SECRET_NAME_MARKERS):
        return match.group(0)
    return f"{variable_name}=[REDACTED:{variable_name}]"


def _publish_evidence_version(stage_path: Path, outputs: dict[str, str]) -> None:
    if not outputs:
        return

    evidence_root = stage_path / _EVIDENCE_ROOT_NAME
    versions_dir = evidence_root / _VERSIONS_DIR_NAME
    version_name = new_evidence_id()
    temp_version_dir = versions_dir / f".{version_name}.tmp"
    version_dir = versions_dir / version_name
    current_link = evidence_root / _CURRENT_LINK_NAME
    temp_current_link: Path | None = None
    previous_version_dir: Path | None = None

    safe_mkdir(versions_dir)
    try:
        safe_mkdir(temp_version_dir)
        for file_name, content in outputs.items():
            _write_new_text(temp_version_dir / file_name, content)
        os.replace(temp_version_dir, version_dir)

        _ensure_public_links(stage_path)
        previous_version_dir = _read_current_version_dir(current_link, versions_dir)
        temp_current_link = _write_temp_symlink(
            evidence_root,
            prefix=f".{_CURRENT_LINK_NAME}.",
            suffix=".tmp",
            target=(Path(_VERSIONS_DIR_NAME) / version_name).as_posix(),
            target_is_directory=True,
        )
        os.replace(temp_current_link, current_link)
    except Exception:
        if temp_current_link is not None:
            with suppress(FileNotFoundError):
                temp_current_link.unlink()
        shutil.rmtree(temp_version_dir, ignore_errors=True)
        shutil.rmtree(version_dir, ignore_errors=True)
        raise
    else:
        if previous_version_dir is not None and previous_version_dir != version_dir:
            shutil.rmtree(previous_version_dir, ignore_errors=True)


def _ensure_public_links(stage_path: Path) -> None:
    temp_links: dict[Path, Path] = {}
    backup_paths: dict[Path, Path | None] = {}
    installed_paths: set[Path] = set()
    links_to_update: list[Path] = []

    for file_name in _PUBLIC_ARTIFACTS:
        public_path = stage_path / file_name
        expected_target = f"{_EVIDENCE_ROOT_NAME}/{_CURRENT_LINK_NAME}/{file_name}"
        if public_path.is_symlink() and os.readlink(public_path) == expected_target:
            continue
        links_to_update.append(public_path)
        temp_links[public_path] = _write_temp_symlink(
            stage_path,
            prefix=f".{file_name}.",
            suffix=".tmp",
            target=expected_target,
            target_is_directory=False,
        )

    try:
        for public_path in links_to_update:
            if _path_exists_or_is_link(public_path):
                backup_path = _reserve_path(
                    public_path.parent,
                    prefix=f".{public_path.name}.",
                    suffix=".bak",
                )
                os.replace(public_path, backup_path)
                backup_paths[public_path] = backup_path
            else:
                backup_paths[public_path] = None

            os.replace(temp_links[public_path], public_path)
            installed_paths.add(public_path)

        for backup_path in backup_paths.values():
            if backup_path is not None:
                with suppress(FileNotFoundError):
                    backup_path.unlink()
    except Exception:
        for public_path in reversed(links_to_update):
            backup_path = backup_paths.get(public_path)
            if public_path in installed_paths:
                if backup_path is not None and backup_path.exists():
                    with suppress(FileNotFoundError):
                        os.replace(backup_path, public_path)
                else:
                    with suppress(FileNotFoundError):
                        public_path.unlink()
            elif backup_path is not None and backup_path.exists():
                with suppress(FileNotFoundError):
                    os.replace(backup_path, public_path)

        for temp_link in temp_links.values():
            with suppress(FileNotFoundError):
                temp_link.unlink()
        raise


def _read_current_version_dir(current_link: Path, versions_dir: Path) -> Path | None:
    if not current_link.is_symlink():
        return None

    target = current_link.resolve(strict=False)
    resolved_versions_dir = versions_dir.resolve()
    try:
        target.relative_to(resolved_versions_dir)
    except ValueError:
        raise ValueError(f"current evidence link points outside {versions_dir}") from None

    return target if target.exists() else None


def _write_new_text(destination: Path, content: str) -> Path:
    safe_mkdir(destination.parent)
    with destination.open("w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    return destination


def _reserve_path(directory: Path, *, prefix: str, suffix: str) -> Path:
    safe_mkdir(directory)
    fd, temp_name = tempfile.mkstemp(dir=directory, prefix=prefix, suffix=suffix)
    os.close(fd)
    reserved_path = Path(temp_name)
    reserved_path.unlink()
    return reserved_path


def _write_temp_symlink(
    directory: Path,
    *,
    prefix: str,
    suffix: str,
    target: str,
    target_is_directory: bool,
) -> Path:
    reserved_path = _reserve_path(directory, prefix=prefix, suffix=suffix)
    os.symlink(target, reserved_path, target_is_directory=target_is_directory)
    return reserved_path


def _path_exists_or_is_link(path: Path) -> bool:
    return path.exists() or path.is_symlink()


__all__ = ["generate"]
