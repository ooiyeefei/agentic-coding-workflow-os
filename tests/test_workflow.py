from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from atelier.evidence.schema import EvidencePack, Verdict
from atelier.policy.engine import PolicyEngine
from atelier.workflow.engine import (
    AdvanceResult,
    RunStatus,
    WorkflowEngine,
    _ASYNC_RUN_LOCKS,
    _read_state,
)
from atelier.workflow.loader import WorkflowNotFoundError, load_workflow
from atelier.workflow.schema import (
    GateType,
    StageDefinition,
    WorkflowDefinition,
    parse_on_reject,
)
from atelier.workflow.stages import StageExecutorDeps, StageResult
from atelier.workflow.transitions import (
    Transition,
    TransitionKind,
    resolve_transition,
)

_FIXED_ULID = "01ARZ3NDEKTSV4RRFFQ69G5F00"


@pytest.fixture(autouse=True)
def _clear_module_locks() -> None:
    _ASYNC_RUN_LOCKS.clear()


# ---------------------------------------------------------------------------
# Mock dependencies
# ---------------------------------------------------------------------------

def _make_evidence(verdict: Verdict) -> EvidencePack:
    return EvidencePack(
        verdict=verdict,
        confidence=0.9,
        summary="mock evidence",
        audit_chain=[_FIXED_ULID],
        timestamp=datetime.now(UTC),
        reviewer_persona_id="mock-reviewer",
    )


class MockPersonaCaller:
    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or {}
        self.calls: list[tuple[str, str, str]] = []

    async def call(
        self, persona_name: str, context: str, *, skill: str, run_id: str
    ) -> str:
        self.calls.append((persona_name, context, skill))
        await asyncio.sleep(0)
        return self._responses.get(persona_name, f"output from {persona_name}")


class MockReviewerCaller:
    def __init__(self, verdicts: list[tuple[Verdict, str]] | None = None) -> None:
        self._verdicts = list(verdicts or [])
        self._call_index = 0
        self.calls: list[str] = []

    async def review(self, content: str, *, run_id: str) -> tuple[Verdict, str]:
        self.calls.append(content)
        await asyncio.sleep(0)
        if self._call_index < len(self._verdicts):
            result = self._verdicts[self._call_index]
            self._call_index += 1
            return result
        return Verdict.APPROVED, ""


class MockEvidenceWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Verdict, str]] = []

    def write(
        self, run_id: str, stage_id: str, verdict: Verdict, content: str
    ) -> EvidencePack:
        self.calls.append((run_id, stage_id, verdict, content))
        return _make_evidence(verdict)


def _make_deps(
    persona_responses: dict[str, str] | None = None,
    reviewer_verdicts: list[tuple[Verdict, str]] | None = None,
) -> StageExecutorDeps:
    return StageExecutorDeps(
        persona_caller=MockPersonaCaller(persona_responses),
        reviewer_caller=MockReviewerCaller(reviewer_verdicts),
        evidence_writer=MockEvidenceWriter(),
    )


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_stage_definition_defaults(self) -> None:
        stage = StageDefinition(id="test", persona="coder", skill="speckit.specify")
        assert stage.gate_type == GateType.AUTO
        assert stage.retry_max == 0
        assert stage.on_reject == "halt"

    def test_workflow_requires_unique_stage_ids(self) -> None:
        with pytest.raises(ValueError, match="duplicate stage id"):
            WorkflowDefinition(
                name="dup",
                version="1.0.0",
                stages=[
                    StageDefinition(id="a", persona="coder", skill="s"),
                    StageDefinition(id="a", persona="coder", skill="s"),
                ],
            )

    def test_workflow_requires_at_least_one_stage(self) -> None:
        with pytest.raises(ValueError):
            WorkflowDefinition(name="empty", version="1.0.0", stages=[])

    def test_revert_to_nonexistent_stage_rejected_at_load(self) -> None:
        with pytest.raises(ValueError, match="not a stage in this workflow"):
            WorkflowDefinition(
                name="bad",
                version="1.0.0",
                stages=[
                    StageDefinition(id="a", persona="coder", skill="s", on_reject="revert_to:missing"),
                ],
            )

    def test_revert_to_valid_stage_accepted(self) -> None:
        wf = WorkflowDefinition(
            name="ok",
            version="1.0.0",
            stages=[
                StageDefinition(id="impl", persona="coder", skill="s"),
                StageDefinition(id="uat", persona="uat", skill="s", on_reject="revert_to:impl"),
            ],
        )
        assert wf.stages[1].on_reject == "revert_to:impl"

    def test_parse_on_reject_simple(self) -> None:
        assert parse_on_reject("halt") == ("halt", None)
        assert parse_on_reject("revise") == ("revise", None)
        assert parse_on_reject("council") == ("council", None)

    def test_parse_on_reject_revert_to(self) -> None:
        action, target = parse_on_reject("revert_to:implement")
        assert action == "revert_to"
        assert target == "implement"

    def test_parse_on_reject_invalid(self) -> None:
        with pytest.raises(ValueError, match="invalid on_reject"):
            parse_on_reject("bogus")

    def test_parse_on_reject_revert_to_empty(self) -> None:
        with pytest.raises(ValueError, match="requires a target"):
            parse_on_reject("revert_to:")

    def test_stage_index(self) -> None:
        wf = WorkflowDefinition(
            name="test",
            version="1.0.0",
            stages=[
                StageDefinition(id="a", persona="coder", skill="s"),
                StageDefinition(id="b", persona="coder", skill="s"),
            ],
        )
        assert wf.stage_index("a") == 0
        assert wf.stage_index("b") == 1
        with pytest.raises(KeyError):
            wf.stage_index("c")


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------

