from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import spanweave.evidence.generator as evidence_generator
from spanweave.evidence import (
    CommandOutput,
    EvidencePack,
    Finding,
    Severity,
    Verdict,
    generate,
)


@pytest.fixture
def evidence_pack(fixed_ulid_values: list[str]) -> EvidencePack:
    return EvidencePack(
        verdict=Verdict.REJECTED,
        confidence=0.82,
        findings=[
            Finding(
                finding_id="finding-auth",
                severity=Severity.RED,
                description="Authentication flow breaks on invalid session reuse.",
                file="spanweave/workflow/stages.py",
                line=42,
                verification="Observed a failing pytest assertion in the review stage fixture.",
            ),
            Finding(
                finding_id="finding-audit",
                severity=Severity.ORANGE,
                description="Audit trace is missing a reference to the retry decision.",
                file="spanweave/audit/log.py",
                line=17,
                verification="Compared the emitted audit chain against the expected decision IDs.",
            ),
            Finding(
                finding_id="finding-copy",
                severity=Severity.YELLOW,
                description=(
                    "Evidence header wording is inconsistent with the rest of the run artifacts."
                ),
                file="spanweave/evidence/templates/evidence.md.j2",
                line=1,
                verification=(
                    "Read the rendered markdown and compared it to the packet header style."
                ),
            ),
        ],
        execution=[
            CommandOutput(
                command="uv run pytest tests/test_evidence.py -v",
                stdout=(
                    "============================= test session starts "
                    "=============================\n"
                    "FAILED tests/test_evidence.py::test_generate_writes_both_files_and_round_trips"
                ),
                stderr="AssertionError: expected evidence file pair",
                exit_code=1,
                finding_ids=["finding-auth", "finding-audit"],
            ),
            CommandOutput(
                command="uv run ruff check spanweave/evidence tests/test_evidence.py",
                stdout="All checks passed!",
                stderr="",
                exit_code=0,
                finding_ids=["finding-copy"],
            ),
        ],
        audit_chain=[fixed_ulid_values[1], fixed_ulid_values[2]],
        timestamp=datetime(2026, 4, 20, 12, 34, 56, tzinfo=UTC),
        reviewer_persona_id="reviewer.default",
    )


def test_generate_writes_both_files_and_round_trips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    evidence_pack: EvidencePack,
) -> None:
    monkeypatch.chdir(tmp_path)

    json_path, md_path = generate(fixed_run_id, "001-review", evidence_pack)

    assert (
        json_path
        == Path(".spanweave") / "runs" / fixed_run_id / "stages" / "001-review" / "evidence.json"
    )
    assert (
        md_path
        == Path(".spanweave") / "runs" / fixed_run_id / "stages" / "001-review" / "evidence.md"
    )
    assert json_path.is_file()
    assert md_path.is_file()

    loaded = EvidencePack.model_validate_json(json_path.read_text(encoding="utf-8"))

    assert loaded == evidence_pack


def test_generate_updates_public_artifacts_via_current_pointer_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    evidence_pack: EvidencePack,
) -> None:
    monkeypatch.chdir(tmp_path)
    json_path, md_path = generate(fixed_run_id, "001-review", evidence_pack)
    updated_pack = evidence_pack.model_copy(update={"confidence": 0.91})
    replace_destinations: list[Path] = []
    original_replace = evidence_generator.os.replace

    def track_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        replace_destinations.append(Path(dst))
        original_replace(src, dst)

    monkeypatch.setattr(evidence_generator.os, "replace", track_replace)

    generate(fixed_run_id, "001-review", updated_pack)
    current_pointer = (
        Path(".spanweave")
        / "runs"
        / fixed_run_id
        / "stages"
        / "001-review"
        / ".evidence"
        / "current"
    )

    assert json_path.is_symlink()
    assert md_path.is_symlink()
    assert json_path.read_text(encoding="utf-8") == updated_pack.model_dump_json(indent=2) + "\n"
    assert json_path.name not in {path.name for path in replace_destinations}
    assert md_path.name not in {path.name for path in replace_destinations}
    assert current_pointer in replace_destinations


def test_generate_renders_expected_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    evidence_pack: EvidencePack,
) -> None:
    monkeypatch.chdir(tmp_path)

    _, md_path = generate(fixed_run_id, "001-review", evidence_pack)
    golden_path = Path(__file__).parent / "golden" / "evidence.md"

    assert md_path.read_text(encoding="utf-8") == golden_path.read_text(encoding="utf-8")


