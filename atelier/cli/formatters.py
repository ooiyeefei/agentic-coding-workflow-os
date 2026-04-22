from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def echo_json(payload: Any) -> None:
    import click

    click.echo(json.dumps(payload, indent=2, sort_keys=False))


def build_help_epilog(
    *,
    examples: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> str:
    sections: list[str] = []

    if notes:
        sections.append("Notes:\n\n\b\n" + "\n".join(f"  {note}" for note in notes))
    if examples:
        sections.append("Examples:\n\n\b\n" + "\n".join(f"  {example}" for example in examples))

    return "\n\n".join(sections)


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return "  (none)"

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def _render_row(row: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))

    separator = "  ".join("-" * width for width in widths)
    rendered_rows = [_render_row(headers), separator]
    rendered_rows.extend(_render_row(row) for row in rows)
    return "\n".join(rendered_rows)


def render_stage_tree(stages: Sequence[Mapping[str, str]]) -> str:
    if not stages:
        return "  (no stages yet)"

    rendered: list[str] = []
    last_index = len(stages) - 1
    for index, stage in enumerate(stages):
        connector = "`--" if index == last_index else "|--"
        rendered.append(
            f"{connector} {stage['stage_id']} [{stage['status']}]"
        )
    return "\n".join(rendered)


def render_key_values(pairs: Sequence[tuple[str, str]]) -> str:
    if not pairs:
        return ""
    width = max(len(key) for key, _ in pairs)
    return "\n".join(f"{key.ljust(width)} : {value}" for key, value in pairs)


def render_match_lines(matches: Sequence[Mapping[str, object]]) -> str:
    if not matches:
        return "No matches found."

    lines = [f"{match['path']}:{match['line']}: {match['text']}" for match in matches]
    return "\n".join(lines)


def render_daemon_status(payload: Mapping[str, object]) -> str:
    lines = [
        ("State", str(payload.get("state", "stopped"))),
        ("Mode", str(payload.get("mode", "placeholder"))),
        ("Path", str(payload.get("state_path", ""))),
    ]
    note = payload.get("note")
    if isinstance(note, str) and note:
        lines.append(("Note", note))
    return render_key_values(lines)


@contextmanager
def pushd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