class TestLoader:
    def test_load_speckit_loop_from_defaults(self) -> None:
        wf = load_workflow("speckit-loop")
        assert wf.name == "speckit-loop"
        assert wf.version == "1.0.0"
        assert len(wf.stages) == 8
        assert wf.stages[0].id == "specify"
        assert wf.stages[-1].id == "cleanup"

    def test_load_speckit_loop_stage_details(self) -> None:
        wf = load_workflow("speckit-loop")
        implement = next(s for s in wf.stages if s.id == "implement")
        assert implement.gate_type == GateType.REVIEW
        assert implement.retry_max == 5
        assert implement.on_reject == "revise"

        uat = next(s for s in wf.stages if s.id == "uat")
        assert uat.persona == "uat"
        assert uat.on_reject == "revert_to:implement"

    def test_load_speckit_loop_destructive_stages_require_approval(self) -> None:
        wf = load_workflow("speckit-loop")
        rebase = next(s for s in wf.stages if s.id == "rebase-analyze")
        cleanup = next(s for s in wf.stages if s.id == "cleanup")
        assert rebase.gate_type == GateType.APPROVAL
        assert cleanup.gate_type == GateType.APPROVAL

    def test_user_workflow_overrides_default(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "user_workflows"
        user_dir.mkdir()
        (user_dir / "speckit-loop.yaml").write_text(yaml.safe_dump({
            "name": "speckit-loop",
            "version": "2.0.0",
            "stages": [{"id": "only", "persona": "coder", "skill": "s"}],
        }), encoding="utf-8")

        wf = load_workflow("speckit-loop", user_dir=user_dir)
        assert wf.version == "2.0.0"
        assert len(wf.stages) == 1

    def test_custom_workflow_from_user_dir(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "workflows"
        user_dir.mkdir()
        (user_dir / "minimal.yaml").write_text(yaml.safe_dump({
            "name": "minimal",
            "version": "1.0.0",
            "stages": [
                {"id": "implement", "persona": "coder", "skill": "speckit.implement"},
                {"id": "review", "persona": "reviewer", "skill": "speckit.implement", "gate_type": "review"},
            ],
        }), encoding="utf-8")

        wf = load_workflow("minimal", user_dir=user_dir)
        assert wf.name == "minimal"
        assert len(wf.stages) == 2

    def test_workflow_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowNotFoundError):
            load_workflow("nonexistent", user_dir=tmp_path, defaults_dir=tmp_path)


# ---------------------------------------------------------------------------
# Transition tests
# ---------------------------------------------------------------------------

class TestTransitions:
    def _two_stage_workflow(self) -> WorkflowDefinition:
        return WorkflowDefinition(
            name="test",
            version="1.0.0",
            stages=[
                StageDefinition(id="a", persona="coder", skill="s", gate_type="review", retry_max=2, on_reject="revise"),
                StageDefinition(id="b", persona="coder", skill="s"),
            ],
        )

    def test_approved_advances(self) -> None:
        wf = self._two_stage_workflow()
        t = resolve_transition(wf, wf.stages[0], Verdict.APPROVED, 0)
        assert t.kind == TransitionKind.ADVANCE
        assert t.next_stage_id == "b"

    def test_approved_last_stage_is_done(self) -> None:
        wf = self._two_stage_workflow()
        t = resolve_transition(wf, wf.stages[1], Verdict.APPROVED, 0)
        assert t.kind == TransitionKind.DONE

    def test_needs_revision_retries(self) -> None:
        wf = self._two_stage_workflow()
        t = resolve_transition(wf, wf.stages[0], Verdict.NEEDS_REVISION, 0)
        assert t.kind == TransitionKind.RETRY
        assert "1/2" in t.reason

    def test_needs_revision_exhausted_escalates_to_council(self) -> None:
        wf = self._two_stage_workflow()
        t = resolve_transition(wf, wf.stages[0], Verdict.NEEDS_REVISION, 2)
        assert t.kind == TransitionKind.COUNCIL

    def test_rejected_halts_by_default(self) -> None:
        wf = WorkflowDefinition(
            name="test",
            version="1.0.0",
            stages=[StageDefinition(id="a", persona="coder", skill="s", on_reject="halt")],
        )
        t = resolve_transition(wf, wf.stages[0], Verdict.REJECTED, 0)
        assert t.kind == TransitionKind.HALT

    def test_rejected_with_revert_to(self) -> None:
        wf = WorkflowDefinition(
            name="test",
            version="1.0.0",
            stages=[
                StageDefinition(id="impl", persona="coder", skill="s"),
                StageDefinition(id="uat", persona="uat", skill="s", on_reject="revert_to:impl"),
            ],
        )
        t = resolve_transition(wf, wf.stages[1], Verdict.REJECTED, 0)
        assert t.kind == TransitionKind.REVERT
        assert t.next_stage_id == "impl"


# ---------------------------------------------------------------------------
# Engine tests — speckit-loop (specify → review gate)
# ---------------------------------------------------------------------------

class TestEngineSpeckit:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.mark.asyncio
    async def test_start_creates_run_and_first_stage(self) -> None:
        engine = WorkflowEngine(deps=_make_deps())
        run_id = engine.start("issue #11")

        state = _read_state(run_id)
        assert state["workflow"] == "speckit-loop"
        assert state["cursor"] == 0
        assert state["status"] == "running"

    @pytest.mark.asyncio
    async def test_advance_specify_auto_gate(self) -> None:
        engine = WorkflowEngine(deps=_make_deps())
        run_id = engine.start("issue #11")

        result = await engine.advance(run_id)
        assert result.stage_result is not None
        assert result.stage_result.verdict == Verdict.APPROVED
        assert result.transition.kind == TransitionKind.ADVANCE
        assert result.run_status == RunStatus.RUNNING

        state = _read_state(run_id)
        assert state["cursor"] == 1

    @pytest.mark.asyncio
    async def test_advance_through_two_auto_stages(self) -> None:
        engine = WorkflowEngine(deps=_make_deps())
        run_id = engine.start("issue #11")

        r1 = await engine.advance(run_id)
        assert r1.transition.kind == TransitionKind.ADVANCE

        r2 = await engine.advance(run_id)
        assert r2.transition.kind == TransitionKind.ADVANCE

        state = _read_state(run_id)
        assert state["cursor"] == 2

    @pytest.mark.asyncio
    async def test_review_gate_approved(self) -> None:
        deps = _make_deps(reviewer_verdicts=[(Verdict.APPROVED, "looks good")])
        engine = WorkflowEngine(deps=deps)
        run_id = engine.start("issue #11")

        await engine.advance(run_id)
        await engine.advance(run_id)

        result = await engine.advance(run_id)
        assert result.stage_result is not None
        assert result.stage_result.verdict == Verdict.APPROVED
        assert result.transition.kind == TransitionKind.ADVANCE

    @pytest.mark.asyncio
    async def test_review_gate_needs_revision_retries(self) -> None:
        deps = _make_deps(reviewer_verdicts=[
            (Verdict.NEEDS_REVISION, "fix the imports"),
            (Verdict.APPROVED, "looks good now"),
        ])
        engine = WorkflowEngine(deps=deps)
        run_id = engine.start("issue #11")

        await engine.advance(run_id)
        await engine.advance(run_id)

        r1 = await engine.advance(run_id)
        assert r1.transition.kind == TransitionKind.RETRY
        state = _read_state(run_id)
        assert state["retry_count"] == 1
        assert state["prior_feedback"] == "fix the imports"

        r2 = await engine.advance(run_id)
        assert r2.stage_result is not None
        assert r2.stage_result.verdict == Verdict.APPROVED
        assert r2.transition.kind == TransitionKind.ADVANCE


# ---------------------------------------------------------------------------
# Engine tests — custom 2-stage workflow
# ---------------------------------------------------------------------------

class TestEngineCustomWorkflow:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.fixture
    def custom_workflow_dir(self, tmp_path: Path) -> Path:
        wf_dir = tmp_path / ".atelier" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "minimal.yaml").write_text(yaml.safe_dump({
            "name": "minimal",
            "version": "1.0.0",
            "description": "Two-stage implement + review workflow",
            "stages": [
                {
                    "id": "implement",
                    "persona": "coder",
                    "skill": "speckit.implement",
                    "gate_type": "auto",
                    "retry_max": 0,
                    "on_reject": "halt",
                },
                {
                    "id": "review",
                    "persona": "reviewer",
                    "skill": "speckit.implement",
                    "gate_type": "review",
                    "retry_max": 1,
                    "on_reject": "revise",
                },
            ],
        }), encoding="utf-8")
        return wf_dir

    @pytest.mark.asyncio
    async def test_custom_workflow_runs_to_completion(
        self, custom_workflow_dir: Path,
    ) -> None:
        deps = _make_deps(reviewer_verdicts=[(Verdict.APPROVED, "all good")])
        engine = WorkflowEngine(deps=deps, user_workflows_dir=custom_workflow_dir)
        run_id = engine.start("issue #99", workflow_name="minimal")

        r1 = await engine.advance(run_id)
        assert r1.transition.kind == TransitionKind.ADVANCE
        assert r1.stage_result is not None
        assert r1.stage_result.verdict == Verdict.APPROVED

        r2 = await engine.advance(run_id)
        assert r2.transition.kind == TransitionKind.DONE
        assert r2.run_status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_custom_workflow_retry_then_pass(
        self, custom_workflow_dir: Path,
    ) -> None:
        deps = _make_deps(reviewer_verdicts=[
            (Verdict.NEEDS_REVISION, "needs work"),
            (Verdict.APPROVED, "fixed"),
        ])
        engine = WorkflowEngine(deps=deps, user_workflows_dir=custom_workflow_dir)
        run_id = engine.start("issue #99", workflow_name="minimal")

        await engine.advance(run_id)

        r1 = await engine.advance(run_id)
        assert r1.transition.kind == TransitionKind.RETRY

        r2 = await engine.advance(run_id)
        assert r2.transition.kind == TransitionKind.DONE
        assert r2.run_status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_custom_workflow_exhausted_retries_escalates(
        self, custom_workflow_dir: Path,
    ) -> None:
        deps = _make_deps(reviewer_verdicts=[
            (Verdict.NEEDS_REVISION, "still bad"),
            (Verdict.NEEDS_REVISION, "still bad"),
        ])
        engine = WorkflowEngine(deps=deps, user_workflows_dir=custom_workflow_dir)
        run_id = engine.start("issue #99", workflow_name="minimal")

        await engine.advance(run_id)

        r1 = await engine.advance(run_id)
        assert r1.transition.kind == TransitionKind.RETRY

        r2 = await engine.advance(run_id)
        assert r2.transition.kind == TransitionKind.COUNCIL
        assert r2.run_status == RunStatus.WAITING_COUNCIL

    @pytest.mark.asyncio
    async def test_council_resume_resets_retry_count(
        self, custom_workflow_dir: Path,
    ) -> None:
        deps = _make_deps(reviewer_verdicts=[
            (Verdict.NEEDS_REVISION, "bad"),
            (Verdict.NEEDS_REVISION, "still bad"),
            (Verdict.APPROVED, "ok after council"),
        ])
        engine = WorkflowEngine(deps=deps, user_workflows_dir=custom_workflow_dir)
        run_id = engine.start("issue #100", workflow_name="minimal")

        await engine.advance(run_id)
        await engine.advance(run_id)
        r_council = await engine.advance(run_id)
        assert r_council.run_status == RunStatus.WAITING_COUNCIL

        r_after = await engine.resume(run_id, approved=True)

        state = _read_state(run_id)
        assert state["retry_count"] == 0

        assert r_after.stage_result is not None
        assert r_after.stage_result.verdict == Verdict.APPROVED
        assert r_after.transition.kind == TransitionKind.DONE


