from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from tests.integration.artifacts import assert_run_artifact_completeness
from tests.integration.conftest import run_repository_e2e


async def _main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    real_llm_enabled = os.getenv("SPANWEAVE_INTEGRATION_REAL_LLM", "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }
    _, result = await run_repository_e2e(
        repo_root,
        real_llm_enabled=real_llm_enabled,
    )
    artifact_files = assert_run_artifact_completeness(
        repo_root,
        result.run_id,
        result.stage_ids,
    )

    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "run_path": f".spanweave/runs/{result.run_id}",
                "stage_ids": result.stage_ids,
                "verified_artifact_files": artifact_files,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
