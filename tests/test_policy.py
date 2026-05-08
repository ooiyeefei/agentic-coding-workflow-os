from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from spanweave.policy import CostCapExceeded, CostTracker, PolicyEngine


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row) for row in rows)
    path.write_text(f"{payload}\n", encoding="utf-8")


def _build_engine(tmp_path: Path, *, today: date) -> PolicyEngine:
    tracker = CostTracker(repo_root=tmp_path, today_provider=lambda: today)
    return PolicyEngine(cost_tracker=tracker)


def test_requires_approval_for_destructive_stages() -> None:
    engine = PolicyEngine()

    assert engine.requires_approval("rebase-before-pr", {}) is True
    assert engine.requires_approval("cleanup-worktree", {}) is True


def test_requires_approval_returns_false_for_normal_stage() -> None:
    engine = PolicyEngine()

    assert engine.requires_approval("implement", {}) is False


def test_is_dry_run_defaults_git_mutations_and_skips_read_only_ops() -> None:
    engine = PolicyEngine()

    assert engine.is_dry_run("git-rebase") is True
    assert engine.is_dry_run("git-branch") is True
    assert engine.is_dry_run("git-push") is True
    assert engine.is_dry_run("git-status") is False
    assert engine.is_dry_run("implement") is False


@pytest.mark.parametrize(
    ("proposed_cost", "should_raise"),
    [
        (Decimal("4.99"), False),
        (Decimal("5.00"), False),
        (Decimal("5.01"), True),
    ],
)
def test_check_cost_enforces_run_cap_boundaries(
    tmp_path: Path,
    fixed_run_id: str,
    proposed_cost: Decimal,
    should_raise: bool,
) -> None:
    today = date(2026, 4, 20)
    engine = _build_engine(tmp_path, today=today)

    if should_raise:
        with pytest.raises(CostCapExceeded):
            engine.check_cost(fixed_run_id, proposed_cost)
        return

    assert engine.check_cost(fixed_run_id, proposed_cost) is True


def test_check_cost_uses_existing_run_total_from_audit_log(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    today = date(2026, 4, 20)
    engine = _build_engine(tmp_path, today=today)
    run_log = tmp_path / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
    _write_jsonl(
        run_log,
        [
            {"event_type": "COST_ACCRUED", "cost_usd": "1.50"},
            {"event_type": "LLM_CALL", "data": {"cost": {"total_usd": "2.50"}}},
        ],
    )

    with pytest.raises(CostCapExceeded) as exc_info:
        engine.check_cost(fixed_run_id, Decimal("2.00"))

    assert exc_info.value.scope == "run"
    assert exc_info.value.projected_total_usd == Decimal("6.00")


def test_check_cost_raises_when_daily_total_exceeds_cap(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    today = date(2026, 4, 20)
    engine = _build_engine(tmp_path, today=today)
    daily_log = tmp_path / ".spanweave" / "audit" / f"{today.isoformat()}.jsonl"
    _write_jsonl(
        daily_log,
        [{"event_type": "LLM_CALL", "data": {"cost": {"total_usd": "49.99"}}}],
    )

    with pytest.raises(CostCapExceeded) as exc_info:
        engine.check_cost(fixed_run_id, Decimal("0.02"))

    assert exc_info.value.scope == "day"
    assert exc_info.value.projected_total_usd == Decimal("50.01")


def test_cost_tracker_raises_on_invalid_json(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    tracker = CostTracker(repo_root=tmp_path)
    run_log = tmp_path / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
    run_log.parent.mkdir(parents=True, exist_ok=True)
    run_log.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        tracker.sum_run_cost(fixed_run_id)


def test_cost_tracker_raises_on_negative_cost(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    tracker = CostTracker(repo_root=tmp_path)
    run_log = tmp_path / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
    _write_jsonl(
        run_log,
        [
            {"event_type": "COST_ACCRUED", "cost_usd": "10.00"},
            {"event_type": "COST_ACCRUED", "cost_usd": "-9.99"},
        ],
    )

    with pytest.raises(ValueError, match="Negative cost"):
        tracker.sum_run_cost(fixed_run_id)
