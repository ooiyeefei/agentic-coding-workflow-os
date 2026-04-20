from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from ulid import ULID

from atelier.evidence import CommandOutput, EvidencePack, Finding, Severity, Verdict
from atelier.security import redact

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_APP_PATH = "demo/app"
DEFAULT_TIMEOUT_SECONDS = 300.0
DEFAULT_UAT_SKILL_PATH = Path("/home/fei/fei/code/hackathon/ccc/skills/uat-testing")
DEFAULT_ENV_FILE = (_REPO_ROOT / "../../.env.local").resolve()

_SUMMARY_PATTERN = re.compile(r"UAT:\s*(?P<passed>\d+)\s*/\s*(?P<total>\d+)\s*passed", re.I)
_STATUS_PATTERN = re.compile(
    r"^(?:[-*]\s*)?(?:\[(?P<bracket_status>[A-Z]+)\]|(?P<status>[A-Z]+))\s*[:\-]\s*(?P<body>.+)$",
    re.IGNORECASE,
)

SubprocessRunner = Callable[..., subprocess.CompletedProcess[str]]


class UATExecutionError(RuntimeError):
    """Raised when UAT execution cannot be completed safely."""


class UATTimeoutError(UATExecutionError):
    """Raised when the external UAT subprocess exceeds the configured timeout."""


class TestAccountCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class UATRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_path: str = DEFAULT_APP_PATH
    test_user: str | None = None
    test_password: str | None = None
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0)
    skill_path: str | None = None
    notes: str | None = None


