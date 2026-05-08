from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from os import PathLike
from pathlib import Path


def safe_mkdir(path: str | PathLike[str]) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def atomic_write(path: str | PathLike[str], content: str | bytes) -> Path:
    """Replace a destination atomically after fully writing temp content.

    The helper guarantees same-directory atomic replacement semantics and leaves
    the existing destination untouched if the final ``os.replace`` step fails.
    It does not claim universal power-loss durability across platforms or
    filesystems.
    """

    destination = Path(path)
    safe_mkdir(destination.parent)

    fd, temp_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)

    try:
        if isinstance(content, bytes):
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())

        os.replace(temp_path, destination)
    except Exception:
        with suppress(FileNotFoundError):
            temp_path.unlink()
        raise

    return destination


__all__ = ["atomic_write", "safe_mkdir"]