# ---------------------------------------------------------------------------
# Approval gate blocks advancement until explicit approval
# Uses a non-destructive skill name to isolate gate behavior from policy.
# ---------------------------------------------------------------------------

class TestApprovalGate:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.fixture
    def approval_workflow_dir(self, tmp_path: Path) -> Path:
        wf_dir = tmp_path / ".atelier" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "approval-check.yaml").write_text(yaml.safe_dump({
            "name": "approval-check",
            "version": "1.0.0",
            "stages": [
                {
                    "id": "gated-stage",
                    "persona": "coder",
                    "skill": "safe-skill",
                    "gate_type": "approval",
                    "retry_max": 0,
                    "on_reject": "halt",
                },
            ],
        }), encoding="utf-8")
        return wf_dir

    @pytest.mark.asyncio
    async def test_approval_gate_blocks_after_execution(
        self, approval_workflow_dir: Path,
    ) -> None:
        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=approval_workflow_dir)
        run_id = engine.start("issue #1", workflow_name="approval-check")

        result = await engine.advance(run_id)
        assert result.run_status == RunStatus.WAITING_APPROVAL
        assert result.transition.kind == TransitionKind.WAITING_APPROVAL
        assert result.stage_result is not None

        state = _read_state(run_id)
        assert state["status"] == "waiting_approval"
        assert state["waiting_reason"] == "gate"

    @pytest.mark.asyncio
    async def test_approval_gate_does_not_advance_on_repeated_advance(
        self, approval_workflow_dir: Path,
    ) -> None:
        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=approval_workflow_dir)
        run_id = engine.start("issue #1", workflow_name="approval-check")

        await engine.advance(run_id)

        result = await engine.advance(run_id)
        assert result.run_status == RunStatus.WAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_resume_without_approval_stays_blocked(
        self, approval_workflow_dir: Path,
    ) -> None:
        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=approval_workflow_dir)
        run_id = engine.start("issue #1", workflow_name="approval-check")
        await engine.advance(run_id)

        result = await engine.resume(run_id, approved=False)
        assert result.run_status == RunStatus.WAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_resume_with_approval_completes(
        self, approval_workflow_dir: Path,
    ) -> None:
        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=approval_workflow_dir)
        run_id = engine.start("issue #1", workflow_name="approval-check")
        await engine.advance(run_id)

        result = await engine.resume(run_id, approved=True)
        assert result.run_status == RunStatus.COMPLETED
        assert result.transition.kind == TransitionKind.DONE

    @pytest.mark.asyncio
    async def test_approval_gate_multi_stage_advances_after_approval(
        self, tmp_path: Path,
    ) -> None:
        wf_dir = tmp_path / ".atelier" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "two-with-gate.yaml").write_text(yaml.safe_dump({
            "name": "two-with-gate",
            "version": "1.0.0",
            "stages": [
                {"id": "build", "persona": "coder", "skill": "safe-skill", "gate_type": "approval"},
                {"id": "deploy", "persona": "coder", "skill": "safe-skill"},
            ],
        }), encoding="utf-8")

        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=wf_dir)
        run_id = engine.start("issue #2", workflow_name="two-with-gate")

        r1 = await engine.advance(run_id)
        assert r1.run_status == RunStatus.WAITING_APPROVAL

        r2 = await engine.resume(run_id, approved=True)
        assert r2.transition.kind == TransitionKind.ADVANCE
        assert r2.run_status == RunStatus.RUNNING

        r3 = await engine.advance(run_id)
        assert r3.transition.kind == TransitionKind.DONE
        assert r3.run_status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Policy gating before destructive stages