def test_generate_escapes_markdown_sensitive_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    pack = EvidencePack(
        verdict=Verdict.REJECTED,
        confidence=0.66,
        findings=[
            Finding(
                finding_id="finding```fence",
                severity=Severity.RED,
                description="<b>escaped</b> [link](https://example.test)",
                file="docs/`weird`.md",
                line=9,
                verification="Line one\n# fake heading",
            )
        ],
        execution=[
            CommandOutput(
                command="printf '```'",
                stdout="before\n```\n# fake heading",
                stderr="<script>alert(1)</script>",
                exit_code=1,
                finding_ids=["finding```fence"],
            )
        ],
        audit_chain=[fixed_ulid_values[4]],
        timestamp=datetime(2026, 4, 20, 12, 36, 0, tzinfo=UTC),
        reviewer_persona_id="reviewer.default",
    )

    _, md_path = generate(fixed_run_id, "003-markdown", pack)
    markdown_text = md_path.read_text(encoding="utf-8")

    assert "&lt;b&gt;escaped&lt;/b&gt;" in markdown_text
    assert r"\[link\]\(https://example.test\)" in markdown_text
    assert "\n````text\nbefore\n```\n# fake heading\n````\n" in markdown_text
    assert "<script>alert(1)</script>" in markdown_text
    assert "\n# fake heading\n\n## Audit Chain" not in markdown_text
    assert "Line one<br>\n\\# fake heading" in markdown_text


def test_generate_redacts_execution_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    pack = EvidencePack(
        verdict=Verdict.NEEDS_REVISION,
        confidence=0.55,
        findings=[
            Finding(
                finding_id="finding-secrets",
                severity=Severity.RED,
                description="Execution output leaked credentials.",
                file="spanweave/evidence/generator.py",
                line=88,
                verification="Injected known secret-shaped values into command output.",
            )
        ],
        execution=[
            CommandOutput(
                command="env",
                stdout="OPENAI_API_KEY=sk-abc12345secret\nTOKEN=ghp_secret_token_value",
                stderr="Authorization: Bearer xoxb-12345678-secret-token",
                exit_code=0,
                finding_ids=["finding-secrets"],
            )
        ],
        audit_chain=[fixed_ulid_values[3]],
        timestamp=datetime(2026, 4, 20, 12, 35, 0, tzinfo=UTC),
        reviewer_persona_id="reviewer.default",
    )

    json_path, md_path = generate(fixed_run_id, "002-redaction", pack)

    json_text = json_path.read_text(encoding="utf-8")
    markdown_text = md_path.read_text(encoding="utf-8")

    assert "sk-abc12345secret" not in json_text
    assert "ghp_secret_token_value" not in json_text
    assert "xoxb-12345678-secret-token" not in json_text
    assert "sk-abc12345secret" not in markdown_text
    assert "ghp_secret_token_value" not in markdown_text
    assert "xoxb-12345678-secret-token" not in markdown_text
    assert "OPENAI_API_KEY=[REDACTED:OPENAI_API_KEY]" in json_text
    assert "TOKEN=[REDACTED:TOKEN]" in json_text
    assert "Bearer [REDACTED:BEARER_TOKEN]" in json_text
    assert "OPENAI_API_KEY=[REDACTED:OPENAI_API_KEY]" in markdown_text
    assert "TOKEN=[REDACTED:TOKEN]" in markdown_text
    assert "Bearer [REDACTED:BEARER_TOKEN]" in markdown_text


def test_generate_keeps_previous_evidence_when_current_pointer_swap_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    evidence_pack: EvidencePack,
) -> None:
    monkeypatch.chdir(tmp_path)
    json_path, md_path = generate(fixed_run_id, "001-review", evidence_pack)
    original_json = json_path.read_text(encoding="utf-8")
    original_markdown = md_path.read_text(encoding="utf-8")
    updated_pack = evidence_pack.model_copy(update={"confidence": 0.91})

    original_replace = evidence_generator.os.replace

    def fail_on_current_swap(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        destination = Path(dst)
        if destination.name == "current":
            raise RuntimeError("boom")
        original_replace(src, dst)

    monkeypatch.setattr(evidence_generator.os, "replace", fail_on_current_swap)

    with pytest.raises(RuntimeError, match="boom"):
        generate(fixed_run_id, "001-review", updated_pack)

    stage_dir = tmp_path / ".spanweave" / "runs" / fixed_run_id / "stages" / "001-review"
    assert json_path.read_text(encoding="utf-8") == original_json
    assert md_path.read_text(encoding="utf-8") == original_markdown
    assert json_path.is_symlink()
    assert md_path.is_symlink()
    assert (stage_dir / ".evidence" / "current").is_symlink()
