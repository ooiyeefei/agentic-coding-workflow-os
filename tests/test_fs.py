from __future__ import annotations

import os
from pathlib import Path

import pytest
from spanweave.util import atomic_write, safe_mkdir


def test_safe_mkdir_is_idempotent(tmp_path: Path) -> None:
    directory = tmp_path / "nested" / "dir"

    first = safe_mkdir(directory)
    second = safe_mkdir(directory)

    assert first == directory
    assert second == directory
    assert directory.is_dir()


def test_atomic_write_creates_parent_and_replaces_text(tmp_path: Path) -> None:
    destination = tmp_path / "packets" / "packet.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("old", encoding="utf-8")

    result = atomic_write(destination, "new")

    assert result == destination
    assert destination.read_text(encoding="utf-8") == "new"
    assert sorted(path.name for path in destination.parent.iterdir()) == ["packet.md"]


def test_atomic_write_supports_bytes(tmp_path: Path) -> None:
    destination = tmp_path / "evidence" / "blob.bin"

    atomic_write(destination, b"\x00\x01spanweave")

    assert destination.read_bytes() == b"\x00\x01spanweave"


def test_atomic_write_replace_failure_leaves_destination_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "audit.jsonl"
    destination.write_text("original", encoding="utf-8")
    observed: dict[str, str | bool] = {}

    def fail_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        temp_path = Path(src)
        observed["tmp_exists_before_failure"] = temp_path.exists()
        observed["tmp_content"] = temp_path.read_text(encoding="utf-8")
        observed["destination_name"] = Path(dst).name
        raise RuntimeError("boom")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(RuntimeError, match="boom"):
        atomic_write(destination, "updated")

    assert destination.read_text(encoding="utf-8") == "original"
    assert observed == {
        "tmp_exists_before_failure": True,
        "tmp_content": "updated",
        "destination_name": "audit.jsonl",
    }
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit.jsonl"]
