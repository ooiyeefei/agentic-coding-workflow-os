"""CLI subcommands for the skill feedback loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from atelier.cli.formatters import build_help_epilog, echo_json
from atelier.learning import (
    KNOWN_RULES_DIR,
    build_rule_block,
    derive_rule_from_outcome,
    load_rules,
    patch_skill_file,
    read_entry,
    render_diff,
)


@click.group(
    "skill_feedback",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Reads SkillOutcome JSON entries to derive one concrete SKILL.md rule.",
            "Rule library lives at .atelier/defaults/feedback_rules/*.yaml; override with "
            "--rules-dir.",
        ),
        examples=(
            "atelier skill_feedback derive --entry path/to/outcome.json",
            "atelier skill_feedback derive --entry outcome.json --skill-file SKILL.md --apply",
            "atelier skill_feedback list-rules --json",
        ),
    ),
)
def skill_feedback_group() -> None:
    """Inspect and apply skill feedback rules derived from past failures."""


@skill_feedback_group.command(
    "derive",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Default behavior is dry-run. Pass --apply to write the patch.",
            "Patch application is restricted to files named SKILL.md.",
        ),
        examples=(
            "atelier skill_feedback derive --entry outcome.json",
            "atelier skill_feedback derive --entry outcome.json --skill-file SKILL.md",
            "atelier skill_feedback derive --entry outcome.json --skill-file SKILL.md --apply",
            "atelier skill_feedback derive --entry outcome.json --json",
        ),
    ),
)
@click.option(
    "--entry",
    "entry_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a SkillOutcome JSON file.",
)
@click.option(
    "--skill-file",
    "skill_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Optional target SKILL.md to preview or patch.",
)
@click.option(
    "--rules-dir",
    "rules_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Override the YAML rule library directory.",
)
@click.option(
    "--apply",
    "apply_patch",
    is_flag=True,
    help="Write the derived rule into --skill-file. Without this flag the patch is preview only.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def derive_command(
    entry_path: Path,
    skill_file: Path | None,
    rules_dir: Path | None,
    apply_patch: bool,
    json_output: bool,
) -> None:
    """Derive one SKILL.md rule from a SkillOutcome JSON entry."""

    try:
        entry = read_entry(entry_path)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        derived = derive_rule_from_outcome(entry, rules_dir=rules_dir)
    except (FileNotFoundError, NotADirectoryError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    summary: dict[str, Any] = {
        "entry": str(entry_path.resolve()),
        "error_type": str(entry.get("error_type", "") or "").strip(),
        "error_message": str(entry.get("error_message", "") or "").strip(),
        "rule_text": derived["rule_text"],
        "rationale": derived["rationale"],
        "matched_pattern": derived["matched_pattern"],
        "fallback": derived["fallback"],
    }

    if skill_file is None:
        if json_output:
            echo_json(summary)
            return
        _emit_text_summary(summary)
        return

    if skill_file.name != "SKILL.md":
        raise click.ClickException("--skill-file must point to a file named SKILL.md.")
    if not skill_file.exists():
        raise click.ClickException(f"SKILL.md not found: {skill_file}")

    original = skill_file.read_text(encoding="utf-8")
    rule_block = build_rule_block(derived["rule_text"], entry)
    updated = patch_skill_file(original, rule_block)
    diff_text = render_diff(original, updated, skill_file)
    changed = bool(diff_text)
    applied = bool(apply_patch and changed)
    if applied:
        skill_file.write_text(updated, encoding="utf-8")

    summary["skill_file"] = str(skill_file.resolve())
    summary["diff"] = diff_text
    summary["changed"] = changed
    summary["applied"] = applied

    if json_output:
        echo_json(summary)
        return

    _emit_text_summary(summary)
    click.echo("\nPatch preview:")
    click.echo(diff_text if diff_text else "(no changes)")
    if not apply_patch:
        click.echo("\nDry run only. Re-run with --apply to write the patch.")
        return
    if applied:
        click.echo(f"\nApplied patch to {skill_file}")
    else:
        click.echo("\nNo changes to apply.")


@skill_feedback_group.command(
    "list-rules",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=("Lists the loaded YAML rules. Useful for inspection and debugging.",),
        examples=(
            "atelier skill_feedback list-rules",
            "atelier skill_feedback list-rules --rules-dir custom/feedback_rules",
            "atelier skill_feedback list-rules --json",
        ),
    ),
)
@click.option(
    "--rules-dir",
    "rules_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Override the YAML rule library directory.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def list_rules_command(rules_dir: Path | None, json_output: bool) -> None:
    """List rules loaded from the feedback rule library."""

    target = rules_dir.resolve() if rules_dir is not None else KNOWN_RULES_DIR
    try:
        rules = load_rules(target)
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload: dict[str, Any] = {
        "rules_dir": str(target),
        "rule_count": len(rules),
        "rules": [
            {
                "id": rule.id,
                "error_types": list(rule.error_types),
                "message_patterns": [pattern.pattern for pattern in rule.message_patterns],
                "rule_text": rule.rule_text,
                "rationale": rule.rationale,
            }
            for rule in rules
        ],
    }

    if json_output:
        echo_json(payload)
        return

    click.echo(f"Rules dir: {target}")
    click.echo(f"Loaded {len(rules)} rule(s)")
    for rule in rules:
        click.echo("")
        click.echo(f"- id: {rule.id}")
        click.echo(f"  error_types: {', '.join(rule.error_types)}")
        click.echo(f"  rule: {rule.rule_text}")


def _emit_text_summary(summary: dict[str, Any]) -> None:
    click.echo(f"Entry: {summary['entry']}")
    click.echo(f"error_type: {summary['error_type'] or '<missing>'}")
    click.echo(f"error_message: {summary['error_message'] or '<missing>'}")
    click.echo(f"Derived rule: {summary['rule_text']}")
    click.echo(f"Rationale: {summary['rationale']}")
    matched = summary.get("matched_pattern")
    click.echo(f"Matched pattern: {matched if matched else '<none>'}")
    click.echo(f"Fallback: {'yes' if summary['fallback'] else 'no'}")


__all__ = ["skill_feedback_group"]
