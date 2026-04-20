from __future__ import annotations

from collections.abc import Iterator

import atelier.util.ulid as ulid_module
import pytest
from atelier.util import (
    EntityPrefix,
    new_action_id,
    new_decision_id,
    new_evidence_id,
    new_packet_id,
    new_run_id,
    new_stage_id,
)
from ulid import ULID


class _DeterministicULIDFactory:
    def __init__(self, values: list[str]) -> None:
        self._values: Iterator[str] = iter(values)

    def __call__(self) -> str:
        return next(self._values)

    @staticmethod
    def parse(value: str) -> ULID:
        return ULID.parse(value)


def test_all_helpers_return_expected_prefixes(
    monkeypatch: pytest.MonkeyPatch,
    fixed_ulid_values: list[str],
) -> None:
    helpers = {
        EntityPrefix.RUN.value: new_run_id,
        EntityPrefix.STAGE.value: new_stage_id,
        EntityPrefix.PACKET.value: new_packet_id,
        EntityPrefix.ACTION.value: new_action_id,
        EntityPrefix.EVIDENCE.value: new_evidence_id,
        EntityPrefix.DECISION.value: new_decision_id,
    }
    monkeypatch.setattr(ulid_module, "ULID", _DeterministicULIDFactory(fixed_ulid_values))

    for prefix, factory in helpers.items():
        value = factory()
        assert value.startswith(f"{prefix}_")
        assert ULID.parse(value.removeprefix(f"{prefix}_"))


def test_run_ids_lexsort_by_creation_order(
    monkeypatch: pytest.MonkeyPatch,
    fixed_ulid_values: list[str],
) -> None:
    monkeypatch.setattr(ulid_module, "ULID", _DeterministicULIDFactory(fixed_ulid_values))
    values = [new_run_id() for _ in range(100)]
    assert values == sorted(values)
