from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from atelier.compiler.budget import enforce_budget, estimate_tokens
from atelier.compiler.provenance import (
    ProvenanceTuple,
    build_provenance_tag,
    render_provenance_footer,
)
from atelier.compiler.sources import (
    PRIORITY_ORDER,
    Objective,
    PriorityTier,
    Source,
)


def _provenance_list() -> list[tuple[str, str, str | None]]:
    return []


class Packet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str
    provenance: list[tuple[str, str, str | None]] = Field(default_factory=_provenance_list)
    estimated_tokens: int


def compile_packet(
    objective: str | Objective,
    sources: Sequence[Source],
    budget_tokens: int,
) -> Packet:
    ordered_input_sources = _require_source_sequence(cast(object, sources))
    normalized_objective = _normalize_objective(objective)
    ordered_sources = _order_sources(normalized_objective, ordered_input_sources)
    deduped_sources = _dedupe_sources(ordered_sources)
    grouped_sources = _group_sources_by_priority(deduped_sources)

    selected_sources: list[Source] = enforce_budget(
        must_items=grouped_sources["must"],
        should_items=grouped_sources["should"],
        nice_items=grouped_sources["nice"],
        budget_tokens=budget_tokens,
        render=_render_packet_body,
    )

    provenance = _build_provenance(selected_sources)
    body = _render_packet_body(selected_sources)
    return Packet(
        body=body,
        provenance=provenance,
        estimated_tokens=estimate_tokens(body),
    )


def _normalize_objective(objective: str | Objective) -> Objective:
    if isinstance(objective, Objective):
        return objective.model_copy(update={"priority": "must"})
    return Objective(content=objective)


def _require_source_sequence(sources: object) -> Sequence[Source]:
    if not isinstance(sources, Sequence):
        raise TypeError("sources must be an ordered sequence to preserve deterministic order")
    return cast(Sequence[Source], sources)


def _order_sources(objective: Objective, sources: Sequence[Source]) -> list[Source]:
    prioritized_sources = sorted(
        sources,
        key=lambda source: PRIORITY_ORDER[source.priority],
    )
    return [objective, *prioritized_sources]


def _dedupe_sources(sources: Sequence[Source]) -> list[Source]:
    seen_ids: set[str] = set()
    deduped: list[Source] = []

    for source in sources:
        if source.source_id in seen_ids:
            continue
        seen_ids.add(source.source_id)
        deduped.append(source)

    return deduped


def _group_sources_by_priority(sources: Sequence[Source]) -> dict[PriorityTier, list[Source]]:
    grouped: dict[PriorityTier, list[Source]] = {
        "must": [],
        "should": [],
        "nice": [],
    }
    for source in sources:
        grouped[source.priority].append(source)
    return grouped


def _render_packet_body(sources: Sequence[Source]) -> str:
    provenance = _build_provenance(sources)
    parts = ["# Context Packet"]
    parts.extend(_render_source_block(source) for source in sources)
    parts.append(render_provenance_footer(provenance))
    return "\n\n".join(parts) + "\n"


def _render_source_block(source: Source) -> str:
    metadata = f"_Source: {source.source_type} | {source.source_id} | {source.path or '-'}_"
    return "\n".join((f"## {source.title}", metadata, "", source.content))


def _build_provenance(sources: Sequence[Source]) -> list[ProvenanceTuple]:
    entries: list[ProvenanceTuple] = []
    for source in sources:
        entries.append(build_provenance_tag(source))
    return entries


__all__ = ["Packet", "compile_packet"]
