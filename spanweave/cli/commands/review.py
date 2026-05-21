"""CLI command: spanweave review — review and confirm pending learnings."""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog

try:
    import questionary
    from rich.console import Console
    from rich.panel import Panel

    HAS_INTERACTIVE = True
except ImportError:
    HAS_INTERACTIVE = False


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
    """Review and confirm pending learnings from auto-extraction."""
    repo_path = repo.resolve()
    pending_dir = repo_path / ".spanweave" / "memory" / "pending" / "decisions"
    confirmed_dir = repo_path / ".spanweave" / "memory" / "decisions"

    if not pending_dir.exists():
        click.echo("No pending learnings to review.")
        return

    pending_files = sorted(pending_dir.glob("*.md"))
    if not pending_files:
        click.echo("No pending learnings to review.")
        return

    confirmed_dir.mkdir(parents=True, exist_ok=True)

    accepted = 0
    dismissed = 0
    edited = 0

    if auto_accept:
        for filepath in pending_files:
            dest = confirmed_dir / filepath.name
            shutil.move(str(filepath), str(dest))
            accepted += 1
    elif HAS_INTERACTIVE:
        console = Console()
        for filepath in pending_files:
            content = filepath.read_text(encoding="utf-8")
            # Parse frontmatter and body
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1].strip()
                body = parts[2].strip()
            else:
                frontmatter_text = ""
                body = content.strip()

            # Display
            panel_content = f"{body}\n\n[dim]{frontmatter_text}[/dim]"
            console.print(Panel(panel_content, title="Pending Decision", border_style="blue"))

            # Prompt
            choice = questionary.select(
                "Action:",
                choices=["Accept", "Edit", "Dismiss"],
            ).ask()

            if choice == "Accept":
                dest = confirmed_dir / filepath.name
                shutil.move(str(filepath), str(dest))
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
                dest = confirmed_dir / filepath.name
                shutil.move(str(filepath), str(dest))
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

    summary = ", ".join(parts_summary) + " learnings." if parts_summary else "No changes made."
    click.echo(summary)


__all__ = ["review_command"]
