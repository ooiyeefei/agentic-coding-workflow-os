from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from spanweave.util.fs import atomic_write, safe_mkdir
    from spanweave.util.ulid import (
        EntityPrefix,
        new_action_id,
        new_decision_id,
        new_packet_id,
    )

_EXPORTS: dict[str, tuple[str, str]] = {
    "atomic_write": ("spanweave.util.fs", "atomic_write"),
    "EntityPrefix": ("spanweave.util.ulid", "EntityPrefix"),
    "new_action_id": ("spanweave.util.ulid", "new_action_id"),
    "new_decision_id": ("spanweave.util.ulid", "new_decision_id"),
    "new_packet_id": ("spanweave.util.ulid", "new_packet_id"),
    "safe_mkdir": ("spanweave.util.fs", "safe_mkdir"),
}

__all__ = [
    "EntityPrefix",
    "atomic_write",
    "new_action_id",
    "new_decision_id",
    "new_packet_id",
    "safe_mkdir",
]


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
