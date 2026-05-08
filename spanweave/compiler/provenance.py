from __future__ import annotations

from typing import TypeAlias

from spanweave.compiler.sources import Source

ProvenanceTuple: TypeAlias = tuple[str, str, str | None]


def build_provenance_tag(source: Source) -> ProvenanceTuple:
    return (source.source_type, source.source_id, source.path)


def render_provenance_footer(entries: list[ProvenanceTuple]) -> str:
    lines = [
        "## Provenance",
        "",
        "| source_type | source_id | path |",
        "| --- | --- | --- |",
    ]

    for source_type, source_id, path in entries:
        lines.append(
            "| "
            f"{_escape_cell(source_type)} | "
            f"{_escape_cell(source_id)} | "
            f"{_escape_cell(path or '-')} |"
        )

    return "\n".join(lines)


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|")


__all__ = ["ProvenanceTuple", "build_provenance_tag", "render_provenance_footer"]
