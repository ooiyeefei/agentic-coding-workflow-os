from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from spanweave.memory import Decision, RejectedAlternative, list_records
from spanweave.memory.reader import DEFAULT_MEMORY_ROOT
from spanweave.util.fs import atomic_write

from .numbering import next_adr_number
from .slug import slugify

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_ADR_OUTPUT = Path("docs/adr")

_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_ARGUMENT_RE = re.compile(
    r"^\*\s+(Good|Bad|Neutral),\s+because\s+(.+)$", re.MULTILINE
)
_EXTRA_BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class _Argument:
    polarity: str
    text: str


@dataclass(frozen=True)
class _ParsedOption:
    title: str
    description: str
    arguments: list[_Argument] = field(default_factory=list)


def _parse_body(body: str) -> _ParsedOption:
    heading_match = _HEADING_RE.search(body)
    title = heading_match.group(1).strip() if heading_match else body.split("\n", 1)[0].strip()

    arguments = [
        _Argument(polarity=m.group(1), text=m.group(2).strip())
        for m in _ARGUMENT_RE.finditer(body)
    ]

    argument_texts = {a.text for a in arguments}
    lines = body.strip().splitlines()
    desc_lines: list[str] = []
    past_heading = not bool(heading_match)
    for line in lines:
        stripped = line.strip()
        if not past_heading:
            if _HEADING_RE.match(stripped):
                past_heading = True
            continue
        if _ARGUMENT_RE.match(stripped):
            continue
        if stripped and stripped not in argument_texts:
            desc_lines.append(stripped)

    return _ParsedOption(
        title=title,
        description=" ".join(desc_lines),
        arguments=arguments,
    )


def _group_by_topic(
    decisions: list[Decision],
    rejected: list[RejectedAlternative],
) -> dict[str, tuple[list[Decision], list[RejectedAlternative]]]:
    all_records: list[Decision | RejectedAlternative] = [*decisions, *rejected]

    tag_freq: dict[str, int] = {}
    for rec in all_records:
        for tag in rec.tags:
            tag_freq[tag] = tag_freq.get(tag, 0) + 1

    def _topic_key(record: Decision | RejectedAlternative) -> str:
        if not record.tags:
            return "uncategorized"
        return min(record.tags, key=lambda t: (-tag_freq[t], t))

    groups: dict[str, tuple[list[Decision], list[RejectedAlternative]]] = {}
    for d in decisions:
        topic = _topic_key(d)
        if topic not in groups:
            groups[topic] = ([], [])
        groups[topic][0].append(d)
    for r in rejected:
        topic = _topic_key(r)
        if topic not in groups:
            groups[topic] = ([], [])
        groups[topic][1].append(r)
    return groups


def _build_consequences(
    decision_options: list[_ParsedOption],
) -> list[dict[str, str]]:
    consequences: list[dict[str, str]] = []
    for opt in decision_options:
        for arg in opt.arguments:
            if arg.polarity in ("Good", "Bad"):
                consequences.append({"polarity": arg.polarity, "text": arg.text})
    return consequences


def _build_pros_cons(
    all_options: list[_ParsedOption],
) -> list[dict[str, object]]:
    pros_cons: list[dict[str, object]] = []
    for opt in all_options:
        if opt.arguments:
            pros_cons.append({
                "title": opt.title,
                "description": opt.description or None,
                "arguments": [
                    {"polarity": a.polarity, "text": a.text} for a in opt.arguments
                ],
            })
    return pros_cons


def _as_justification(text: str) -> str:
    text = text.rstrip(".")
    if text and text[0].isupper():
        text = text[0].lower() + text[1:]
    return text


def _normalize_rendered(text: str) -> str:
    normalized = _EXTRA_BLANK_LINES_RE.sub("\n\n", text)
    return normalized.strip() + "\n"


def synthesize_adr(
    run_id: str,
    *,
    memory_root: Path = DEFAULT_MEMORY_ROOT,
    adr_output_dir: Path = _DEFAULT_ADR_OUTPUT,
) -> list[Path]:
    """Synthesize MADR 3.0 ADRs from Decision + RejectedAlternative records."""
    decisions = [
        r
        for r in list_records(memory_root, type="Decision", run_id=run_id)
        if isinstance(r, Decision)
    ]
    rejected = [
        r
        for r in list_records(
            memory_root, type="RejectedAlternative", run_id=run_id
        )
        if isinstance(r, RejectedAlternative)
    ]

    if not decisions:
        return []

    groups = _group_by_topic(decisions, rejected)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template("madr.md.j2")

    written: list[Path] = []
    adr_num = next_adr_number(adr_output_dir)

    for topic in sorted(groups):
        topic_decisions, topic_rejected = groups[topic]

        if not topic_decisions:
            continue

        primary = max(
            topic_decisions,
            key=lambda d: (d.confidence or 0.0, -d.timestamp.timestamp()),
        )
        primary_parsed = _parse_body(primary.body)

        decision_options = [_parse_body(d.body) for d in topic_decisions]
        rejected_options = [_parse_body(r.body) for r in topic_rejected]
        all_options = decision_options + rejected_options

        all_tags: set[str] = set()
        for rec in [*topic_decisions, *topic_rejected]:
            all_tags.update(rec.tags)
        all_tags.discard(topic)
        decision_drivers = sorted(all_tags) if all_tags else []

        sources = sorted({rec.source for rec in [*topic_decisions, *topic_rejected]})
        latest = max(rec.timestamp for rec in [*topic_decisions, *topic_rejected])

        consequences = _build_consequences(decision_options)
        pros_cons = _build_pros_cons(all_options)

        adr_title = topic.replace("-", " ").title()

        rendered = template.render(
            title=adr_title,
            status="accepted",
            date=latest.strftime("%Y-%m-%d"),
            decision_makers=", ".join(sources),
            consulted=None,
            informed=None,
            context=primary_parsed.description or primary_parsed.title,
            decision_drivers=decision_drivers if decision_drivers else None,
            considered_options=[{"title": o.title} for o in all_options],
            chosen_option=primary_parsed.title,
            justification=_as_justification(
                primary_parsed.description or primary_parsed.title
            ),
            consequences=consequences if consequences else None,
            confirmation=None,
            pros_cons=pros_cons if pros_cons else None,
            more_information=None,
        )

        slug = slugify(adr_title)
        filename = f"{adr_num:04d}-{slug}.md"
        output_path = adr_output_dir / filename

        atomic_write(output_path, _normalize_rendered(rendered))
        written.append(output_path)
        adr_num += 1

    return written


__all__ = ["synthesize_adr"]
