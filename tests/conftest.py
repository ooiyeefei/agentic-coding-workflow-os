from __future__ import annotations

import sys
from pathlib import Path

import pytest
from ulid import ULID

_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_FIXED_ULID_PREFIX = "01ARZ3NDEKTSV4RRFFQ69G5F"
_REPO_ROOT = Path(__file__).resolve().parents[1]

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


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


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if session.testscollected == 0 and exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
