from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import yaml
from atelier.daemon.server import DAEMON_SECRET_HEADER, create_app
from atelier.workflow.stages import StageExecutorDeps

_TEST_SECRET = "test-daemon-secret"


def _auth_headers(secret: str = _TEST_SECRET) -> dict[str, str]:
    return {DAEMON_SECRET_HEADER: secret}


def _transport(app, *, client_host: str = "127.0.0.1") -> httpx.ASGITransport:
    return httpx.ASGITransport(app=app, client=(client_host, 8080))


class _FailingPersonaCaller:
    async def call(
        self, persona_name: str, context: str, *, skill: str, run_id: str,
    ) -> str:
        raise RuntimeError("daemon boom")


async def _wait_for_run_state(
    client: httpx.AsyncClient,
    run_id: str,
    *,
    status: str,
    waiting_reason: str | None = None,
    timeout: float = 5.0,
) -> dict[str, object]:
    deadline = asyncio.get_running_loop().time() + timeout
    last_payload: dict[str, object] | None = None
    while True:
        response = await client.get(f"/runs/{run_id}", headers=_auth_headers())
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if payload["status"] == status and (
            waiting_reason is None or payload["waiting_reason"] == waiting_reason
        ):
            return payload
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(
                f"run {run_id} did not reach status={status!r} "
                f"waiting_reason={waiting_reason!r}; last payload={last_payload}"
            )
        await asyncio.sleep(0.01)


@pytest.fixture
def approval_workflow_dir(tmp_path: Path) -> Path:
    workflow_dir = tmp_path / ".atelier" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "approval-check.yaml").write_text(
        yaml.safe_dump(
            {
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
            }
        ),
        encoding="utf-8",
    )
    return workflow_dir


def test_create_app_persists_secret_when_env_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOCAL_DAEMON_SECRET", raising=False)

    app = create_app(repo_root=tmp_path)

    secret_path = tmp_path / ".atelier" / "daemon" / "secret.txt"
    assert secret_path.is_file()
    assert secret_path.read_text(encoding="utf-8").strip() == app.state.daemon_config.shared_secret


