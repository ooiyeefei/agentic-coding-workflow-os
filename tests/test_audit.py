from __future__ import annotations

import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from spanweave.audit import (
    AuditEvent,
    CostAccruedEvent,
    DecisionLoggedEvent,
    EventType,
    GateEnteredEvent,
    LLMCallEvent,
    OverrideAppliedEvent,
    ToolCallEvent,
    events_by_type,
    events_for_run,
    log,
    sum_cost_for_run,
)


def _non_blank_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def _multiprocess_worker(
    repo_path: str, run_id: str, count: int, worker_id: int,
) -> None:
    for i in range(count):
        log(
            run_id,
            EventType.TOOL_CALL,
            {"tool_name": f"proc{worker_id}_tool{i}", "success": True},
            repo_root=Path(repo_path),
            _today=date(2026, 4, 21),
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestEventSchemas:
    def test_llm_call_event_round_trip(self, fixed_run_id: str) -> None:
        event = LLMCallEvent(
            run_id=fixed_run_id,
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=200,
            cost_usd=0.003,
            stop_reason="end_turn",
        )
        line = event.to_json_line()
        restored = AuditEvent.from_json_line(line)
        assert isinstance(restored, LLMCallEvent)
        assert restored.event_id == event.event_id
        assert restored.provider == "anthropic"
        assert restored.cost_usd == pytest.approx(0.003)

    def test_tool_call_event_round_trip(self, fixed_run_id: str) -> None:
        event = ToolCallEvent(
            run_id=fixed_run_id,
            tool_name="bash",
            arguments_summary="ls -la",
            result_summary="success",
            success=True,
            duration_ms=42,
        )
        restored = AuditEvent.from_json_line(event.to_json_line())
        assert isinstance(restored, ToolCallEvent)
        assert restored.tool_name == "bash"
        assert restored.duration_ms == 42

    def test_gate_entered_event_round_trip(self, fixed_run_id: str) -> None:
        event = GateEnteredEvent(
            run_id=fixed_run_id,
            gate_name="code_review",
            from_stage="coding",
            to_stage="review",
            verdict="APPROVED",
        )
        restored = AuditEvent.from_json_line(event.to_json_line())
        assert isinstance(restored, GateEnteredEvent)
        assert restored.gate_name == "code_review"

    def test_decision_logged_event_round_trip(self, fixed_run_id: str) -> None:
        event = DecisionLoggedEvent(
            run_id=fixed_run_id,
            decision_id="decision_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            summary="Use O_APPEND for audit writes",
            source="coder",
            confidence=0.95,
        )
        restored = AuditEvent.from_json_line(event.to_json_line())
        assert isinstance(restored, DecisionLoggedEvent)
        assert restored.confidence == pytest.approx(0.95)

    def test_override_applied_event_round_trip(self, fixed_run_id: str) -> None:
        event = OverrideAppliedEvent(
            run_id=fixed_run_id,
            target="max_cost_usd",
            original_value="1.00",
            override_value="5.00",
            reason="approved by lead",
        )
        restored = AuditEvent.from_json_line(event.to_json_line())
        assert isinstance(restored, OverrideAppliedEvent)
        assert restored.override_value == "5.00"

    def test_cost_accrued_event_round_trip(self, fixed_run_id: str) -> None:
        event = CostAccruedEvent(
            run_id=fixed_run_id,
            cost_usd=0.05,
            category="llm",
            detail="claude-sonnet batch",
        )
        restored = AuditEvent.from_json_line(event.to_json_line())
        assert isinstance(restored, CostAccruedEvent)
        assert restored.cost_usd == pytest.approx(0.05)

    def test_unknown_event_type_raises(self) -> None:
        line = json.dumps({
            "event_type": "NONEXISTENT",
            "run_id": "run_abc",
            "event_id": "evt_abc",
        })
        with pytest.raises(ValueError, match="unknown event_type"):
            AuditEvent.from_json_line(line)

    def test_extra_field_rejected(self, fixed_run_id: str) -> None:
        with pytest.raises(ValidationError):
            LLMCallEvent(
                run_id=fixed_run_id,
                provider="anthropic",
                model="claude",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.01,
                unexpected_field="boom",  # type: ignore[call-arg]
            )

    def test_negative_cost_rejected(self, fixed_run_id: str) -> None:
        with pytest.raises(ValidationError):
            CostAccruedEvent(
                run_id=fixed_run_id,
                cost_usd=-1.0,
                category="llm",
            )

    def test_missing_event_type_in_json_raises(self) -> None:
        line = json.dumps({"run_id": "run_abc", "event_id": "evt_abc"})
        with pytest.raises(ValueError, match="missing 'event_type'"):
            AuditEvent.from_json_line(line)

    def test_naive_timestamp_rejected(self, fixed_run_id: str) -> None:
        with pytest.raises(ValidationError, match="timezone-aware"):
            LLMCallEvent(
                run_id=fixed_run_id,
                provider="anthropic",
                model="claude",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                timestamp=datetime(2026, 1, 1),
            )

    def test_invalid_run_id_prefix_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LLMCallEvent(
                run_id="bad_prefix_123",
                provider="anthropic",
                model="claude",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
            )


# ---------------------------------------------------------------------------
# Writer: log()
# ---------------------------------------------------------------------------


class TestWriter:
    def test_log_creates_per_run_and_daily_files(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        today = date(2026, 4, 21)
        log(
            fixed_run_id,
            EventType.LLM_CALL,
            {
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "input_tokens": 500,
                "output_tokens": 100,
                "cost_usd": 0.002,
            },
            repo_root=repo,
            _today=today,
        )

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        daily_log = repo / ".spanweave" / "audit" / "2026-04-21.jsonl"

        assert run_log.exists()
        assert daily_log.exists()

        run_lines = _non_blank_lines(run_log.read_text())
        daily_lines = _non_blank_lines(daily_log.read_text())
        assert len(run_lines) == 1
        assert len(daily_lines) == 1

        parsed = json.loads(run_lines[0])
        assert parsed["event_type"] == "LLM_CALL"
        assert parsed["provider"] == "anthropic"

    def test_log_appends_multiple_events(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        today = date(2026, 4, 21)
        for i in range(5):
            log(
                fixed_run_id,
                EventType.TOOL_CALL,
                {"tool_name": f"tool_{i}", "success": True},
                repo_root=repo,
                _today=today,
            )

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        lines = _non_blank_lines(run_log.read_text())
        assert len(lines) == 5

        tool_names = {json.loads(line)["tool_name"] for line in lines}
        assert tool_names == {f"tool_{i}" for i in range(5)}

    def test_log_returns_typed_event(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        event = log(
            fixed_run_id,
            EventType.GATE_ENTERED,
            {"gate_name": "review_gate", "verdict": "APPROVED"},
            repo_root=repo,
            _today=date(2026, 4, 21),
        )
        assert isinstance(event, GateEnteredEvent)
        assert event.gate_name == "review_gate"

    def test_log_rejects_unknown_event_type(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        with pytest.raises(ValueError, match="unknown event_type"):
            log(
                fixed_run_id,
                "NOT_A_TYPE",  # type: ignore[arg-type]
                {},
                repo_root=repo,
            )

    def test_daily_rollover_creates_separate_files(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        day1 = date(2026, 4, 20)
        day2 = date(2026, 4, 21)

        log(
            fixed_run_id,
            EventType.COST_ACCRUED,
            {"cost_usd": 0.01, "category": "llm"},
            repo_root=repo,
            _today=day1,
        )
        log(
            fixed_run_id,
            EventType.COST_ACCRUED,
            {"cost_usd": 0.02, "category": "llm"},
            repo_root=repo,
            _today=day2,
        )

        daily1 = repo / ".spanweave" / "audit" / "2026-04-20.jsonl"
        daily2 = repo / ".spanweave" / "audit" / "2026-04-21.jsonl"

        assert daily1.exists()
        assert daily2.exists()

        lines1 = _non_blank_lines(daily1.read_text())
        lines2 = _non_blank_lines(daily2.read_text())
        assert len(lines1) == 1
        assert len(lines2) == 1

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        run_lines = _non_blank_lines(run_log.read_text())
        assert len(run_lines) == 2


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_secrets_redacted_in_audit_log(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        log(
            fixed_run_id,
            EventType.TOOL_CALL,
            {
                "tool_name": "env_reader",
                "arguments_summary": "OPENAI_API_KEY=sk-proj-abc123def456ghi789",
                "result_summary": "read env var",
            },
            repo_root=repo,
            _today=date(2026, 4, 21),
        )

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        content = run_log.read_text()
        assert "sk-proj-abc123def456ghi789" not in content
        assert "[REDACTED:" in content

    def test_github_pat_redacted(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        log(
            fixed_run_id,
            EventType.OVERRIDE_APPLIED,
            {
                "target": "github_token",
                "original_value": "ghp_ABCDEFGHIJKLMNOPabcdefghijklmnop",
                "override_value": "ghp_NewTokenValue12345678901234567890",
                "reason": "rotated credentials",
            },
            repo_root=repo,
            _today=date(2026, 4, 21),
        )

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        content = run_log.read_text()
        assert "ghp_ABCDEFGHIJKLMNOP" not in content
        assert "ghp_NewTokenValue" not in content
        assert "[REDACTED:" in content

    def test_bearer_token_redacted(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        log(
            fixed_run_id,
            EventType.TOOL_CALL,
            {
                "tool_name": "http_request",
                "arguments_summary": (
                    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123"
                ),
                "result_summary": "200 OK",
            },
            repo_root=repo,
            _today=date(2026, 4, 21),
        )

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        content = run_log.read_text()
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in content
        assert "[REDACTED:" in content

    def test_json_shaped_secret_redacted(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        log(
            fixed_run_id,
            EventType.TOOL_CALL,
            {
                "tool_name": "raw-json",
                "arguments_summary": '{"api_key": "sk-xxx"}',
                "result_summary": "ok",
            },
            repo_root=repo,
            _today=date(2026, 4, 21),
        )

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        content = run_log.read_text()
        assert "sk-xxx" not in content
        assert "[REDACTED:" in content

    def test_json_shaped_password_redacted(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        log(
            fixed_run_id,
            EventType.TOOL_CALL,
            {
                "tool_name": "db-connect",
                "arguments_summary": '{"password": "hunter2", "host": "db.local"}',
                "result_summary": "connected",
            },
            repo_root=repo,
            _today=date(2026, 4, 21),
        )

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        content = run_log.read_text()
        assert "hunter2" not in content
        assert "db.local" in content
        assert "[REDACTED:" in content


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


class TestQueryHelpers:
    def test_events_for_run_returns_typed_events(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        today = date(2026, 4, 21)
        log(
            fixed_run_id,
            EventType.LLM_CALL,
            {
                "provider": "anthropic",
                "model": "claude",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.001,
            },
            repo_root=repo,
            _today=today,
        )
        log(
            fixed_run_id,
            EventType.TOOL_CALL,
            {"tool_name": "read", "success": True},
            repo_root=repo,
            _today=today,
        )

        events = events_for_run(fixed_run_id, repo_root=repo)
        assert len(events) == 2
        assert isinstance(events[0], LLMCallEvent)
        assert isinstance(events[1], ToolCallEvent)

    def test_events_for_run_empty_when_no_log(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        events = events_for_run(fixed_run_id, repo_root=repo)
        assert events == []

    def test_events_by_type_filters_correctly(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        today = date(2026, 4, 21)
        log(
            fixed_run_id,
            EventType.LLM_CALL,
            {
                "provider": "anthropic",
                "model": "claude",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.001,
            },
            repo_root=repo,
            _today=today,
        )
        log(
            fixed_run_id,
            EventType.TOOL_CALL,
            {"tool_name": "bash"},
            repo_root=repo,
            _today=today,
        )
        log(
            fixed_run_id,
            EventType.LLM_CALL,
            {
                "provider": "openai",
                "model": "gpt-4",
                "input_tokens": 200,
                "output_tokens": 80,
                "cost_usd": 0.005,
            },
            repo_root=repo,
            _today=today,
        )

        llm_events = events_by_type(
            EventType.LLM_CALL, repo_root=repo, day=today
        )
        assert len(llm_events) == 2
        assert all(isinstance(e, LLMCallEvent) for e in llm_events)

        tool_events = events_by_type(
            EventType.TOOL_CALL, repo_root=repo, day=today
        )
        assert len(tool_events) == 1

    def test_events_by_type_filters_by_since(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        today = date(2026, 4, 21)
        log(
            fixed_run_id,
            EventType.LLM_CALL,
            {
                "provider": "anthropic",
                "model": "claude",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.001,
                "timestamp": datetime(
                    2026, 4, 21, 10, 0, tzinfo=UTC
                ).isoformat(),
            },
            repo_root=repo,
            _today=today,
        )
        late = log(
            fixed_run_id,
            EventType.LLM_CALL,
            {
                "provider": "anthropic",
                "model": "claude",
                "input_tokens": 200,
                "output_tokens": 80,
                "cost_usd": 0.002,
                "timestamp": datetime(
                    2026, 4, 21, 14, 0, tzinfo=UTC
                ).isoformat(),
            },
            repo_root=repo,
            _today=today,
        )

        cutoff = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
        filtered = events_by_type(
            EventType.LLM_CALL, since=cutoff, repo_root=repo, day=today
        )
        assert len(filtered) == 1
        assert filtered[0].event_id == late.event_id

    def test_sum_cost_for_run_aggregates_correctly(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        today = date(2026, 4, 21)
        log(
            fixed_run_id,
            EventType.LLM_CALL,
            {
                "provider": "anthropic",
                "model": "claude",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cost_usd": 0.003,
            },
            repo_root=repo,
            _today=today,
        )
        log(
            fixed_run_id,
            EventType.COST_ACCRUED,
            {"cost_usd": 0.05, "category": "tool"},
            repo_root=repo,
            _today=today,
        )
        log(
            fixed_run_id,
            EventType.TOOL_CALL,
            {"tool_name": "read"},
            repo_root=repo,
            _today=today,
        )

        total = sum_cost_for_run(fixed_run_id, repo_root=repo)
        assert total == pytest.approx(0.053)

    def test_sum_cost_for_run_zero_when_no_log(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        assert sum_cost_for_run(fixed_run_id, repo_root=repo) == 0.0


# ---------------------------------------------------------------------------
# Concurrency: 1000 concurrent appends
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_1000_concurrent_appends_produce_valid_json_lines(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        today = date(2026, 4, 21)
        num_writers = 1000

        def write_event(index: int) -> str:
            event = log(
                fixed_run_id,
                EventType.TOOL_CALL,
                {
                    "tool_name": f"tool_{index}",
                    "arguments_summary": f"arg_{index}",
                    "success": True,
                },
                repo_root=repo,
                _today=today,
            )
            return event.event_id

        with ThreadPoolExecutor(max_workers=32) as executor:
            event_ids = list(executor.map(write_event, range(num_writers)))

        assert len(event_ids) == num_writers
        assert len(set(event_ids)) == num_writers

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        raw_lines = _non_blank_lines(run_log.read_text())
        assert len(raw_lines) == num_writers

        parsed_ids: set[str] = set()
        for i, line in enumerate(raw_lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                pytest.fail(
                    f"corrupt JSON at line {i + 1}: {line[:100]!r}"
                )
            assert isinstance(payload, dict), (
                f"line {i + 1} is not a JSON object"
            )
            assert payload["event_type"] == "TOOL_CALL"
            parsed_ids.add(payload["event_id"])

        assert len(parsed_ids) == num_writers

        daily_log = repo / ".spanweave" / "audit" / "2026-04-21.jsonl"
        daily_lines = _non_blank_lines(daily_log.read_text())
        assert len(daily_lines) == num_writers

    def test_concurrent_mixed_event_types(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        today = date(2026, 4, 21)
        event_configs: list[tuple[EventType, dict[str, object]]] = [
            (EventType.LLM_CALL, {
                "provider": "anthropic", "model": "claude",
                "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.001,
            }),
            (EventType.TOOL_CALL, {"tool_name": "bash", "success": True}),
            (EventType.GATE_ENTERED, {"gate_name": "review"}),
            (EventType.COST_ACCRUED, {"cost_usd": 0.01, "category": "llm"}),
        ]

        def write_event(index: int) -> str:
            event_type, data = event_configs[index % len(event_configs)]
            event = log(
                fixed_run_id, event_type, data,
                repo_root=repo, _today=today,
            )
            return event.event_id

        num_writers = 200
        with ThreadPoolExecutor(max_workers=16) as executor:
            event_ids = list(executor.map(write_event, range(num_writers)))

        assert len(set(event_ids)) == num_writers

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        raw_lines = _non_blank_lines(run_log.read_text())
        assert len(raw_lines) == num_writers

        for line in raw_lines:
            payload = json.loads(line)
            assert payload["event_type"] in {e.value for e in EventType}

    def test_multiprocess_concurrent_appends_no_corruption(
        self, repo: Path, fixed_run_id: str
    ) -> None:
        num_procs = 8
        events_per_proc = 125
        total_expected = num_procs * events_per_proc

        procs = [
            multiprocessing.Process(
                target=_multiprocess_worker,
                args=(str(repo), fixed_run_id, events_per_proc, i),
            )
            for i in range(num_procs)
        ]

        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(timeout=60)
            assert proc.exitcode == 0, (
                f"worker {proc.name} exited with {proc.exitcode}"
            )

        run_log = repo / ".spanweave" / "runs" / fixed_run_id / "audit.jsonl"
        raw_lines = _non_blank_lines(run_log.read_text())
        assert len(raw_lines) == total_expected

        parsed_ids: set[str] = set()
        for i, line in enumerate(raw_lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                pytest.fail(
                    f"corrupt JSON at line {i + 1}: {line[:100]!r}"
                )
            assert isinstance(payload, dict), (
                f"line {i + 1} is not a JSON object"
            )
            parsed_ids.add(payload["event_id"])

        assert len(parsed_ids) == total_expected

        daily_log = repo / ".spanweave" / "audit" / "2026-04-21.jsonl"
        daily_lines = _non_blank_lines(daily_log.read_text())
        assert len(daily_lines) == total_expected
