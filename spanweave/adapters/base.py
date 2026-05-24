from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from textwrap import shorten
from typing import ClassVar, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from spanweave.memory import Decision, MemoryRecord, RejectedAlternative, ReviewFinding
from spanweave.util.ulid import new_run_id, new_stage_id

DEFAULT_ADAPTER_MANIFEST_DIR = Path(__file__).resolve().parent / "manifests"
CapabilityName = Literal["tool_use", "file_access", "bash", "git", "mcp", "memory"]

_ISSUE_PATTERN = re.compile(r"(?:issue\s+)?#\d+", re.IGNORECASE)
_BARE_ISSUE_PATTERN = re.compile(r"#\d+")
_ADR_PATTERN = re.compile(r"ADR-\d{4}", re.IGNORECASE)
_MARKED_RECORD_PATTERN = re.compile(
    (
        r"^(?:[-*]\s*)?"
        r"(?P<marker>decision|finding|review finding|rejected|rejected alternative)"
        r"\s*[:\-]\s*(?P<body>.+)$"
    ),
    re.IGNORECASE,
)
_INFERRED_DECISION_PATTERN = re.compile(
    r"^(?:use|keep|store|support|reference|treat|emit|format|load|parse|ingest|detect)\b",
    re.IGNORECASE,
)
_NATURAL_LANGUAGE_DECISION_PATTERN = re.compile(
    (
        r"^(?:(?:we|i|the team)\s+)?"
        r"(?:decided|chose|agreed|resolved)\s+to\s+"
        r"(?P<body>.+)$"
        r"|^the decision (?:is|was)\s+to\s+(?P<decision_body>.+)$"
    ),
    re.IGNORECASE,
)
_ADR_FILE_PATTERN = re.compile(r"^(?P<number>\d{4})-")

# Role-protocol Decisions are injected by the session-prompt builder so the
# packet compiler can carry the persona's behavior contract. They are rendered
# as the leading directive of the prompt, so they must be filtered out of the
# "Prior Decisions" section to avoid showing the same text twice (issue #67).
# The discriminator mirrors ``spanweave.session.resume._memory_record_path``.
_ROLE_PROTOCOL_TAG = "role-protocol"
_ROLE_PROTOCOL_SOURCE = "spanweave:session.prompt"


def _is_role_protocol_record(record: MemoryRecord) -> bool:
    return _ROLE_PROTOCOL_TAG in record.tags and record.source == _ROLE_PROTOCOL_SOURCE


# Minimum normalized token length to consider for ADR tag matching. Guards
# against trivial 1-2 char tokens producing false-positive substring matches.
_MIN_MATCH_TOKEN_LEN = 3


def _normalize_match_text(text: str) -> str:
    """Lowercase, fold ``-``/``_`` to spaces, collapse whitespace.

    Keeps ``#`` so issue refs (``#24``) survive; this lets a tag like
    ``workflow-validation`` match an ADR title ``# Workflow Validation`` and a
    driver ``* workflow-validation`` after the same normalization.
    """
    lowered = text.casefold().replace("-", " ").replace("_", " ")
    return " ".join(lowered.split())


def _run_match_tokens(memory_records: Sequence[MemoryRecord]) -> list[str]:
    """Build normalized match tokens from a run's record tags and issue refs.

    Tokens are normalized the same way as ADR text so substring matching is
    stable across hyphen/space/case differences.
    """
    tokens: list[str] = []
    seen: set[str] = set()
    for record in memory_records:
        candidates: list[str] = [*record.tags]
        # Match the bare ``#<n>`` form so an ADR referencing the issue matches
        # regardless of an "issue " prefix on either side.
        for issue in record.related_issues:
            candidates.extend(match.group(0) for match in _BARE_ISSUE_PATTERN.finditer(issue))
        for candidate in candidates:
            normalized = _normalize_match_text(candidate)
            if len(normalized) < _MIN_MATCH_TOKEN_LEN or normalized in seen:
                continue
            seen.add(normalized)
            tokens.append(normalized)
    return tokens


class ToolManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[CapabilityName] = Field(min_length=1)
    session_format: str = Field(min_length=1)
    config_paths: list[str] = Field(min_length=1)
    context_injection: str = Field(min_length=1)

    @field_validator("session_format", "context_injection")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized

    @field_validator("capabilities", "config_paths")
    @classmethod
    def _normalize_string_list(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = value.strip()
            if not item:
                raise ValueError("list items must be non-empty")
            if item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        return normalized


def load_tool_manifest(path: str | Path) -> ToolManifest:
    manifest_path = Path(path)
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest {manifest_path} did not contain a YAML mapping")
    return ToolManifest.model_validate(payload)


def load_tool_manifests(directory: str | Path = DEFAULT_ADAPTER_MANIFEST_DIR) -> list[ToolManifest]:
    manifest_dir = Path(directory)
    return [
        load_tool_manifest(path)
        for path in sorted(manifest_dir.glob("*.yaml"))
        if path.is_file()
    ]


def load_shipped_manifest(tool_name: str) -> ToolManifest:
    return load_tool_manifest(DEFAULT_ADAPTER_MANIFEST_DIR / f"{tool_name}.yaml")


@dataclass(frozen=True)
class TranscriptEntry:
    role: str
    text: str
    timestamp: str | None = None
    metadata: dict[str, str] = dataclass_field(default_factory=dict)


def _unique_strings(values: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _record_type_for_marker(
    marker: str,
) -> type[Decision] | type[ReviewFinding] | type[RejectedAlternative]:
    normalized = marker.casefold().replace(" ", "")
    if normalized == "decision":
        return Decision
    if normalized in {"finding", "reviewfinding"}:
        return ReviewFinding
    if normalized in {"rejected", "rejectedalternative"}:
        return RejectedAlternative
    raise ValueError(f"unsupported marker {marker!r}")


def _extract_issue_refs(text: str) -> list[str]:
    return _unique_strings(match.group(0) for match in _ISSUE_PATTERN.finditer(text))


def _extract_related_adrs(text: str) -> list[str]:
    return _unique_strings(match.group(0).upper() for match in _ADR_PATTERN.finditer(text))


def _normalize_candidate_lines(text: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        candidates.append(re.sub(r"^[-*]\s*", "", stripped))
    return candidates


def _summarize_body(body: str) -> str:
    for raw_line in body.splitlines():
        candidate = raw_line.strip().lstrip("#").strip()
        if candidate:
            return shorten(candidate, width=160, placeholder="...")
    return "No summary available."


def _sentence_case(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    return stripped[0].upper() + stripped[1:]


def _natural_language_decision_body(line: str) -> str | None:
    match = _NATURAL_LANGUAGE_DECISION_PATTERN.match(line)
    if match is None:
        return None
    body = match.group("body") or match.group("decision_body")
    if body is None:
        return None
    return _sentence_case(body)


def _build_record(
    record_class: type[Decision] | type[ReviewFinding] | type[RejectedAlternative],
    *,
    body: str,
    run_id: str,
    stage_id: str,
    source: str,
    related_issues: Sequence[str],
    tags: Sequence[str],
    confidence: float,
) -> MemoryRecord:
    payload: dict[str, object] = {
        "run_id": run_id,
        "stage_id": stage_id,
        "related_issues": list(related_issues),
        "related_adrs": _extract_related_adrs(body),
        "tags": _unique_strings(tags),
        "confidence": confidence,
        "source": source,
        "body": body,
    }
    return cast(MemoryRecord, record_class.model_validate(payload))


def extract_records_from_entries(
    entries: Sequence[TranscriptEntry],
    *,
    source: str,
    default_tags: Sequence[str] = (),
) -> list[MemoryRecord]:
    if not entries:
        return []

    run_id = new_run_id()
    stage_id = new_stage_id()
    combined_text = "\n".join(entry.text for entry in entries)
    related_issues = _extract_issue_refs(combined_text)
    extracted: list[MemoryRecord] = []
    seen: set[tuple[str, str]] = set()

    for entry in entries:
        for line in _normalize_candidate_lines(entry.text):
            match = _MARKED_RECORD_PATTERN.match(line)
            if match is not None:
                record_class = _record_type_for_marker(match.group("marker"))
                body = match.group("body").strip()
                confidence = 0.95
            elif entry.role == "assistant" and _INFERRED_DECISION_PATTERN.match(line):
                record_class = Decision
                body = line.strip()
                confidence = 0.65
            elif entry.role == "assistant" and (
                natural_body := _natural_language_decision_body(line)
            ):
                record_class = Decision
                body = natural_body
                confidence = 0.85
            else:
                continue

            key = (record_class.record_type, body.casefold())
            if key in seen:
                continue
            seen.add(key)
            extracted.append(
                _build_record(
                    record_class,
                    body=body,
                    run_id=run_id,
                    stage_id=stage_id,
                    source=source,
                    related_issues=related_issues,
                    tags=[*default_tags, entry.role, record_class.record_type.casefold()],
                    confidence=confidence,
                )
            )

    return extracted


class ToolAdapter(ABC):
    tool_name: ClassVar[str]
    session_format: ClassVar[str]

    def __init__(self, repo_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root or Path.cwd())

    @property
    def manifest(self) -> ToolManifest | None:
        manifest_path = DEFAULT_ADAPTER_MANIFEST_DIR / f"{self.tool_name}.yaml"
        if not manifest_path.is_file():
            return None
        return load_tool_manifest(manifest_path)

    @abstractmethod
    def ingest_transcript(self, session_path: str | Path) -> list[MemoryRecord]:
        """Read tool-native session state and return extracted typed memory records."""

    @abstractmethod
    def format_context_packet(
        self,
        run_id: str,
        role: str,
        memory_records: Sequence[MemoryRecord],
    ) -> str:
        """Render a paste-ready context packet for this tool."""

    @abstractmethod
    def detect(self) -> bool:
        """Return True when this adapter appears to match the active tool environment."""

    def _source_label(self, session_path: Path) -> str:
        try:
            resolved = session_path.resolve().relative_to(self.repo_root.resolve())
            return f"{self.tool_name}:{resolved.as_posix()}"
        except ValueError:
            return f"{self.tool_name}:{session_path.resolve().as_posix()}"

    def _extract_records(
        self,
        entries: Sequence[TranscriptEntry],
        *,
        session_path: Path,
        extra_tags: Sequence[str] = (),
    ) -> list[MemoryRecord]:
        return extract_records_from_entries(
            entries,
            source=self._source_label(session_path),
            default_tags=[self.tool_name, *extra_tags],
        )

    def _build_packet(
        self,
        *,
        heading: str,
        role: str,
        instructions: Sequence[str],
        config_lines: Sequence[str],
        run_id: str,
        memory_records: Sequence[MemoryRecord],
    ) -> str:
        parts = [
            heading,
            f"Resume work as the `{role}` agent using context transferred by Spanweave.",
            "",
            "## Operating Instructions",
            *[f"- {instruction}" for instruction in instructions],
            "",
            "## Tool Convention Files",
            *[f"- {line}" for line in config_lines],
            "",
            self._render_record_section("Prior Decisions", memory_records, Decision),
            "",
            self._render_record_section("Open Findings", memory_records, ReviewFinding),
            "",
            self._render_record_section(
                "Rejected Alternatives",
                memory_records,
                RejectedAlternative,
            ),
            "",
            self._render_relevant_adrs(memory_records),
            "",
            self._render_run_state(run_id),
        ]
        return "\n".join(parts).strip() + "\n"

    def _render_record_section(
        self,
        title: str,
        memory_records: Sequence[MemoryRecord],
        record_class: type[Decision] | type[ReviewFinding] | type[RejectedAlternative],
    ) -> str:
        records = [
            record
            for record in memory_records
            if isinstance(record, record_class) and not _is_role_protocol_record(record)
        ]
        lines = [f"## {title}"]
        if not records:
            lines.append("- None captured.")
            return "\n".join(lines)

        for record in records:
            lines.append(f"- {_summarize_body(record.body)}")
        return "\n".join(lines)

    def _render_relevant_adrs(self, memory_records: Sequence[MemoryRecord]) -> str:
        """Render the "Relevant ADRs" section.

        Surfaces ADRs two ways and de-dupes the union (issue #73):

        1. Back-references — any ADR id in a record's ``related_adrs``.
        2. On-disk match — ADRs under ``docs/adr/*.md`` whose
           frontmatter/title/content matches the run's tags or issue refs.
           This supplements the back-reference path so ADRs surface even when
           no record was back-filled at ADR-generation time.
        """
        referenced = _unique_strings(
            adr_id
            for record in memory_records
            for adr_id in record.related_adrs
        )
        adrs_on_disk = self._load_adrs_on_disk()
        matched = self._adrs_matching_run(memory_records, adrs_on_disk)

        # Back-referenced ADRs first (provenance is explicit), then on-disk
        # tag/issue matches not already shown. De-dupe by ADR id.
        ordered_ids: list[str] = []
        seen: set[str] = set()
        for adr_id in [*referenced, *matched]:
            if adr_id in seen:
                continue
            seen.add(adr_id)
            ordered_ids.append(adr_id)

        lines = ["## Relevant ADRs"]
        if not ordered_ids:
            lines.append("- No ADRs referenced by transferred memory.")
            return "\n".join(lines)

        for adr_id in ordered_ids:
            entry = adrs_on_disk.get(adr_id)
            if entry is not None:
                path, title, _ = entry
                lines.append(f"- {adr_id}: {title} ({path.relative_to(self.repo_root)})")
            else:
                lines.append(f"- {adr_id}: referenced by memory, file not found in docs/adr/")
        return "\n".join(lines)

    def _load_adrs_on_disk(self) -> dict[str, tuple[Path, str, str]]:
        """Map ADR id -> (path, title, normalized searchable text).

        Files-first: reads ``docs/adr/*.md`` directly; no index or DB.
        """
        adr_dir = self.repo_root / "docs" / "adr"
        adrs: dict[str, tuple[Path, str, str]] = {}
        if not adr_dir.is_dir():
            return adrs
        for path in sorted(adr_dir.glob("*.md")):
            match = _ADR_FILE_PATTERN.match(path.name)
            if match is None:
                continue
            adr_id = f"ADR-{match.group('number')}"
            raw = path.read_text(encoding="utf-8", errors="ignore")
            adrs[adr_id] = (path, self._adr_title_from_text(raw, path), _normalize_match_text(raw))
        return adrs

    def _adrs_matching_run(
        self,
        memory_records: Sequence[MemoryRecord],
        adrs_on_disk: dict[str, tuple[Path, str, str]],
    ) -> list[str]:
        """Return ADR ids whose on-disk text matches the run's tags/issues."""
        if not adrs_on_disk:
            return []
        tokens = _run_match_tokens(memory_records)
        if not tokens:
            return []
        matched: list[str] = []
        for adr_id, (_, _, searchable) in adrs_on_disk.items():
            if any(token in searchable for token in tokens):
                matched.append(adr_id)
        return matched

    def _adr_title_from_text(self, raw: str, path: Path) -> str:
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped.removeprefix("# ").strip()
        return path.stem

    def _render_run_state(self, run_id: str) -> str:
        run_path = self.repo_root / ".spanweave" / "runs" / run_id
        lines = ["## Current Run State", f"- Run ID: {run_id}"]
        if not run_path.is_dir():
            lines.append("- Status: unavailable (run directory not found)")
            return "\n".join(lines)

        state = self._read_yaml_mapping(run_path / "workflow_state.yaml")
        run_metadata = self._read_frontmatter_mapping(run_path / "run.md")
        stage_labels = self._stage_labels(run_path)

        issue_ref = str(run_metadata.get("issue_ref", "")).strip() or "unknown"
        workflow = str(state.get("workflow", "unknown")).strip() or "unknown"
        status = str(state.get("status", "unknown")).strip() or "unknown"
        waiting_reason = str(state.get("waiting_reason", "")).strip()
        current_stage = next(
            (label.split(" [", 1)[0] for label in stage_labels if label.endswith("[current]")),
            "none",
        )

        lines.extend(
            [
                f"- Issue: {issue_ref}",
                f"- Workflow: {workflow}",
                f"- Status: {status}",
                f"- Current stage: {current_stage}",
            ]
        )
        if waiting_reason:
            lines.append(f"- Waiting reason: {waiting_reason}")
        lines.append(
            "- Stages: "
            + (", ".join(stage_labels) if stage_labels else "none recorded")
        )
        return "\n".join(lines)

    def _stage_labels(self, run_path: Path) -> list[str]:
        stages_root = run_path / "stages"
        if not stages_root.is_dir():
            return []

        stage_paths = sorted(path for path in stages_root.iterdir() if path.is_dir())
        labels: list[str] = []
        current_marked = False
        for path in stage_paths:
            if (path / ".complete").is_file():
                status = "completed"
            elif not current_marked:
                status = "current"
                current_marked = True
            else:
                status = "created"
            labels.append(f"{path.name} [{status}]")
        return labels

    def _read_yaml_mapping(self, path: Path) -> dict[str, object]:
        if not path.is_file():
            return {}
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return cast(dict[str, object], payload)

    def _read_frontmatter_mapping(self, path: Path) -> dict[str, object]:
        if not path.is_file():
            return {}

        raw = path.read_text(encoding="utf-8")
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


__all__ = [
    "DEFAULT_ADAPTER_MANIFEST_DIR",
    "ToolAdapter",
    "ToolManifest",
    "TranscriptEntry",
    "extract_records_from_entries",
    "load_shipped_manifest",
    "load_tool_manifest",
    "load_tool_manifests",
]