@pytest.mark.asyncio
async def test_post_runs_creates_run_and_get_runs_returns_metadata(tmp_path: Path) -> None:
    app = create_app(repo_root=tmp_path, shared_secret=_TEST_SECRET, event_poll_interval=0.01)

    async with httpx.AsyncClient(
        transport=_transport(app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/runs",
            json={"issue_ref": "42", "context": "future plugin trigger"},
            headers=_auth_headers(),
        )
        assert created.status_code == 201
        create_payload = created.json()
        run_id = create_payload["run_id"]
        assert create_payload["issue_ref"] == "issue #42"
        assert create_payload["status"] == "running"
        assert create_payload["current_stage"] == "001-specify"

        fetched = await client.get(
            f"/runs/{run_id}",
            headers={**_auth_headers(), "Origin": "http://localhost:3000"},
        )
        assert fetched.status_code == 200
        assert fetched.headers["access-control-allow-origin"] == "http://localhost:3000"
        fetch_payload = fetched.json()
        assert fetch_payload["run_id"] == run_id
        assert fetch_payload["stages"][0]["stage_id"] == "001-specify"

        advanced_payload = await _wait_for_run_state(
            client,
            run_id,
            status="waiting_approval",
            waiting_reason="policy",
        )
        assert advanced_payload["current_stage"] == "007-rebase-analyze"


@pytest.mark.asyncio
async def test_events_stream_emits_daemon_generated_audit_event(
    tmp_path: Path,
) -> None:
    app = create_app(repo_root=tmp_path, shared_secret=_TEST_SECRET, event_poll_interval=0.01)

    async with httpx.AsyncClient(
        transport=_transport(app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/runs",
            json={"issue_ref": "42"},
            headers=_auth_headers(),
        )
        run_id = created.json()["run_id"]

        response = await client.get(
            f"/runs/{run_id}/events",
            params={"limit": 1},
            headers=_auth_headers(),
            timeout=5.0,
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: TOOL_CALL" in response.text
        assert '"tool_name":"001-specify"' in response.text


@pytest.mark.asyncio
async def test_background_failure_marks_run_failed_and_streams_failure_event(
    tmp_path: Path,
) -> None:
    failing_deps = StageExecutorDeps(
        persona_caller=_FailingPersonaCaller(),
        reviewer_caller=object(),
        evidence_writer=object(),
    )
    app = create_app(
        repo_root=tmp_path,
        shared_secret=_TEST_SECRET,
        stage_executor_deps=failing_deps,
        event_poll_interval=0.01,
    )

    async with httpx.AsyncClient(
        transport=_transport(app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/runs",
            json={"issue_ref": "42"},
            headers=_auth_headers(),
        )
        run_id = created.json()["run_id"]

        response = await client.get(
            f"/runs/{run_id}/events",
            params={"limit": 1},
            headers=_auth_headers(),
            timeout=5.0,
        )
        assert response.status_code == 200
        assert '"tool_name":"daemon-runner"' in response.text
        assert '"success":false' in response.text

        failed_payload = await _wait_for_run_state(client, run_id, status="failed")
        assert failed_payload["last_transition"] == "halt"
        assert "daemon background execution failed" in failed_payload["last_transition_reason"]
        assert failed_payload["current_stage"] == "001-specify"


@pytest.mark.asyncio
async def test_post_approve_advances_gate_waiting_run(
    tmp_path: Path,
    approval_workflow_dir: Path,
) -> None:
    app = create_app(
        repo_root=tmp_path,
        shared_secret=_TEST_SECRET,
        user_workflows_dir=approval_workflow_dir,
        event_poll_interval=0.01,
    )

    async with httpx.AsyncClient(
        transport=_transport(app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/runs",
            json={"issue_ref": "99", "workflow": "approval-check"},
            headers=_auth_headers(),
        )
        assert created.status_code == 201
        run_id = created.json()["run_id"]

        waiting_payload = await _wait_for_run_state(
            client,
            run_id,
            status="waiting_approval",
            waiting_reason="gate",
        )
        assert waiting_payload["current_stage"] == "001-gated-stage"

        approved = await client.post(f"/runs/{run_id}/approve", headers=_auth_headers())
        assert approved.status_code == 200
        payload = approved.json()
        assert payload["approved"] is True
        assert payload["run"]["run_id"] == run_id
        assert payload["run"]["status"] == "completed"
        assert payload["run"]["current_stage"] is None


@pytest.mark.asyncio
async def test_post_approve_rejects_run_that_is_not_waiting_approval(
    tmp_path: Path,
) -> None:
    app = create_app(
        repo_root=tmp_path,
        shared_secret=_TEST_SECRET,
        event_poll_interval=0.01,
        auto_advance_runs=False,
    )

    async with httpx.AsyncClient(
        transport=_transport(app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/runs",
            json={"issue_ref": "42"},
            headers=_auth_headers(),
        )
        run_id = created.json()["run_id"]

        rejected = await client.post(f"/runs/{run_id}/approve", headers=_auth_headers())
        assert rejected.status_code == 409
        assert "only waiting_approval runs can be approved" in rejected.json()["detail"]


@pytest.mark.asyncio
async def test_post_approve_rejects_policy_waiting_run(tmp_path: Path) -> None:
    app = create_app(repo_root=tmp_path, shared_secret=_TEST_SECRET, event_poll_interval=0.01)

    async with httpx.AsyncClient(
        transport=_transport(app),
        base_url="http://testserver",
    ) as client:
        created = await client.post(
            "/runs",
            json={"issue_ref": "42"},
            headers=_auth_headers(),
        )
        run_id = created.json()["run_id"]

        await _wait_for_run_state(
            client,
            run_id,
            status="waiting_approval",
            waiting_reason="policy",
        )

        rejected = await client.post(f"/runs/{run_id}/approve", headers=_auth_headers())
        assert rejected.status_code == 409
        assert "only completed gate waits can be approved" in rejected.json()["detail"]


@pytest.mark.asyncio
async def test_daemon_requires_secret_and_loopback_client(tmp_path: Path) -> None:
    app = create_app(repo_root=tmp_path, shared_secret=_TEST_SECRET, event_poll_interval=0.01)

    async with httpx.AsyncClient(
        transport=_transport(app),
        base_url="http://testserver",
    ) as local_client:
        missing_secret = await local_client.get("/runs/run_bad")
        assert missing_secret.status_code == 401

    async with httpx.AsyncClient(
        transport=_transport(app, client_host="10.0.0.8"),
        base_url="http://testserver",
    ) as remote_client:
        non_loopback = await remote_client.get("/runs/run_bad", headers=_auth_headers())
        assert non_loopback.status_code == 403
