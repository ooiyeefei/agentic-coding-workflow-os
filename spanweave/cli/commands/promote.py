"""CLI command: spanweave promote — move private decisions to shared."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

import click
import yaml

from spanweave.cli.formatters import build_help_epilog
from spanweave.sharing import load_sharing_policy, should_auto_promote


def _parse_frontmatter(filepath: Path) -> dict[str, object]:
    """Parse YAML frontmatter from a markdown record file."""
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


def _collection_for_id(record_id: str) -> str | None:
    """Infer the collection name from a record ID prefix."""
    prefix_map = {
        "decision": "decisions",
        "review_finding": "findings",
        "rejected_alternative": "rejected_alternatives",
        "skill_outcome": "skill_outcomes",
    }
    for prefix, collection in prefix_map.items():
        if record_id.startswith(f"{prefix}_"):
            return collection
    return None


def _find_record_in_private(
    record_id: str, memory_root: Path
) -> tuple[Path, str] | None:
    """Find a record file in private/ by its ID, return (path, collection)."""
    collection = _collection_for_id(record_id)
    if collection:
        candidate = memory_root / "private" / collection / f"{record_id}.md"
        if candidate.is_file():
            return candidate, collection

    # Fallback: search all private collections
    private_dir = memory_root / "private"
    if not private_dir.is_dir():
        return None
    for md_file in private_dir.rglob(f"{record_id}.md"):
        # Determine collection from path
        relative = md_file.relative_to(private_dir)
        coll = relative.parts[0] if len(relative.parts) > 1 else "decisions"
        return md_file, coll
    return None


def _is_already_shared(record_id: str, memory_root: Path) -> bool:
    """Check if a record is already in shared/."""
    collection = _collection_for_id(record_id)
    if collection:
        candidate = memory_root / "shared" / collection / f"{record_id}.md"
        if candidate.is_file():
            return True

    shared_dir = memory_root / "shared"
    if not shared_dir.is_dir():
        return False
    return any(shared_dir.rglob(f"{record_id}.md"))


@click.command(
    "promote",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Moves records from .spanweave/memory/private/ to .spanweave/memory/shared/.",
            "Records in shared/ become visible to teammates via git push.",
        ),
        examples=(
            "spanweave promote decision_01KPT1YDHEJE16N9FFEATWTG63",
            "spanweave promote --all-pending",
        ),
    ),
)
@click.argument("record_id", required=False, default=None)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
@click.option(
    "--all-pending",
    is_flag=True,
    help="Promote all confirmed private decisions that match auto-promote criteria.",
)
def promote_command(record_id: str | None, repo: Path, all_pending: bool) -> None:
    """Promote a private decision to shared (team-visible).

    Moves the record from .spanweave/memory/private/<collection>/ to
    .spanweave/memory/shared/<collection>/. The record is then visible
    to teammates via git push.
    """
    repo_path = repo.resolve()
    memory_root = repo_path / ".spanweave" / "memory"

    if not record_id and not all_pending:
        click.echo("Error: provide a RECORD_ID or use --all-pending.", err=True)
        raise SystemExit(1)

    if all_pending:
        _promote_all_pending(memory_root, repo_path)
        return

    assert record_id is not None

    # Check if already shared
    if _is_already_shared(record_id, memory_root):
        click.echo(f"Already in shared/: {record_id} (no-op)")
        return

    # Find in private
    found = _find_record_in_private(record_id, memory_root)
    if found is None:
        click.echo(f"Error: record {record_id} not found in private/.", err=True)
        raise SystemExit(1)

    source_path, collection = found
    dest_dir = memory_root / "shared" / collection
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / source_path.name
    shutil.move(str(source_path), str(dest_path))
    click.echo(f"Promoted {record_id} to shared/ (visible to team after git push)")


def _promote_all_pending(memory_root: Path, repo_path: Path) -> None:
    """Promote all private decisions matching auto_promote_on_tags or confidence."""
    policy = load_sharing_policy(repo_path)
    private_dir = memory_root / "private"
    if not private_dir.is_dir():
        click.echo("No private records to promote.")
        return

    promoted = 0
    for md_file in sorted(private_dir.rglob("*.md")):
        metadata = _parse_frontmatter(md_file)
        if not metadata:
            continue
        if should_auto_promote(metadata, policy):
            relative = md_file.relative_to(private_dir)
            collection = relative.parts[0] if len(relative.parts) > 1 else "decisions"
            dest_dir = memory_root / "shared" / collection
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / md_file.name
            shutil.move(str(md_file), str(dest_path))
            record_id = metadata.get("id", md_file.stem)
            click.echo(f"Promoted {record_id} to shared/")
            promoted += 1

    if promoted == 0:
        click.echo("No records matched auto-promote criteria.")
    else:
        click.echo(f"\nPromoted {promoted} record(s) to shared/.")


__all__ = ["promote_command"]
