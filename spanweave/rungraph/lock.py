from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import get_ident
from typing import TextIO

from spanweave.util.paths import run_dir

_LOCK_FILE_NAME = ".lock"


@dataclass
class _HeldRunLock:
    path: Path
    handle: TextIO
    depth: int


_HELD_RUN_LOCKS: dict[tuple[int, str], _HeldRunLock] = {}


@contextmanager
def run_lock(run_id: str) -> Iterator[Path]:
    run_path = run_dir(run_id)
    if not run_path.is_dir():
        raise FileNotFoundError(f"run not found: {run_id}")

    key = (get_ident(), run_id)
    held_lock = _HELD_RUN_LOCKS.get(key)
    if held_lock is not None:
        held_lock.depth += 1
        try:
            yield held_lock.path
        finally:
            held_lock.depth -= 1
        return

    lock_path = run_path / _LOCK_FILE_NAME
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        _HELD_RUN_LOCKS[key] = _HeldRunLock(path=lock_path, handle=handle, depth=1)
        try:
            yield lock_path
        finally:
            active_lock = _HELD_RUN_LOCKS.pop(key)
            fcntl.flock(active_lock.handle.fileno(), fcntl.LOCK_UN)
            active_lock.handle.close()
    except Exception:
        handle.close()
        raise


__all__ = ["run_lock"]
