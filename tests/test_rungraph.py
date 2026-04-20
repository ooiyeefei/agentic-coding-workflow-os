from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from atelier.rungraph import (
    create_run,
    create_stage,
    list_runs,
    list_stages,
    mark_stage_complete,
    next_stage_to_execute,
    run_lock,
)

_LOCK_HELPER = """
from __future__ import annotations
import sys
import time
from pathlib import Path

from atelier.rungraph import create_stage, mark_stage_complete, run_lock

mode = sys.argv[1]
run_id = sys.argv[2]
signal_path = Path(sys.argv[3])

if mode == "hold":
    release_path = Path(sys.argv[4])
    with run_lock(run_id):
        signal_path.write_text("locked", encoding="utf-8")
        while not release_path.exists():
            time.sleep(0.05)
elif mode == "acquire":
    with run_lock(run_id):
        signal_path.write_text("acquired", encoding="utf-8")
elif mode == "create_stage":
    stage_name = sys.argv[4]
    stage_id = create_stage(run_id, stage_name)
    signal_path.write_text(stage_id, encoding="utf-8")
elif mode == "mark_complete":
    stage_id = sys.argv[4]
    mark_stage_complete(run_id, stage_id)
    signal_path.write_text("completed", encoding="utf-8")
elif mode == "nested_mutation":
    stage_name = sys.argv[4]
    with run_lock(run_id):
        stage_id = create_stage(run_id, stage_name)
        mark_stage_complete(run_id, stage_id)
    signal_path.write_text(stage_id, encoding="utf-8")
else:
    raise SystemExit(f"unsupported mode: {mode}")
"""


def test_create_run_stage_layout_and_resume_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    run_id = create_run("issue #9")
    stage_ids = [
        create_stage(run_id, "specify"),
        create_stage(run_id, "clarify"),
        create_stage(run_id, "implement"),
    ]

    assert list_runs() == [run_id]
    assert list_stages(run_id) == stage_ids

    run_path = tmp_path / ".atelier" / "runs" / run_id
    assert run_path.exists()
    assert (run_path / ".lock").is_file()
    assert (run_path / "run.md").is_file()
    assert (run_path / "audit.jsonl").is_file()
    assert (run_path / "stages").is_dir()

    for stage_id in stage_ids:
        stage_path = run_path / "stages" / stage_id
        assert stage_path.is_dir()
        assert (stage_path / "stage.md").is_file()
        assert (stage_path / "packet.md").is_file()
        assert (stage_path / "transcript.jsonl").is_file()
        assert (stage_path / "evidence.md").is_file()
        assert (stage_path / "evidence.json").is_file()
        assert (stage_path / "decisions").is_dir()
        assert (stage_path / "findings").is_dir()

    mark_stage_complete(run_id, stage_ids[0])
    mark_stage_complete(run_id, stage_ids[1])

    third_stage_path = run_path / "stages" / stage_ids[2]
    (third_stage_path / "packet.md").write_text("partial packet", encoding="utf-8")

    assert next_stage_to_execute(run_id) == stage_ids[2]

    mark_stage_complete(run_id, stage_ids[2])
    assert next_stage_to_execute(run_id) is None


def test_run_lock_blocks_second_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = create_run("issue #9")

    holder_signal = tmp_path / "holder.signal"
    contender_signal = tmp_path / "contender.signal"
    release_signal = tmp_path / "release.signal"

    holder = _start_lock_process(tmp_path, "hold", run_id, holder_signal, release_signal)
    try:
        _wait_for_path(holder_signal)

        contender = _start_lock_process(tmp_path, "acquire", run_id, contender_signal)
        try:
            time.sleep(0.25)
            assert not contender_signal.exists()

            release_signal.write_text("release", encoding="utf-8")
            _wait_for_path(contender_signal)
            _assert_process_completed(contender)
        finally:
            if contender.poll() is None:
                contender.kill()
                contender.wait(timeout=5)

        _assert_process_completed(holder)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=5)