# ---------------------------------------------------------------------------

class TestPolicyGating:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.fixture
    def destructive_workflow_dir(self, tmp_path: Path) -> Path:
        wf_dir = tmp_path / ".atelier" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "with-cleanup.yaml").write_text(yaml.safe_dump({
            "name": "with-cleanup",
            "version": "1.0.0",
            "stages": [
                {"id": "implement", "persona": "coder", "skill": "speckit.implement"},
                {"id": "cleanup", "persona": "coder", "skill": "cleanup-worktree"},
            ],
        }), encoding="utf-8")
        return wf_dir

    @pytest.mark.asyncio
    async def test_policy_blocks_destructive_stage(
        self, destructive_workflow_dir: Path,
    ) -> None:
        engine = WorkflowEngine(
            deps=_make_deps(),
            user_workflows_dir=destructive_workflow_dir,
        )
        run_id = engine.start("issue #3", workflow_name="with-cleanup")

        r1 = await engine.advance(run_id)
        assert r1.transition.kind == TransitionKind.ADVANCE

        r2 = await engine.advance(run_id)
        assert r2.run_status == RunStatus.WAITING_APPROVAL
        assert "policy" in _read_state(run_id).get("waiting_reason", "")

    @pytest.mark.asyncio
    async def test_policy_approval_allows_execution(
        self, destructive_workflow_dir: Path,
    ) -> None:
        engine = WorkflowEngine(
            deps=_make_deps(),
            user_workflows_dir=destructive_workflow_dir,
        )
        run_id = engine.start("issue #3", workflow_name="with-cleanup")

        await engine.advance(run_id)
        await engine.advance(run_id)

        result = await engine.resume(run_id, approved=True)
        assert result.run_status == RunStatus.COMPLETED
        assert result.transition.kind == TransitionKind.DONE

    @pytest.mark.asyncio
    async def test_policy_resume_without_approval_stays_blocked(
        self, destructive_workflow_dir: Path,
    ) -> None:
        engine = WorkflowEngine(
            deps=_make_deps(),
            user_workflows_dir=destructive_workflow_dir,
        )
        run_id = engine.start("issue #3", workflow_name="with-cleanup")
        await engine.advance(run_id)
        await engine.advance(run_id)

        result = await engine.resume(run_id, approved=False)
        assert result.run_status == RunStatus.WAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_default_policy_enforces_on_destructive_stage(
        self, destructive_workflow_dir: Path,
    ) -> None:
        engine = WorkflowEngine(
            deps=_make_deps(),
            user_workflows_dir=destructive_workflow_dir,
        )
        run_id = engine.start("issue #3", workflow_name="with-cleanup")

        await engine.advance(run_id)
        result = await engine.advance(run_id)
        assert result.run_status == RunStatus.WAITING_APPROVAL
        assert "policy" in _read_state(run_id).get("waiting_reason", "")

    @pytest.mark.asyncio
    async def test_policy_checks_skill_name_not_just_stage_id(
        self, tmp_path: Path,
    ) -> None:
        wf_dir = tmp_path / ".atelier" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "rebase-test.yaml").write_text(yaml.safe_dump({
            "name": "rebase-test",
            "version": "1.0.0",
            "stages": [
                {"id": "my-rebase", "persona": "coder", "skill": "rebase-before-pr"},
            ],
        }), encoding="utf-8")

        engine = WorkflowEngine(
            deps=_make_deps(),
            user_workflows_dir=wf_dir,
        )
        run_id = engine.start("issue #4", workflow_name="rebase-test")

        result = await engine.advance(run_id)
        assert result.run_status == RunStatus.WAITING_APPROVAL
        assert "policy" in _read_state(run_id).get("waiting_reason", "")


