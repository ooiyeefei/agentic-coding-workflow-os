from __future__ import annotations

import pytest
from ulid import ULID

_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_FIXED_ULID_PREFIX = "01ARZ3NDEKTSV4RRFFQ69G5F"


def _deterministic_ulids(count: int) -> list[str]:
    values = [
        _FIXED_ULID_PREFIX + _CROCKFORD_BASE32[index // 32] + _CROCKFORD_BASE32[index % 32]
        for index in range(count)
    ]
    for value in values:
        ULID.parse(value)
    return values


@pytest.fixture
def fixed_ulid_values() -> list[str]:
    return _deterministic_ulids(100)


@pytest.fixture
def fixed_run_id(fixed_ulid_values: list[str]) -> str:
    return f"run_{fixed_ulid_values[0]}"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if session.testscollected == 0 and exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
