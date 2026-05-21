from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from spanweave.adr import synthesize_adr
from spanweave.compiler import (
    AcceptanceGate,
    ExactCommands,
    IssueText,
    Objective,
    RepoRule,
    SampleDoc,
    Source,
    WorktreeRef,
    compile_packet,
)
from spanweave.evidence import CommandOutput, EvidencePack, Finding, Severity, Verdict, generate
from spanweave.git import analyze_rebase, cleanup_run_worktrees, create_worktree
from spanweave.llm import (
    AnthropicAdapter,
    CapabilityManifest,
    CapabilityRequirements,
    LLMAdapter,
    Message,
    OpenAIAdapter,
    Response,
    load_capability_manifests,
    route_persona_to_model,
)
from spanweave.memory import Decision, RejectedAlternative, WorkflowEvent, write_record
from spanweave.personas import UAT, Coder, Reviewer
from spanweave.personas.base import DEFAULT_MODEL_DIR, load_persona_definition
from spanweave.personas.uat_runner import UATRequest, load_env_file
from spanweave.rungraph import list_stages
from spanweave.util.fs import atomic_write
from spanweave.util.paths import run_dir
from spanweave.workflow import RunStatus, WorkflowEngine, load_workflow
from spanweave.workflow.stages import PersonaCallResult, StageExecutorDeps
from ulid import ULID

_SOURCE_ROOT = Path(__file__).resolve().parents[2]
_VERDICT_RE = re.compile(r"VERDICT:\s*(APPROVED|NEEDS_REVISION|REJECTED)\b")