# ---------------------------------------------------------------------------
# Idempotency under concurrent advance()
# ---------------------------------------------------------------------------

class TestIdempotency:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.fixture
    def two_stage_dir(self, tmp_path: Path) -> Path:
        wf_dir = tmp_path / ".atelier" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "two-stage.yaml").write_text(yaml.safe_dump({
            "name": "two-stage",
            "version": "1.0.0",
            "stages": [
                {"id": "implement", "persona": "coder", "skill": "s"},
                {"id": "review", "persona": "reviewer", "skill": "s"},
            ],
        }), encoding="utf-8")
        return wf_dir

    @pytest.mark.asyncio
    async def test_concurrent_advance_single_instance_no_duplicates(
        self, two_stage_dir: Path, tmp_path: Path,
    ) -> None:
        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=two_stage_dir)
        run_id = engine.start("issue #5", workflow_name="two-stage")

        await asyncio.gather(
            engine.advance(run_id),
            engine.advance(run_id),
        )

        run_path = tmp_path / ".atelier" / "runs" / run_id / "stages"
        stage_dirs = sorted(p.name for p in run_path.iterdir() if p.is_dir())
        slugs = [d.split("-", 1)[1] for d in stage_dirs]
        dupes = {s: c for s, c in Counter(slugs).items() if c > 1}
        assert not dupes, f"duplicate stage slugs: {dupes} from {stage_dirs}"

    @pytest.mark.asyncio
    async def test_concurrent_advance_two_instances_no_duplicates(
        self, two_stage_dir: Path, tmp_path: Path,
    ) -> None:
        engine_a = WorkflowEngine(deps=_make_deps(), user_workflows_dir=two_stage_dir)
        engine_b = WorkflowEngine(deps=_make_deps(), user_workflows_dir=two_stage_dir)
        run_id = engine_a.start("issue #6", workflow_name="two-stage")

        await asyncio.gather(
            engine_a.advance(run_id),
            engine_b.advance(run_id),
        )

        run_path = tmp_path / ".atelier" / "runs" / run_id / "stages"
        stage_dirs = sorted(p.name for p in run_path.iterdir() if p.is_dir())
        slugs = [d.split("-", 1)[1] for d in stage_dirs]
        dupes = {s: c for s, c in Counter(slugs).items() if c > 1}
        assert not dupes, f"duplicate stage slugs: {dupes} from {stage_dirs}"

    @pytest.mark.asyncio
    async def test_contended_advance_returns_snapshot_not_new_work(
        self, two_stage_dir: Path,
    ) -> None:
        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=two_stage_dir)
        run_id = engine.start("issue #7", workflow_name="two-stage")

        results = await asyncio.gather(
            engine.advance(run_id),
            engine.advance(run_id),
        )

        stage_results_with_content = [
            r for r in results if r.stage_result is not None
        ]
        assert len(stage_results_with_content) == 1

    @pytest.mark.asyncio
    async def test_contended_snapshot_reflects_retry_not_advance(
        self, tmp_path: Path,
    ) -> None:
        wf_dir = tmp_path / ".atelier" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "review-only.yaml").write_text(yaml.safe_dump({
            "name": "review-only",
            "version": "1.0.0",
            "stages": [
                {
                    "id": "code",
                    "persona": "coder",
                    "skill": "s",
                    "gate_type": "review",
                    "retry_max": 3,
                    "on_reject": "revise",
                },
            ],
        }), encoding="utf-8")

        deps = _make_deps(reviewer_verdicts=[
            (Verdict.NEEDS_REVISION, "try again"),
            (Verdict.NEEDS_REVISION, "try again"),
        ])
        engine = WorkflowEngine(deps=deps, user_workflows_dir=wf_dir)
        run_id = engine.start("issue #9", workflow_name="review-only")

        r1 = await engine.advance(run_id)
        assert r1.transition.kind == TransitionKind.RETRY

        results = await asyncio.gather(
            engine.advance(run_id),
            engine.advance(run_id),
        )

        snapshot = next(r for r in results if r.stage_result is None)
        assert snapshot.transition.kind == TransitionKind.RETRY
        assert "retry" in snapshot.transition.reason

    @pytest.mark.asyncio
    async def test_contended_snapshot_reflects_advance_after_advance(
        self, two_stage_dir: Path,
    ) -> None:
        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=two_stage_dir)
        run_id = engine.start("issue #10", workflow_name="two-stage")

        results = await asyncio.gather(
            engine.advance(run_id),
            engine.advance(run_id),
        )

        snapshot = next(r for r in results if r.stage_result is None)
        assert snapshot.transition.kind == TransitionKind.ADVANCE
        assert "approved" in snapshot.transition.reason

    @pytest.mark.asyncio
    async def test_sequential_advance_still_progresses(
        self, two_stage_dir: Path,
    ) -> None:
        engine = WorkflowEngine(deps=_make_deps(), user_workflows_dir=two_stage_dir)
        run_id = engine.start("issue #8", workflow_name="two-stage")

        r1 = await engine.advance(run_id)
        r2 = await engine.advance(run_id)

        assert r1.stage_result is not None
        assert r2.stage_result is not None
        assert r2.run_status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Evidence pack is always produced
