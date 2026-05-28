"""CLI command: spanweave review — review and confirm pending learnings."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, cast

import click
import yaml

from spanweave.cli.formatters import build_help_epilog
from spanweave.sharing import load_sharing_policy, should_auto_promote

# Optional 'interactive' extra. Pyright can't see these modules in a fresh dev
# install (they're declared as an optional extra in pyproject.toml), so we
# silence the missing-import / unknown-type complaints here — the runtime
# fallback branch below makes the absence safe.
questionary: Any  # noqa: PLW0604
Console: Any  # noqa: PLW0604
Panel: Any  # noqa: PLW0604
try:
    # ruff: noqa: I001
    import questionary  # type: ignore[no-redef]  # pyright: ignore[reportMissingImports]
    from rich.console import Console  # type: ignore[no-redef]  # pyright: ignore[reportMissingImports]
    from rich.panel import Panel  # type: ignore[no-redef]  # pyright: ignore[reportMissingImports]

    has_interactive = True
except ImportError:
    questionary = None  # type: ignore[no-redef]
    Console = None  # type: ignore[no-redef]
    Panel = None  # type: ignore[no-redef]
    has_interactive = False

# Public alias for tests / external readers; lower-case mutable name keeps
# pyright from complaining about constant-redefinition in the try/except.
HAS_INTERACTIVE = has_interactive


def _parse_record_frontmatter(filepath: Path) -> dict[str, object]:
    """Parse YAML frontmatter from a pending record file."""
    raw = filepath.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}
    _, _, remainder = raw.partition("---\n")
    frontmatter_text, separator, _ = remainder.partition("\n---\n")
    if not separator:
        return {}
    payload = yaml.safe_load(frontmatter_text)
    if not isinstance(payload, dict):
        return {}
    return cast(dict[str, object], payload)


# Mapping from accepted frontmatter `type:` values (case-insensitive) to the
# memory subdirectory that holds them. The pending/ -> destination move is
# routed by this map; anything not in it is rejected as "unknown type" so the
# record stays in pending/ for the user to fix and re-review.
#
# Note: `reflection` is handled separately because its sharing policy field is
# `new_reflections` (not `new_findings`/`new_decisions`), and historically the
# extractor stages reflections under pending/reflections/ rather than
# pending/decisions/.
_TYPE_TO_DIR: dict[str, str] = {
    "decision": "decisions",
    "finding": "findings",
    "rejected_alternative": "rejected_alternatives",
}


def _route_accepted_record(
    filepath: Path, kind: str, repo_path: Path
) -> tuple[Path, str] | None:
    """Determine where to route an accepted record based on sharing policy.

    Returns (destination_path, reason_message), or None if the record's
    frontmatter `type:` is unknown/missing — in that case a warning is written
    to stderr and the caller should leave the file untouched in pending/.

    The route is decided by the frontmatter `type:` field (not by `kind`,
    which only tells us which pending/ subdir the record was found in). This
    way a `type: finding` record dropped into pending/decisions/ (the
    extractor's only pending subdir) still lands in findings/.
    """
    policy = load_sharing_policy(repo_path)
    metadata = _parse_record_frontmatter(filepath)
    memory_root = repo_path / ".spanweave" / "memory"

    # Reflections: dedicated policy field; preserve existing behavior.
    if kind == "reflection":
        if policy.new_reflections == "shared":
            dest_dir = memory_root / "shared" / "reflections"
        else:
            dest_dir = memory_root / "private" / "reflections"
        dest_dir.mkdir(parents=True, exist_ok=True)
        reason = f"{policy.new_reflections}/"
        return dest_dir / filepath.name, reason

    # All other kinds: route by frontmatter `type:`.
    raw_type = metadata.get("type")
    type_str = raw_type.strip().lower() if isinstance(raw_type, str) else ""
    subdir = _TYPE_TO_DIR.get(type_str)
    if subdir is None:
        # Unknown / missing / non-string type: warn and leave in pending/.
        click.echo(
            f"  {filepath.stem} -> SKIPPED (unknown type "
            f"{raw_type!r}; fix frontmatter and re-review). "
            f"Left in pending/.",
            err=True,
        )
        return None

    # Apply existing sharing policy to determine private/ vs shared/.
    if metadata and should_auto_promote(metadata, policy):
        dest_dir = memory_root / "shared" / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        raw_tags = metadata.get("tags", [])
        tags_list: list[str] = (
            cast(list[str], raw_tags) if isinstance(raw_tags, list) else []
        )
        matched_tags: list[str] = [
            t for t in tags_list if t in policy.auto_promote_tags
        ]
        if matched_tags:
            reason = f"shared/{subdir}/ (auto-promoted: tagged '{matched_tags[0]}')"
        else:
            reason = (
                f"shared/{subdir}/ (auto-promoted: confidence threshold exceeded)"
            )
        return dest_dir / filepath.name, reason

    # Default-shared types (e.g. findings under default policy) still land in
    # shared/ even without auto-promote criteria.
    default_field = {
        "decisions": policy.new_decisions,
        "findings": policy.new_findings,
        # No default policy field exists for rejected_alternatives; treat as
        # private by default (same conservative default as decisions).
        "rejected_alternatives": "private",
    }[subdir]

    if default_field == "shared":
        dest_dir = memory_root / "shared" / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        reason = f"shared/{subdir}/ (policy default)"
        return dest_dir / filepath.name, reason

    dest_dir = memory_root / "private" / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    if subdir == "decisions":
        reason = "private/ (promote later with `spanweave promote`)"
    else:
        reason = f"private/{subdir}/"
    return dest_dir / filepath.name, reason


@click.command(
    "review",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Pending learnings come from `spanweave extract` auto-extraction.",
            "Interactive mode requires: pip install spanweave[interactive]",
        ),
        examples=(
            "spanweave review --repo .",
            "spanweave review --auto-accept",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
@click.option(
    "--auto-accept",
    is_flag=True,
    help="Accept all pending without interactive review.",
)
def review_command(repo: Path, auto_accept: bool) -> None:
    """Review and confirm pending learnings from auto-extraction and reflection."""
    repo_path = repo.resolve()
    pending_decisions_dir = repo_path / ".spanweave" / "memory" / "pending" / "decisions"
    pending_reflections_dir = repo_path / ".spanweave" / "memory" / "pending" / "reflections"

    # Gather pending items with their type
    pending_items: list[tuple[Path, str]] = []  # (filepath, kind)

    if pending_decisions_dir.exists():
        for f in sorted(pending_decisions_dir.glob("*.md")):
            pending_items.append((f, "decision"))

    if pending_reflections_dir.exists():
        for f in sorted(pending_reflections_dir.glob("*.md")):
            pending_items.append((f, "reflection"))

    if not pending_items:
        click.echo("No pending learnings to review.")
        return

    accepted = 0
    dismissed = 0
    edited = 0
    skipped = 0

    if auto_accept:
        for filepath, kind in pending_items:
            routed = _route_accepted_record(filepath, kind, repo_path)
            if routed is None:
                # Unknown type: warning already emitted; leave file in pending/.
                skipped += 1
                continue
            dest, reason = routed
            shutil.move(str(filepath), str(dest))
            record_id = filepath.stem
            click.echo(f"  {record_id} -> {reason}")
            accepted += 1
    elif HAS_INTERACTIVE:
        console = Console()
        for filepath, kind in pending_items:
            content = filepath.read_text(encoding="utf-8")
            # Parse frontmatter and body
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1].strip()
                body = parts[2].strip()
            else:
                frontmatter_text = ""
                body = content.strip()

            # Display with kind-specific styling
            if kind == "reflection":
                panel_title = "Pending Reflection"
                border_style = "green"
            else:
                panel_title = "Pending Decision"
                border_style = "blue"

            panel_content = f"{body}\n\n[dim]{frontmatter_text}[/dim]"
            console.print(Panel(panel_content, title=panel_title, border_style=border_style))

            # Prompt
            choice = questionary.select(
                "Action:",
                choices=["Accept", "Edit", "Dismiss"],
            ).ask()

            if choice == "Accept":
                routed = _route_accepted_record(filepath, kind, repo_path)
                if routed is None:
                    # Unknown type: warning already emitted; leave in pending/.
                    skipped += 1
                    continue
                dest, reason = routed
                shutil.move(str(filepath), str(dest))
                click.echo(f"  -> {reason}")
                accepted += 1
            elif choice == "Edit":
                new_body = questionary.text("Edit body:", default=body).ask()
                if new_body and new_body != body:
                    # Rewrite file with edited body
                    if len(parts) >= 3:
                        new_content = f"---\n{parts[1]}---\n{new_body}\n"
                    else:
                        new_content = f"{new_body}\n"
                    filepath.write_text(new_content, encoding="utf-8")
                routed = _route_accepted_record(filepath, kind, repo_path)
                if routed is None:
                    skipped += 1
                    continue
                dest, reason = routed
                shutil.move(str(filepath), str(dest))
                click.echo(f"  -> {reason}")
                edited += 1
            elif choice == "Dismiss":
                filepath.unlink()
                dismissed += 1
    else:
        click.echo(
            "Interactive review requires the 'interactive' extras.\n"
            "Install with: pip install spanweave[interactive]\n"
            "Or use --auto-accept to accept all pending decisions."
        )
        return

    # Summary
    parts_summary: list[str] = []
    if accepted:
        parts_summary.append(f"Accepted {accepted}")
    if edited:
        parts_summary.append(f"edited {edited}")
    if dismissed:
        parts_summary.append(f"dismissed {dismissed}")
    if skipped:
        parts_summary.append(f"skipped {skipped} (unknown type — left in pending/)")

    summary = ", ".join(parts_summary) + " learnings." if parts_summary else "No changes made."
    click.echo(summary)


__all__ = ["review_command"]
