from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from atelier.cli.main import main
from atelier.learning import (
    APPEND_MARKER,
    FALLBACK_RULE,
    KNOWN_RULES_DIR,
    build_rule_block,
    derive_rule_from_outcome,
    load_rules,
    patch_skill_file,
    render_diff,
)
from atelier.learning.rule_loader import RuleLoadError, parse_rule_document
from click.testing import CliRunner


def _write_entry(tmp_path: Path, entry: dict[str, Any]) -> Path:
    path = tmp_path / "outcome.json"
    path.write_text(json.dumps(entry), encoding="utf-8")
    return path


def test_known_rules_dir_resolves_to_repo_root() -> None:
    assert KNOWN_RULES_DIR.is_dir(), f"bundled rules dir missing: {KNOWN_RULES_DIR}"
    yaml_files = sorted(path.name for path in KNOWN_RULES_DIR.glob("*.yaml"))
    assert yaml_files == [
        "api_contract_change.yaml",
        "missed_edge_case.yaml",
        "rate_limit_throttling.yaml",
        "root_cause_vs_symptom.yaml",
        "unverified_assumption.yaml",
    ]


def test_load_rules_returns_five_compiled_rules() -> None:
    rules = load_rules(KNOWN_RULES_DIR)

    assert len(rules) == 5
    rule_ids = sorted(rule.id for rule in rules)
    assert rule_ids == [
        "api_contract_change",
        "missed_edge_case",
        "rate_limit_throttling",
        "root_cause_vs_symptom",
        "unverified_assumption",
    ]
    for rule in rules:
        assert rule.error_types
        assert rule.message_patterns
        assert all(pattern.search("") is not None or True for pattern in rule.message_patterns)
        assert rule.rule_text.strip()
        assert rule.rationale.strip()


def test_load_rules_raises_for_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_rules(tmp_path / "does-not-exist")


def test_parse_rule_document_rejects_invalid_regex(tmp_path: Path) -> None:
    document = {
        "id": "broken",
        "error_types": ["x"],
        "message_patterns": ["[unterminated"],
        "rule_text": "rule",
        "rationale": "why",
    }
    with pytest.raises(RuleLoadError):
        parse_rule_document(document, tmp_path / "broken.yaml")


def test_parse_rule_document_requires_error_types(tmp_path: Path) -> None:
    document = {
        "id": "bad",
        "error_types": [],
        "message_patterns": ["foo"],
        "rule_text": "rule",
        "rationale": "why",
    }
    with pytest.raises(RuleLoadError):
        parse_rule_document(document, tmp_path / "bad.yaml")


def test_explicit_candidate_takes_precedence() -> None:
    candidate = "Always run the failing scenario explicitly before declaring success."
    entry: dict[str, Any] = {
        "error_type": "missed_bug",
        "error_message": "edge case missing",
        "learned_rule_candidate": candidate,
    }

    derived = derive_rule_from_outcome(entry)

    assert derived["rule_text"] == candidate
    assert derived["matched_pattern"] is None
    assert derived["fallback"] is False
    assert "explicit learned_rule_candidate" in derived["rationale"]


def test_short_explicit_candidate_is_ignored() -> None:
    entry: dict[str, Any] = {
        "error_type": "missed_bug",
        "error_message": "edge case missing",
        "learned_rule_candidate": "too short",
    }

    derived = derive_rule_from_outcome(entry)

    assert derived["matched_pattern"] == "missed_edge_case"


@pytest.mark.parametrize(
    ("error_type", "error_message", "expected_id"),
    [
        ("missed_bug", "did not test the empty input edge case", "missed_edge_case"),
        ("missed_bug", "rate-limit handling regressed at 429 boundary", "rate_limit_throttling"),
        ("api_contract", "public api response shape changed silently", "api_contract_change"),
        ("insufficient_verification", "did not run the failing test", "unverified_assumption"),
        (
            "root_cause_missed",
            "wrong fix that only patches the symptom only",
            "root_cause_vs_symptom",
        ),
    ],
)
def test_derive_rule_matches_each_known_pattern(
    error_type: str,
    error_message: str,
    expected_id: str,
) -> None:
    entry: dict[str, Any] = {
        "error_type": error_type,
        "error_message": error_message,
    }

    derived = derive_rule_from_outcome(entry)

    assert derived["matched_pattern"] == expected_id
    assert derived["fallback"] is False
    assert derived["rule_text"].strip()
    assert derived["rationale"].strip()


def test_derive_rule_falls_back_when_no_pattern_matches() -> None:
    entry: dict[str, Any] = {
        "error_type": "novel_failure_kind",
        "error_message": "Something unexpected happened that no rule covers.",
    }

    derived = derive_rule_from_outcome(entry)

    assert derived["fallback"] is True
    assert derived["matched_pattern"] is None
    assert FALLBACK_RULE in derived["rule_text"]
    assert "Something unexpected" in derived["rule_text"]


def test_derive_rule_falls_back_with_only_error_type() -> None:
    entry: dict[str, Any] = {"error_type": "novel"}

    derived = derive_rule_from_outcome(entry)

    assert derived["fallback"] is True
    assert derived["matched_pattern"] is None
    assert derived["rule_text"] == FALLBACK_RULE