# ---------------------------------------------------------------------------

class TestEvidencePack:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.mark.asyncio
    async def test_stage_result_has_evidence_pack(self) -> None:
        engine = WorkflowEngine(deps=_make_deps())
        run_id = engine.start("issue #11")

        result = await engine.advance(run_id)
        assert result.stage_result is not None
        assert result.stage_result.evidence is not None
        assert isinstance(result.stage_result.evidence, EvidencePack)
        assert result.stage_result.evidence.verdict == Verdict.APPROVED

    @pytest.mark.asyncio
    async def test_evidence_produced_on_review_stage(self) -> None:
        deps = _make_deps(reviewer_verdicts=[(Verdict.NEEDS_REVISION, "fix it")])
        engine = WorkflowEngine(deps=deps)
        run_id = engine.start("issue #11")
        await engine.advance(run_id)
        await engine.advance(run_id)

        result = await engine.advance(run_id)
        assert result.stage_result is not None
        assert isinstance(result.stage_result.evidence, EvidencePack)
        assert result.stage_result.evidence.verdict == Verdict.NEEDS_REVISION

    @pytest.mark.asyncio
    async def test_evidence_writer_called_for_every_stage(self) -> None:
        deps = _make_deps()
        engine = WorkflowEngine(deps=deps)
        run_id = engine.start("issue #11")

        await engine.advance(run_id)
        await engine.advance(run_id)

        writer = deps.evidence_writer
        assert len(writer.calls) == 2