def _bool_from_env(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def ensure_main_ref(repo_root: Path) -> None:
    """Ensure a local ``main`` branch ref exists before worktree ops.

    GitHub Actions checks out a PR branch as the local HEAD without creating
    a local ``main`` ref, so ``git worktree add ... main`` (which the harness
    hard-codes via ``create_worktree``'s default ``base_branch="main"``) fails
    on every PR with ``fatal: invalid reference: main``. On checkouts of main
    itself the probe short-circuits and this is a no-op.
    """
    probe = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/main"],
        check=False,
        cwd=repo_root,
    )
    if probe.returncode == 0:
        return
    create = subprocess.run(
        ["git", "branch", "main", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if create.returncode != 0:
        raise RuntimeError(
            f"could not create 'main' ref in {repo_root}: {create.stderr.strip()}"
        )


def _mock_manifest(model: str) -> CapabilityManifest:
    return CapabilityManifest.model_validate(
        {
            "provider": "mock",
            "model": model,
            "offers": {
                "tool_use": True,
                "parallel_tool_use": True,
                "long_context": 200000,
                "code_execution": True,
                "structured_outputs": True,
            },
            "cost_per_mtok_in": 0.0,
            "cost_per_mtok_out": 0.0,
        }
    )


def _build_real_adapter(
    requirements: CapabilityRequirements,
    *,
    skip_on_missing_credentials: bool = True,
) -> LLMAdapter:
    manifests = load_capability_manifests(DEFAULT_MODEL_DIR)
    available = [
        manifest
        for manifest in manifests
        if (
            manifest.provider == "openai" and os.getenv("OPENAI_API_KEY")
        ) or (
            manifest.provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY")
        )
    ]
    if not available:
        message = (
            "SPANWEAVE_INTEGRATION_REAL_LLM=1 was set, but no matching provider credentials "
            "were available."
        )
        if not skip_on_missing_credentials:
            raise RuntimeError(message)
        pytest.skip(
            message
        )

    selected = route_persona_to_model(
        requirements,
        sorted(available, key=lambda manifest: (manifest.cost_per_mtok_in, manifest.model)),
    )
    if selected.provider == "openai":
        return OpenAIAdapter(selected)
    if selected.provider == "anthropic":
        return AnthropicAdapter(selected)
    raise AssertionError(f"Unsupported provider for integration adapter: {selected.provider}")


def _mock_coder_response(messages: list[Message]) -> str:
    user_message = messages[-1].content
    match = re.search(r"Recommended next command:\s*(/\S+)", user_message)
    recommended = match.group(1) if match else "/speckit.specify"
    if "cleanup-worktree" in user_message:
        return "Confirmed the cleanup preconditions and removed the run worktree."
    if "rebase-before-pr" in user_message:
        return "Summarized the mutation-free rebase analysis for human approval."
    return (
        f"Next command: {recommended}\n"
        "The packet is actionable, the stage can proceed, and the filesystem artifacts "
        "should be written for replay."
    )


def _mock_reviewer_response(messages: list[Message]) -> str:
    del messages
    return (
        "VERDICT: APPROVED\n"
        "Command: uv run pytest tests/integration -q\n"
        "Output: mock integration verification passed without findings."
    )


def _mock_uat_response(messages: list[Message]) -> str:
    del messages
    return (
        "1. Open /login.\n"
        "2. Submit invalid credentials enough times to trigger the limiter.\n"
        "3. Confirm the visible wait message and Retry-After guidance."
    )


class MockAdapter(LLMAdapter):
    def __init__(
        self,
        manifest: CapabilityManifest,
        response_factory: Callable[[list[Message]], str],
    ) -> None:
        super().__init__(manifest)
        self._response_factory = response_factory
        self.calls: list[list[Message]] = []

    async def generate(
        self,
        messages: list[Message],
        tools: list[Any] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
        *,
        run_id: str | None = None,
        policy: Any = None,
    ) -> Response:
        self.ensure_supported(required_capabilities)
        self.enforce_cost_policy(messages, tools, run_id=run_id, policy=policy)
        self.calls.append(messages)
        content = self._response_factory(messages)
        return self.build_response(
            response_id="integration-mock",
            content=content,
            tool_calls=[],
            stop_reason="completed",
            input_tokens=self.estimate_input_tokens(messages, tools),
            output_tokens=max(len(content) // 4, 1),
        )


@dataclass(frozen=True)
class IntegrationWorkspace:
    source_root: Path
    repo_root: Path
    demo_issue_path: Path
    demo_meta_path: Path
    demo_app_path: Path
    issue_text: str
    issue_meta: dict[str, Any]
    demo_credentials: dict[str, str]


@dataclass(frozen=True)
class WorkflowRunResult:
    run_id: str
    stage_ids: list[str]
    approval_reasons: list[str]
    adr_paths: list[Path]
    removed_worktrees: list[Path]
    rebase_reports: list[str]


@dataclass
class IntegrationHarness:
    workspace: IntegrationWorkspace
    persona_mode: str
    coder_persona: Coder
    reviewer_persona: Reviewer
    uat_persona: UAT
    cleanup_paths: list[Path] = field(default_factory=lambda: [])
    rebase_reports: list[str] = field(default_factory=lambda: [])
    stage_record_ids: dict[str, str] = field(default_factory=lambda: {})
    worktree_path: Path | None = None
    _rejected_written: bool = False
    persona_caller: _HarnessPersonaCaller = field(init=False)
    reviewer_caller: _HarnessReviewerCaller = field(init=False)
    evidence_writer: _HarnessEvidenceWriter = field(init=False)
    deps: StageExecutorDeps = field(init=False)

    def __post_init__(self) -> None:
        self.persona_caller = _HarnessPersonaCaller(self)
        self.reviewer_caller = _HarnessReviewerCaller(self)
        self.evidence_writer = _HarnessEvidenceWriter(self)
        self.deps = StageExecutorDeps(
            persona_caller=self.persona_caller,
            reviewer_caller=self.reviewer_caller,
            evidence_writer=self.evidence_writer,
        )

    def attach_run(self, run_id: str) -> None:
        if self.worktree_path is not None:
            return
        self.worktree_path = create_worktree(run_id, repo_root=self.workspace.repo_root)

    def stage_path(self, run_id: str, stage_id: str) -> Path:
        return self.workspace.repo_root / run_dir(run_id) / "stages" / stage_id

    def current_stage_id(self, run_id: str) -> str:
        stages = list_stages(run_id)
        if not stages:
            raise AssertionError(f"run {run_id} has no created stages")
        return stages[-1]

    def stage_record_id(self, stage_id: str) -> str:
        return self.stage_record_ids.setdefault(stage_id, f"stage_{ULID()}")

    def read_state(self, run_id: str) -> dict[str, Any]:
        state_path = self.workspace.repo_root / run_dir(run_id) / "workflow_state.yaml"
        payload = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AssertionError(f"invalid workflow state payload for {run_id}")
        return cast("dict[str, Any]", payload)

    def build_packet(self, run_id: str, stage_id: str, skill: str, context: str) -> str:
        readme_text = (self.workspace.demo_app_path / "README.md").read_text(encoding="utf-8")
        sources: list[Source] = [
            RepoRule(
                source_id="integration-rules",
                priority="must",
                title="Integration Rules",
                content=(self.workspace.repo_root / "AGENTS.md").read_text(encoding="utf-8"),
                path="AGENTS.md",
            ),
            IssueText(
                source_id=str(self.workspace.issue_meta["id"]),
                priority="must",
                title=str(self.workspace.issue_meta["title"]),
                content=self.workspace.issue_text,
                path=str(self.workspace.demo_issue_path.relative_to(self.workspace.repo_root)),
            ),
            SampleDoc(
                source_id="demo-app-readme",
                priority="should",
                title="Demo App README",
                content=readme_text,
                path="demo/app/README.md",
            ),
            ExactCommands(
                source_id="integration-commands",
                priority="nice",
                title="Exact Commands",
                content=(
                    "- `uv run pytest tests/integration -q`\n"
                    f"- `skill={skill}`\n"
                    f"- `run_id={run_id}`"
                ),
            ),
            AcceptanceGate(
                source_id="demo-acceptance",
                priority="nice",
                title="Acceptance Gate",
                content="\n".join(
                    cast("list[str]", self.workspace.issue_meta["acceptance_checks"])
                ),
            ),
        ]
        if self.worktree_path is not None:
            sources.append(
                WorktreeRef(
                    source_id=run_id,
                    priority="should",
                    title="Run Worktree",
                    content=f"Run worktree: {self.worktree_path}",
                    path=str(self.worktree_path),
                )
            )

        packet = compile_packet(
            Objective(
                content=(
                    f"Execute workflow stage {stage_id} with skill {skill}. "
                    f"User context: {context[:240]}"
                )
            ),
            sources,
            budget_tokens=20000,
        )
        atomic_write(self.stage_path(run_id, stage_id) / "packet.md", packet.body)
        return packet.body

    def append_transcript(
        self,
        run_id: str,
        stage_id: str,
        *,
        persona: str,
        skill: str,
        content: str,
    ) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "persona": persona,
            "skill": skill,
            "content": content,
        }
        transcript_path = self.stage_path(run_id, stage_id) / "transcript.jsonl"
        with transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def build_uat_request(self) -> UATRequest:
        return UATRequest(
            app_path=str(self.workspace.demo_app_path),
            test_user=self.workspace.demo_credentials["TEST_USER"],
            test_password=self.workspace.demo_credentials["TEST_PASSWORD"],
            notes="Integration harness execution against copied demo app fixture.",
        )

    def build_evidence_pack(
        self,
        stage_id: str,
        verdict: Verdict,
        persona_result: PersonaCallResult,
    ) -> EvidencePack:
        existing_pack = persona_result.evidence_pack()
        if existing_pack is not None:
            return existing_pack if existing_pack.verdict == verdict else existing_pack.model_copy(
                update={"verdict": verdict}
            )

        content = persona_result.content
        findings: list[Finding] = []
        if verdict != Verdict.APPROVED:
            findings.append(
                Finding(
                    finding_id="integration-review",
                    severity=Severity.ORANGE,
                    description="Review stage did not approve the integration artifact.",
                    file="tests/integration",
                    verification=content,
                )
            )

        return EvidencePack(
            verdict=verdict,
            confidence=0.95,
            summary=f"{stage_id} completed with {verdict.value}",
            findings=findings,
            execution=[
                CommandOutput(
                    command=f"integration-stage {stage_id}",
                    stdout=content,
                    stderr="",
                    exit_code=0 if verdict == Verdict.APPROVED else 1,
                    finding_ids=[finding.finding_id for finding in findings],
                )
            ],
            audit_chain=[str(ULID())],
            timestamp=datetime.now(UTC),
            reviewer_persona_id="reviewer.integration",
        )

    def write_memory_records(self, run_id: str, stage_id: str) -> None:
        tags = ["workflow-validation", stage_id.split("-", 1)[1]]
        # Auto-stub records are now WorkflowEvent (not Decision) per fix #72.
        # These are audit-trail and excluded from resume packets.
        event = WorkflowEvent(
            run_id=run_id,
            stage_id=self.stage_record_id(stage_id),
            tags=tags,
            confidence=0.9,
            source="integration-harness",
            body=(
                f"# Persist workflow evidence for {stage_id}\n\n"
                f"The {stage_id} stage stores packet, transcript, and evidence artifacts "
                "directly on disk for replay and inspection.\n\n"
                "* Good, because integration tests can assert on durable filesystem outputs\n"
                "* Bad, because each workflow run leaves behind more generated artifacts\n"
            ),
        )
        write_record(event)

        # Simulate a real persona-emitted Decision for substantive stages
        # (implement/specify/plan). ADR synthesis requires real Decisions.
        if stage_id.endswith("implement") and not self._rejected_written:
            decision = Decision(
                run_id=run_id,
                stage_id=self.stage_record_id(stage_id),
                tags=["workflow-validation", "implement"],
                confidence=0.9,
                source="coder",
                body=(
                    "# Use typed workflow validation for integration tests\n\n"
                    "Integration tests validate the full speckit-loop by asserting "
                    "on durable filesystem outputs.\n\n"
                    "* Good, because integration tests can assert on durable filesystem outputs\n"
                    "* Bad, because each workflow run leaves behind more generated artifacts\n"
                ),
            )
            write_record(decision)

            rejected = RejectedAlternative(
                run_id=run_id,
                stage_id=self.stage_record_id(stage_id),
                tags=["workflow-validation", "artifact-minimization"],
                confidence=0.6,
                source="integration-harness",
                body=(
                    "# Keep workflow validation in memory only\n\n"
                    "A purely in-memory validation path would avoid writing packets, "
                    "transcripts, and evidence artifacts to the filesystem.\n\n"
                    "* Good, because temporary test state stays smaller and faster to clean up\n"
                    "* Bad, because replay, inspection, and ADR synthesis "
                    "lose their durable inputs\n"
                ),
            )
            write_record(rejected)
            self._rejected_written = True

    def synthesize_adrs(self, run_id: str) -> list[Path]:
        return synthesize_adr(run_id, adr_output_dir=self.workspace.repo_root / "docs" / "adr")

    async def run_full_workflow(self) -> WorkflowRunResult:
        engine = WorkflowEngine(deps=self.deps)
        run_id = engine.start(
            "issue #24",
            context=self.workspace.issue_text,
        )
        self.attach_run(run_id)

        approval_reasons: list[str] = []
        result = await engine.advance(run_id)
        while True:
            while result.run_status == RunStatus.WAITING_APPROVAL:
                approval_reasons.append(str(self.read_state(run_id).get("waiting_reason", "")))
                result = await engine.resume(run_id, approved=True)

            if result.is_done:
                break

            result = await engine.advance(run_id)

        adr_paths = self.synthesize_adrs(run_id)
        return WorkflowRunResult(
            run_id=run_id,
            stage_ids=list_stages(run_id),
            approval_reasons=approval_reasons,
            adr_paths=adr_paths,
            removed_worktrees=list(self.cleanup_paths),
            rebase_reports=list(self.rebase_reports),
        )


class _HarnessPersonaCaller:
    def __init__(self, harness: IntegrationHarness) -> None:
        self._harness = harness

    async def call(
        self,
        persona_name: str,
        context: str,
        *,
        skill: str,
        run_id: str,
    ) -> PersonaCallResult:
        stage_id = self._harness.current_stage_id(run_id)
        packet_body = self._harness.build_packet(run_id, stage_id, skill, context)
        metadata: dict[str, Any] = {}

        if skill == "rebase-before-pr":
            if self._harness.worktree_path is None:
                raise AssertionError("worktree was not attached before rebase analysis")
            report = analyze_rebase(self._harness.worktree_path, target="main")
            content = (
                f"Rebase analysis for {self._harness.worktree_path.name}: "
                f"clean={report.clean}, conflicts={len(report.files_with_conflicts)}"
            )
            self._harness.rebase_reports.append(content)
        elif skill == "cleanup-worktree":
            removed = cleanup_run_worktrees(
                run_id,
                confirm=True,
                repo_root=self._harness.workspace.repo_root,
            )
            self._harness.cleanup_paths.extend(removed)
            content = f"Removed {len(removed)} run worktree(s) for {run_id}."
        elif persona_name == "uat":
            response = await self._harness.uat_persona.respond(self._harness.build_uat_request())
            content = response.content
            evidence_pack = response.metadata.get("evidence_pack")
            if evidence_pack is not None:
                metadata["evidence_pack"] = EvidencePack.model_validate(evidence_pack)
        else:
            response = await self._harness.coder_persona.respond(packet_body)
            content = response.content

        self._harness.append_transcript(
            run_id,
            stage_id,
            persona=persona_name,
            skill=skill,
            content=content,
        )
        return PersonaCallResult(content=content, metadata=metadata)


class _HarnessReviewerCaller:
    def __init__(self, harness: IntegrationHarness) -> None:
        self._harness = harness

    async def review(self, content: str, *, run_id: str) -> tuple[Verdict, str]:
        response = await self._harness.reviewer_persona.review({"run_id": run_id, "diff": content})
        feedback = response.content
        match = _VERDICT_RE.search(feedback)
        verdict = Verdict(match.group(1)) if match else Verdict.APPROVED
        return verdict, feedback


class _HarnessEvidenceWriter:
    def __init__(self, harness: IntegrationHarness) -> None:
        self._harness = harness

    def write(
        self,
        run_id: str,
        stage_id: str,
        verdict: Verdict,
        persona_result: PersonaCallResult,
    ) -> EvidencePack:
        pack = self._harness.build_evidence_pack(stage_id, verdict, persona_result)
        generate(run_id, stage_id, pack)
        self._harness.write_memory_records(run_id, stage_id)
        return pack


def _build_coder_persona(mode: str) -> Coder:
    if mode == "real":
        definition = load_persona_definition(Coder.default_prompt_path())
        return Coder(
            adapter=_build_real_adapter(
                definition.required_capabilities,
                skip_on_missing_credentials=True,
            )
        )

    return Coder(
        adapter=MockAdapter(_mock_manifest("integration-mock-coder"), _mock_coder_response)
    )


def _build_reviewer_persona() -> Reviewer:
    return Reviewer(
        adapter=MockAdapter(
            _mock_manifest("integration-mock-reviewer"),
            _mock_reviewer_response,
        )
    )


def _fake_uat_runner(
    request: UATRequest,
    *,
    test_plan: str | None = None,
) -> EvidencePack:
    return EvidencePack(
        verdict=Verdict.APPROVED,
        confidence=1.0,
        summary="UAT: 3/3 passed",
        findings=[],
        execution=[
            CommandOutput(
                command=f"mock-uat {request.app_path}",
                stdout=test_plan or "",
                stderr="",
                exit_code=0,
                finding_ids=[],
            )
        ],
        audit_chain=[str(ULID())],
        timestamp=datetime.now(UTC),
        reviewer_persona_id="uat.integration",
    )


def _build_uat_persona() -> UAT:
    return UAT(
        adapter=MockAdapter(_mock_manifest("integration-mock-uat"), _mock_uat_response),
        runner=_fake_uat_runner,
    )


def load_integration_workspace(
    repo_root: Path,
    *,
    source_root: Path | None = None,
) -> IntegrationWorkspace:
    resolved_repo_root = repo_root.resolve()
    resolved_source_root = (source_root or resolved_repo_root).resolve()
    demo_root = resolved_repo_root / "demo"
    demo_issue_path = demo_root / "issue.md"
    demo_meta_path = demo_root / "issue.meta.yaml"
    demo_app_path = demo_root / "app"
    issue_meta = cast(
        "dict[str, Any]",
        yaml.safe_load(demo_meta_path.read_text(encoding="utf-8")),
    )
    return IntegrationWorkspace(
        source_root=resolved_source_root,
        repo_root=resolved_repo_root,
        demo_issue_path=demo_issue_path,
        demo_meta_path=demo_meta_path,
        demo_app_path=demo_app_path,
        issue_text=demo_issue_path.read_text(encoding="utf-8"),
        issue_meta=issue_meta,
        demo_credentials=load_env_file(demo_app_path / ".env.example"),
    )


def create_fixture_workspace(tmp_path: Path) -> IntegrationWorkspace:
    repo_root = tmp_path / "repo"
    demo_target = repo_root / "demo"
    repo_root.mkdir()
    shutil.copytree(_SOURCE_ROOT / "demo", demo_target)
    shutil.copy2(_SOURCE_ROOT / "AGENTS.md", repo_root / "AGENTS.md")
    shutil.copy2(_SOURCE_ROOT / "README.md", repo_root / "README.md")

    _git("init", "-b", "main", cwd=repo_root)
    _git("config", "user.email", "integration@spanweave.test", cwd=repo_root)
    _git("config", "user.name", "Spanweave Integration", cwd=repo_root)
    _git("add", ".", cwd=repo_root)
    _git("commit", "-m", "Initial integration fixture", cwd=repo_root)

    return load_integration_workspace(repo_root, source_root=_SOURCE_ROOT)


def build_integration_harness(
    workspace: IntegrationWorkspace,
    *,
    real_llm_enabled: bool,
    skip_on_missing_credentials: bool = True,
) -> IntegrationHarness:
    mode = "real" if real_llm_enabled else "mock"
    coder_persona = (
        _build_coder_persona(mode)
        if skip_on_missing_credentials
        else (
            Coder(
                adapter=_build_real_adapter(
                    load_persona_definition(Coder.default_prompt_path()).required_capabilities,
                    skip_on_missing_credentials=False,
                )
            )
            if mode == "real"
            else _build_coder_persona("mock")
        )
    )
    return IntegrationHarness(
        workspace=workspace,
        persona_mode=mode,
        coder_persona=coder_persona,
        reviewer_persona=_build_reviewer_persona(),
        uat_persona=_build_uat_persona(),
    )


async def run_repository_e2e(
    repo_root: Path,
    *,
    real_llm_enabled: bool = False,
) -> tuple[IntegrationHarness, WorkflowRunResult]:
    workspace = load_integration_workspace(repo_root, source_root=_SOURCE_ROOT)
    ensure_main_ref(workspace.repo_root)
    harness = build_integration_harness(
        workspace,
        real_llm_enabled=real_llm_enabled,
        skip_on_missing_credentials=False,
    )
    previous_cwd = Path.cwd()
    os.chdir(workspace.repo_root)
    try:
        result = await harness.run_full_workflow()
    finally:
        os.chdir(previous_cwd)
    return harness, result


@pytest.fixture
def real_llm_enabled() -> bool:
    return _bool_from_env("SPANWEAVE_INTEGRATION_REAL_LLM")


@pytest.fixture
def integration_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> IntegrationWorkspace:
    workspace = create_fixture_workspace(tmp_path)
    monkeypatch.chdir(workspace.repo_root)
    return workspace


@pytest.fixture
def integration_harness(
    integration_workspace: IntegrationWorkspace,
    real_llm_enabled: bool,
) -> IntegrationHarness:
    return build_integration_harness(
        integration_workspace,
        real_llm_enabled=real_llm_enabled,
    )


@pytest.fixture
def mock_integration_harness(
    integration_workspace: IntegrationWorkspace,
) -> IntegrationHarness:
    return build_integration_harness(
        integration_workspace,
        real_llm_enabled=False,
    )


@pytest.fixture
def workflow_stage_names() -> list[str]:
    workflow = load_workflow("speckit-loop")
    return [stage.id for stage in workflow.stages]
