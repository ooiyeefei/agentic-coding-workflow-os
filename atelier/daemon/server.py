from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path
from secrets import compare_digest, token_urlsafe

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from ulid import ULID

from atelier.evidence.schema import EvidencePack, Verdict
from atelier.util.fs import atomic_write, safe_mkdir
from atelier.workflow.stages import StageExecutorDeps

from .routes import router

DAEMON_SECRET_HEADER = "X-Atelier-Secret"
LOCAL_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$"
_LOOPBACK_ALIASES = {"localhost", "testclient"}
_DEFAULT_POLL_INTERVAL = 0.05


@dataclass(frozen=True)
class DaemonConfig:
    repo_root: Path
    shared_secret: str
    stage_executor_deps: StageExecutorDeps
    shared_secret_path: Path | None = None
    user_workflows_dir: Path | None = None
    defaults_workflows_dir: Path | None = None
    event_poll_interval: float = _DEFAULT_POLL_INTERVAL
    auto_advance_runs: bool = True


class _DaemonPersonaCaller:
    async def call(
        self, persona_name: str, context: str, *, skill: str, run_id: str,
    ) -> str:
        return (
            f"daemon-run for {run_id}\n"
            f"persona={persona_name}\n"
            f"skill={skill}\n"
            f"context={context}"
        )


class _DaemonReviewerCaller:
    async def review(self, content: str, *, run_id: str) -> tuple[Verdict, str]:
        return Verdict.APPROVED, ""


class _DaemonEvidenceWriter:
    def write(
        self, run_id: str, stage_id: str, verdict: Verdict, content: str,
    ) -> EvidencePack:
        return EvidencePack(
            verdict=verdict,
            confidence=1.0,
            summary=f"daemon evidence for {run_id}:{stage_id}",
            audit_chain=[str(ULID())],
            timestamp=datetime.now(UTC),
            reviewer_persona_id="daemon-reviewer",
        )


def default_stage_executor_deps() -> StageExecutorDeps:
    return StageExecutorDeps(
        persona_caller=_DaemonPersonaCaller(),
        reviewer_caller=_DaemonReviewerCaller(),
        evidence_writer=_DaemonEvidenceWriter(),
    )


def _secret_path(repo_root: Path) -> Path:
    return repo_root / ".atelier" / "daemon" / "secret.txt"


def _load_or_create_secret(repo_root: Path) -> tuple[str, Path]:
    path = _secret_path(repo_root)
    if path.is_file():
        secret = path.read_text(encoding="utf-8").strip()
        if secret:
            return secret, path

    secret = token_urlsafe(32)
    safe_mkdir(path.parent)
    atomic_write(path, secret + "\n")
    return secret, path


def _resolve_secret(
    repo_root: Path,
    *,
    shared_secret: str | None = None,
) -> tuple[str, Path | None]:
    explicit_secret = (shared_secret or "").strip()
    if explicit_secret:
        return explicit_secret, None

    env_secret = os.environ.get("LOCAL_DAEMON_SECRET", "").strip()
    if env_secret:
        return env_secret, None

    return _load_or_create_secret(repo_root)


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host in _LOOPBACK_ALIASES:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


async def require_loopback_client(request: Request) -> None:
    client = request.client
    host = client.host if client is not None else None
    if not _is_loopback_host(host):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="daemon only accepts loopback clients",
        )


async def require_shared_secret(
    request: Request,
    x_atelier_secret: str | None = Header(default=None, alias=DAEMON_SECRET_HEADER),
) -> None:
    config: DaemonConfig = request.app.state.daemon_config
    if x_atelier_secret is None or not compare_digest(x_atelier_secret, config.shared_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid daemon secret",
        )


def create_app(
    *,
    repo_root: str | Path = Path("."),
    shared_secret: str | None = None,
    stage_executor_deps: StageExecutorDeps | None = None,
    user_workflows_dir: Path | None = None,
    defaults_workflows_dir: Path | None = None,
    event_poll_interval: float = _DEFAULT_POLL_INTERVAL,
    auto_advance_runs: bool = True,
) -> FastAPI:
    resolved_repo_root = Path(repo_root).resolve()
    resolved_secret, secret_path = _resolve_secret(
        resolved_repo_root,
        shared_secret=shared_secret,
    )
    config = DaemonConfig(
        repo_root=resolved_repo_root,
        shared_secret=resolved_secret,
        stage_executor_deps=stage_executor_deps or default_stage_executor_deps(),
        shared_secret_path=secret_path,
        user_workflows_dir=user_workflows_dir,
        defaults_workflows_dir=defaults_workflows_dir,
        event_poll_interval=event_poll_interval,
        auto_advance_runs=auto_advance_runs,
    )

    run_tasks: dict[str, asyncio.Task[None]] = {}

    @asynccontextmanager
    async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            tasks = list(run_tasks.values())
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(
        title="Atelier Daemon",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan,
    )
    app.state.daemon_config = config
    app.state.run_tasks = run_tasks
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=LOCAL_ORIGIN_REGEX,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[DAEMON_SECRET_HEADER, "Content-Type"],
    )
    app.include_router(
        router,
        dependencies=[Depends(require_loopback_client), Depends(require_shared_secret)],
    )

    return app


__all__ = [
    "DAEMON_SECRET_HEADER",
    "DaemonConfig",
    "LOCAL_ORIGIN_REGEX",
    "create_app",
    "default_stage_executor_deps",
    "require_loopback_client",
    "require_shared_secret",
]