def test_create_stage_blocks_when_run_is_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = create_run("issue #9")

    holder_signal = tmp_path / "holder.signal"
    stage_signal = tmp_path / "stage.signal"
    release_signal = tmp_path / "release.signal"

    holder = _start_lock_process(tmp_path, "hold", run_id, holder_signal, release_signal)
    try:
        _wait_for_path(holder_signal)

        creator = _start_lock_process(tmp_path, "create_stage", run_id, stage_signal, "alpha")
        try:
            time.sleep(0.25)
            assert not stage_signal.exists()
            assert list_stages(run_id) == []

            release_signal.write_text("release", encoding="utf-8")
            _wait_for_path(stage_signal)
            assert stage_signal.read_text(encoding="utf-8") == "001-alpha"
            _assert_process_completed(creator)
            assert list_stages(run_id) == ["001-alpha"]
        finally:
            if creator.poll() is None:
                creator.kill()
                creator.wait(timeout=5)

        _assert_process_completed(holder)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=5)


def test_mark_stage_complete_blocks_when_run_is_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = create_run("issue #9")
    stage_id = create_stage(run_id, "alpha")

    holder_signal = tmp_path / "holder.signal"
    completion_signal = tmp_path / "completion.signal"
    release_signal = tmp_path / "release.signal"

    holder = _start_lock_process(tmp_path, "hold", run_id, holder_signal, release_signal)
    try:
        _wait_for_path(holder_signal)

        completer = _start_lock_process(
            tmp_path,
            "mark_complete",
            run_id,
            completion_signal,
            stage_id,
        )
        try:
            time.sleep(0.25)
            assert not completion_signal.exists()
            assert next_stage_to_execute(run_id) == stage_id

            release_signal.write_text("release", encoding="utf-8")
            _wait_for_path(completion_signal)
            assert completion_signal.read_text(encoding="utf-8") == "completed"
            _assert_process_completed(completer)
            assert next_stage_to_execute(run_id) is None
        finally:
            if completer.poll() is None:
                completer.kill()
                completer.wait(timeout=5)

        _assert_process_completed(holder)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=5)


def test_run_lock_is_reclaimable_after_holder_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = create_run("issue #9")

    holder_signal = tmp_path / "holder.signal"
    reacquired_signal = tmp_path / "reacquired.signal"
    release_signal = tmp_path / "unused.signal"

    holder = _start_lock_process(tmp_path, "hold", run_id, holder_signal, release_signal)
    try:
        _wait_for_path(holder_signal)
        holder.kill()
        holder.wait(timeout=5)

        reacquirer = _start_lock_process(tmp_path, "acquire", run_id, reacquired_signal)
        try:
            _wait_for_path(reacquired_signal)
            _assert_process_completed(reacquirer)
        finally:
            if reacquirer.poll() is None:
                reacquirer.kill()
                reacquirer.wait(timeout=5)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=5)


def test_run_lock_releases_after_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = create_run("issue #9")

    try:
        with run_lock(run_id):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    with run_lock(run_id):
        assert True


def test_mutators_can_run_inside_explicit_run_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = create_run("issue #9")
    nested_signal = tmp_path / "nested.signal"

    nested = _start_lock_process(tmp_path, "nested_mutation", run_id, nested_signal, "alpha")
    try:
        _wait_for_path(nested_signal)
        assert nested_signal.read_text(encoding="utf-8") == "001-alpha"
        _assert_process_completed(nested)
    finally:
        if nested.poll() is None:
            nested.kill()
            nested.wait(timeout=5)

    assert list_stages(run_id) == ["001-alpha"]
    assert next_stage_to_execute(run_id) is None


def _start_lock_process(
    workdir: Path,
    mode: str,
    run_id: str,
    signal_path: Path,
    extra_argument: str | Path | None = None,
) -> subprocess.Popen[str]:
    args = [sys.executable, "-c", _LOCK_HELPER, mode, run_id, str(signal_path)]
    if extra_argument is not None:
        args.append(str(extra_argument))

    environment = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(repo_root) if pythonpath is None else f"{repo_root}{os.pathsep}{pythonpath}"
    )

    return subprocess.Popen(
        args,
        cwd=workdir,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_path(path: Path, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {path}")


def _assert_process_completed(process: subprocess.Popen[str]) -> None:
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, (
        f"subprocess exited with {process.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