def test_derive_rule_rejects_empty_entry() -> None:
    with pytest.raises(ValueError):
        derive_rule_from_outcome({})


def test_derive_rule_honors_custom_rules_dir(tmp_path: Path) -> None:
    custom_dir = tmp_path / "rules"
    custom_dir.mkdir()
    (custom_dir / "only.yaml").write_text(
        "id: custom_only\n"
        "error_types: [special]\n"
        "message_patterns:\n"
        "  - 'special-token'\n"
        "rule_text: |\n"
        "  Always check for the special token before continuing.\n"
        "rationale: |\n"
        "  Custom rule for tests.\n",
        encoding="utf-8",
    )
    entry: dict[str, Any] = {
        "error_type": "special",
        "error_message": "missing special-token in payload",
    }

    derived = derive_rule_from_outcome(entry, rules_dir=custom_dir)

    assert derived["matched_pattern"] == "custom_only"
    assert "special token" in derived["rule_text"]


def test_patch_skill_file_appends_block_when_marker_absent() -> None:
    original = "# Skill\n\nIntro text.\n"
    rule_block = build_rule_block(
        "Always state the missed check.",
        {"run_id": "run_01ARZ3NDEKTSV4RRFFQ69G5FAV", "error_type": "missed_bug"},
    )

    patched = patch_skill_file(original, rule_block)

    assert APPEND_MARKER in patched
    assert "## Learned Rules" in patched
    assert "Always state the missed check." in patched
    assert "run_id=run_01ARZ3NDEKTSV4RRFFQ69G5FAV" in patched


def test_patch_skill_file_is_idempotent() -> None:
    original = "# Skill\n\nIntro text.\n"
    rule_block = build_rule_block("Always state the missed check.", {})

    once = patch_skill_file(original, rule_block)
    twice = patch_skill_file(once, rule_block)

    assert once == twice


def test_render_diff_returns_unified_diff(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    original = "# Skill\n\nIntro.\n"
    rule_block = build_rule_block("Add the missing check.", {})
    updated = patch_skill_file(original, rule_block)

    diff = render_diff(original, updated, skill_path)

    assert diff
    assert "+## Learned Rules" in diff
    assert "Add the missing check." in diff


def test_diff_only_does_not_write(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    original_text = "# Skill\n\nIntro.\n"
    skill_path.write_text(original_text, encoding="utf-8")
    entry_path = _write_entry(
        tmp_path,
        {"error_type": "missed_bug", "error_message": "did not test edge case"},
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "skill_feedback",
            "derive",
            "--entry",
            str(entry_path),
            "--skill-file",
            str(skill_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Patch preview" in result.output
    assert "Dry run only" in result.output
    assert skill_path.read_text(encoding="utf-8") == original_text


def test_apply_writes_skill_file(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("# Skill\n\nIntro.\n", encoding="utf-8")
    entry_path = _write_entry(
        tmp_path,
        {
            "run_id": "run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "error_type": "missed_bug",
            "error_message": "did not test edge case",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "skill_feedback",
            "derive",
            "--entry",
            str(entry_path),
            "--skill-file",
            str(skill_path),
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Applied patch" in result.output
    contents = skill_path.read_text(encoding="utf-8")
    assert APPEND_MARKER in contents
    assert "## Learned Rules" in contents


def test_cli_smoke_derive_emits_expected_output(tmp_path: Path) -> None:
    entry_path = _write_entry(
        tmp_path,
        {
            "error_type": "missed_bug",
            "error_message": "did not test the empty input edge case",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["skill_feedback", "derive", "--entry", str(entry_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Derived rule:" in result.output
    assert "Matched pattern: missed_edge_case" in result.output
    assert "Fallback: no" in result.output


def test_cli_smoke_derive_json(tmp_path: Path) -> None:
    entry_path = _write_entry(
        tmp_path,
        {
            "error_type": "api_contract",
            "error_message": "public api response shape changed",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["skill_feedback", "derive", "--entry", str(entry_path), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["matched_pattern"] == "api_contract_change"
    assert payload["fallback"] is False
    assert payload["rule_text"]


def test_cli_list_rules_text(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["skill_feedback", "list-rules"])

    assert result.exit_code == 0, result.output
    assert "Loaded 5 rule(s)" in result.output
    assert "id: missed_edge_case" in result.output


def test_cli_list_rules_json() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["skill_feedback", "list-rules", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["rule_count"] == 5
    rule_ids = sorted(rule["id"] for rule in payload["rules"])
    assert rule_ids == [
        "api_contract_change",
        "missed_edge_case",
        "rate_limit_throttling",
        "root_cause_vs_symptom",
        "unverified_assumption",
    ]


def test_cli_list_rules_custom_dir(tmp_path: Path) -> None:
    custom_dir = tmp_path / "rules"
    custom_dir.mkdir()
    (custom_dir / "solo.yaml").write_text(
        "id: solo\n"
        "error_types: [s]\n"
        "message_patterns: ['x']\n"
        "rule_text: |\n"
        "  text\n"
        "rationale: |\n"
        "  why\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["skill_feedback", "list-rules", "--rules-dir", str(custom_dir), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["rule_count"] == 1
    assert payload["rules"][0]["id"] == "solo"