def run_uat(
    request: UATRequest,
    *,
    test_plan: str | None = None,
    subprocess_runner: SubprocessRunner = subprocess.run,
) -> EvidencePack:
    command = build_uat_command(request.skill_path, request.app_path)
    credentials = resolve_test_account_credentials(request)
    env = os.environ.copy()
    env["TEST_USER"] = credentials.username
    env["TEST_PASSWORD"] = credentials.password
    env["ATELIER_UAT_APP_PATH"] = str(Path(request.app_path).resolve())
    if test_plan:
        env["ATELIER_UAT_TEST_PLAN"] = test_plan
    if request.notes:
        env["ATELIER_UAT_NOTES"] = request.notes

    try:
        completed = subprocess_runner(
            command,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(_REPO_ROOT),
            timeout=request.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise UATTimeoutError(
            "UAT subprocess timed out after "
            f"{request.timeout_seconds:g}s: {render_command(command)}"
        ) from exc
    except OSError as exc:
        raise UATExecutionError(
            f"Failed to invoke UAT subprocess {render_command(command)}: {exc}"
        ) from exc

    return build_evidence_pack(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        secrets=[credentials.username, credentials.password],
    )


def build_uat_command(skill_path: str | None, app_path: str) -> list[str]:
    resolved_skill_path = resolve_skill_path(skill_path)
    entrypoint = resolve_skill_entrypoint(resolved_skill_path)
    return [*entrypoint, str(Path(app_path).resolve())]


def resolve_skill_path(skill_path: str | None = None) -> Path:
    candidate = (
        skill_path
        or os.getenv("ATELIER_UAT_SKILL_PATH")
        or str(DEFAULT_UAT_SKILL_PATH)
    )
    path = Path(candidate).expanduser()
    if not path.exists():
        raise UATExecutionError(
            "Configured UAT skill path does not exist: "
            f"{path}. Set ATELIER_UAT_SKILL_PATH to a valid executable or skill directory."
        )
    return path


def resolve_skill_entrypoint(path: Path) -> list[str]:
    if path.is_file():
        return _file_command(path)

    if not path.is_dir():
        raise UATExecutionError(f"Configured UAT skill path is not invokable: {path}")

    for candidate in (
        path / "run.sh",
        path / "run",
        path / "uat-testing",
        path / "bin" / "uat-testing",
        path / "main.py",
    ):
        if candidate.is_file():
            return _file_command(candidate)

    raise UATExecutionError(
        "Configured UAT skill path is a directory but no supported entrypoint was found: "
        f"{path}. Expected one of run.sh, run, uat-testing, bin/uat-testing, or main.py."
    )


def _file_command(path: Path) -> list[str]:
    if path.suffix == ".py":
        return [sys.executable, str(path)]
    if path.suffix == ".sh":
        return ["bash", str(path)]
    if os.access(path, os.X_OK):
        return [str(path)]
    raise UATExecutionError(
        f"Configured UAT skill entrypoint is not executable: {path}. "
        "Provide an executable file, a .py script, or a .sh script."
    )


def resolve_test_account_credentials(
    request: UATRequest,
    *,
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = None,
) -> TestAccountCredentials:
    values = dict(environ or os.environ)
    file_values = load_env_file(env_file or DEFAULT_ENV_FILE)

    username = request.test_user or values.get("TEST_USER") or file_values.get("TEST_USER")
    password = (
        request.test_password or values.get("TEST_PASSWORD") or file_values.get("TEST_PASSWORD")
    )
    if not username or not password:
        raise UATExecutionError(
            "Unable to resolve TEST_USER and TEST_PASSWORD for UAT. "
            "Provide them in the context packet, environment, or ../../.env.local."
        )

    return TestAccountCredentials(username=username, password=password)


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def build_evidence_pack(
    *,
    command: list[str],
    exit_code: int,
    stdout: str,
    stderr: str,
    secrets: list[str] | None = None,
) -> EvidencePack:
    summary, findings = parse_uat_report(stdout, stderr)
    redacted_stdout = redact(stdout, secrets=secrets)
    redacted_stderr = redact(stderr, secrets=secrets)
    redacted_summary = redact(summary, secrets=secrets)
    redacted_findings = [
        Finding(
            finding_id=finding.finding_id,
            severity=finding.severity,
            description=redact(finding.description, secrets=secrets),
            verification=redact(finding.verification, secrets=secrets),
            file=finding.file,
            line=finding.line,
        )
        for finding in findings
    ]

    if exit_code != 0 and not redacted_findings:
        verification = redacted_stderr or redacted_stdout or f"exit_code={exit_code}"
        redacted_findings.append(
            Finding(
                finding_id=_finding_id(len(redacted_findings) + 1),
                severity=Severity.RED,
                description=f"UAT subprocess exited with code {exit_code}",
                file="uat-report",
                verification=verification,
            )
        )

    verdict = derive_verdict(redacted_findings, exit_code)
    if not redacted_summary:
        if redacted_findings:
            redacted_summary = f"UAT completed with {len(redacted_findings)} finding(s)"
        elif exit_code == 0:
            redacted_summary = "UAT completed successfully"
        else:
            redacted_summary = f"UAT failed with exit code {exit_code}"

    return EvidencePack(
        verdict=verdict,
        confidence=1.0,
        summary=redacted_summary,
        findings=redacted_findings,
        execution=[
            CommandOutput(
                command=render_command(command),
                stdout=redacted_stdout,
                stderr=redacted_stderr,
                exit_code=exit_code,
                finding_ids=[finding.finding_id for finding in redacted_findings],
            )
        ],
        audit_chain=[str(ULID())],
        timestamp=datetime.now(UTC),
        reviewer_persona_id="uat",
    )


def parse_uat_report(stdout: str, stderr: str) -> tuple[str, list[Finding]]:
    stdout_text = stdout.strip()
    stderr_text = stderr.strip()
    if not stdout_text and not stderr_text:
        return "", []

    summary_parts: list[str] = []
    findings: list[Finding] = []
    text_reports: list[str] = []

    for report_text in (stdout_text, stderr_text):
        if not report_text:
            continue

        json_result = _parse_json_report(report_text)
        if json_result is None:
            text_reports.append(report_text)
            continue

        summary, stream_findings = json_result
        if summary:
            summary_parts.append(summary)
        findings.extend(stream_findings)

    if text_reports:
        text_summary, text_findings = _parse_text_report("\n".join(text_reports))
        if text_summary:
            summary_parts.append(text_summary)
        findings.extend(text_findings)

    return _merge_report_parts(summary_parts, findings)


def _merge_report_parts(
    summary_parts: list[str],
    findings: list[Finding],
) -> tuple[str, list[Finding]]:
    unique_summaries: list[str] = []
    for summary in summary_parts:
        if summary and summary not in unique_summaries:
            unique_summaries.append(summary)

    if not unique_summaries:
        return "", findings
    if len(unique_summaries) == 1:
        return unique_summaries[0], findings
    return " | ".join(unique_summaries), findings


def _parse_json_report(report_text: str) -> tuple[str, list[Finding]] | None:
    try:
        payload = json.loads(report_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    summary = str(payload.get("summary") or "")
    findings_payload = payload.get("findings", [])
    findings = _parse_json_findings(findings_payload)
    if not summary and findings:
        summary = f"UAT completed with {len(findings)} finding(s)"
    return summary, findings


def _parse_json_findings(payload: Any) -> list[Finding]:
    if not isinstance(payload, list):
        return []

    findings: list[Finding] = []
    for item in payload:
        if isinstance(item, str):
            findings.append(
                _build_finding(
                    index=len(findings) + 1,
                    severity=Severity.RED,
                    description=item,
                    verification="Parsed from JSON findings",
                )
            )
            continue
        if not isinstance(item, dict):
            continue

        severity = normalize_severity(item.get("severity") or item.get("status"))
        description = str(item.get("description") or item.get("title") or "").strip()
        if not severity or not description:
            continue

        line_value = item.get("line")
        findings.append(
            _build_finding(
                index=len(findings) + 1,
                severity=severity,
                description=description,
                verification=str(item.get("verification") or item.get("details") or "").strip(),
                file=str(item.get("file")).strip() if item.get("file") else "uat-report",
                line=line_value if isinstance(line_value, int) else None,
            )
        )
    return findings


def _parse_text_report(report_text: str) -> tuple[str, list[Finding]]:
    summary = ""
    findings: list[Finding] = []
    pass_count = 0
    total_count = 0

    for line in report_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        summary_match = _SUMMARY_PATTERN.search(stripped)
        if summary_match:
            pass_count = int(summary_match.group("passed"))
            total_count = int(summary_match.group("total"))
            summary = f"UAT: {pass_count}/{total_count} passed"
            continue

        status_match = _STATUS_PATTERN.match(stripped)
        if not status_match:
            continue

        status = (
            status_match.group("bracket_status") or status_match.group("status") or ""
        ).upper()
        body = status_match.group("body").strip()
        normalized = normalize_severity(status)
        if status == "PASS":
            pass_count += 1
            total_count += 1
            continue
        if normalized is None:
            continue
        total_count += 1
        findings.append(
            _build_finding(
                index=len(findings) + 1,
                severity=normalized,
                description=body,
                verification=stripped,
            )
        )

    if not summary and total_count:
        summary = f"UAT: {pass_count}/{total_count} passed"
    return summary, findings


def normalize_severity(value: Any) -> Severity | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip().upper()
    severity_map = {
        "ERROR": Severity.RED,
        "FAIL": Severity.RED,
        "FAILED": Severity.RED,
        "RED": Severity.RED,
        "WARN": Severity.YELLOW,
        "WARNING": Severity.YELLOW,
        "YELLOW": Severity.YELLOW,
        "ORANGE": Severity.ORANGE,
    }
    return severity_map.get(normalized)


def derive_verdict(findings: list[Finding], exit_code: int) -> Verdict:
    severities = {finding.severity for finding in findings}
    if exit_code != 0 or Severity.RED in severities:
        return Verdict.REJECTED
    if severities & {Severity.ORANGE, Severity.YELLOW}:
        return Verdict.NEEDS_REVISION
    return Verdict.APPROVED


def _finding_id(index: int) -> str:
    return f"uat-finding-{index:03d}"


def _build_finding(
    *,
    index: int,
    severity: Severity,
    description: str,
    verification: str,
    file: str | None = None,
    line: int | None = None,
) -> Finding:
    return Finding(
        finding_id=_finding_id(index),
        severity=severity,
        description=description,
        file=file or "uat-report",
        line=line,
        verification=verification or description,
    )


def render_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)