# ---------------------------------------------------------------------------
# Skill name passed to persona caller
# ---------------------------------------------------------------------------

class TestSkillPassthrough:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.mark.asyncio
    async def test_persona_caller_receives_skill_name(self) -> None:
        deps = _make_deps()
        engine = WorkflowEngine(deps=deps)
        run_id = engine.start("issue #11")

        await engine.advance(run_id)

        caller = deps.persona_caller
        assert len(caller.calls) == 1
        persona_name, context, skill = caller.calls[0]
        assert persona_name == "coder"
        assert skill == "speckit.specify"

    @pytest.mark.asyncio
    async def test_each_stage_gets_its_own_skill(self) -> None:
        deps = _make_deps()
        engine = WorkflowEngine(deps=deps)
        run_id = engine.start("issue #11")

        await engine.advance(run_id)
        await engine.advance(run_id)

        caller = deps.persona_caller
        assert len(caller.calls) == 2
        assert caller.calls[0][2] == "speckit.specify"
        assert caller.calls[1][2] == "speckit.clarify"


# ---------------------------------------------------------------------------
# Resume tests
# ---------------------------------------------------------------------------

class TestResume:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.mark.asyncio
    async def test_resume_picks_up_from_cursor(self) -> None:
        engine = WorkflowEngine(deps=_make_deps())
        run_id = engine.start("issue #11")

        await engine.advance(run_id)

        result = await engine.resume(run_id)
        assert result.stage_result is not None
        assert result.transition.kind == TransitionKind.ADVANCE

        state = _read_state(run_id)
        assert state["cursor"] == 2

    @pytest.mark.asyncio
    async def test_resume_completed_run_returns_done(self) -> None:
        engine = WorkflowEngine(deps=_make_deps())
        run_id = engine.start("issue #11")

        for _ in range(20):
            result = await engine.advance(run_id)
            while result.run_status == RunStatus.WAITING_APPROVAL:
                result = await engine.resume(run_id, approved=True)
            if result.is_done:
                break

        result = await engine.resume(run_id)
        assert result.run_status == RunStatus.COMPLETED
        assert result.transition.kind == TransitionKind.DONE


# ---------------------------------------------------------------------------
# Filesystem artifacts
# ---------------------------------------------------------------------------

class TestFilesystemArtifacts:
    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.mark.asyncio
    async def test_run_directory_structure(self, tmp_path: Path) -> None:
        engine = WorkflowEngine(deps=_make_deps())
        run_id = engine.start("issue #11")
        await engine.advance(run_id)

        run_path = tmp_path / ".atelier" / "runs" / run_id
        assert run_path.is_dir()
        assert (run_path / "run.md").is_file()
        assert (run_path / "workflow_state.yaml").is_file()
        assert (run_path / "stages").is_dir()

        stages = sorted(p.name for p in (run_path / "stages").iterdir() if p.is_dir())
        assert len(stages) >= 2
        assert stages[0] == "001-specify"

        stage_path = run_path / "stages" / "001-specify"
        assert (stage_path / "packet.md").is_file()
        assert (stage_path / "transcript.jsonl").is_file()
        assert (stage_path / "evidence.md").exists()
        assert (stage_path / "evidence.json").exists()
