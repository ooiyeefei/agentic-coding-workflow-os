# Context Packet

## Objective
_Source: objective | objective | -_

Execute workflow stage 003-plan with skill speckit.plan. User context: # Demo App: Rate limit failed `POST /login` attempts

## User Story

As a demo operator, I want repeated failed sign-in attempts throttled by client IP so the demo app shows a realistic security control that can be exercised through both th

## Integration Rules
_Source: repo_rule | integration-rules | AGENTS.md_

# agentic-coding-workflow-os Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-22

## Active Technologies
- Python 3.11 + pydantic v2, python-frontmatter, pathlib, pytest, pytest-asyncio, Python standard library `subprocess`, `json`, `re`, `os` (008-uat-persona-integration)
- In-memory Pydantic models plus repo-local markdown/YAML files; subprocess evidence kept in memory for this slice (008-uat-persona-integration)
- Python 3.11 + pathlib, pydantic v2, python-ulid, pytest, pytest-asyncio, standard-library `fcntl`, existing `atelier.util.fs` helpers (007-rungraph-tree-ops)
- Filesystem-only state under `.atelier/runs/<run_id>/...` matching the roadmap's canonical storage layout (007-rungraph-tree-ops)
- Python 3.11 + Python `re` and `typing` from the standard library, plus `pytest` for validation (006-secret-redaction)
- N/A for the redaction function itself; transforms in-memory strings before persistence (006-secret-redaction)
- Python 3.11 + pydantic v2, pathlib, pytest (006-context-compiler)
- In-memory source models and markdown strings; optional filesystem paths only as provenance metadata (006-context-compiler)
- Python 3.11 + pydantic v2, python-frontmatter, pathlib, pyyaml, python-ulid, pytest (005-typed-memory-records)
- Markdown files with YAML frontmatter under `.atelier/memory/{decisions,findings,rejected_alternatives}/` (005-typed-memory-records)
- Python 3.11 + pydantic v2, pathlib, pytest (012-policy-engine)
- Filesystem JSONL audit logs under `.atelier/runs/` and `.atelier/audit/` (012-policy-engine)
- Python 3.11 + anthropic SDK, openai SDK, pydantic v2, python-frontmatter, pathlib, pytest (005-swappability-demo)
- Filesystem outputs under `demo/swap-demo-output/` and generated fixture files inside the demo workspace (005-swappability-demo)
- Python 3.11 + pydantic v2, asyncio, pathlib, python-frontmatter, pyyaml, pytest, pytest-asyncio (005-council-tiebreaker)
- Filesystem-backed council report records under `.atelier/memory/council_reports/` plus in-process Pydantic models (005-council-tiebreaker)
- Python 3.11 + pydantic v2, python-frontmatter, pathlib, pyyaml, pytest, pytest-asyncio (004-persona-library)
- Python 3.11 plus Bash for the local runner + pytest, pytest-asyncio, pathlib, subprocess, existing `atelier.compiler`, `atelier.personas`, `atelier.workflow`, `atelier.evidence`, `atelier.memory`, `atelier.adr`, and `atelier.git` modules (acw-w24)
- Temporary filesystem state under `.atelier/runs/`, `.atelier/memory/`, and `docs/adr/` inside isolated test repositories (acw-w24)

## Project Structure

```text
src/
tests/
```

## Commands

cd src && pytest && ruff check .

## Code Style

Python 3.11: Follow standard conventions

## Recent Changes
- acw-w24: Added Python 3.11 plus Bash for the local runner + pytest, pytest-asyncio, pathlib, subprocess, existing `atelier.compiler`, `atelier.personas`, `atelier.workflow`, `atelier.evidence`, `atelier.memory`, `atelier.adr`, and `atelier.git` modules
- 008-uat-persona-integration: Added Python 3.11 + pydantic v2, python-frontmatter, pathlib, pytest, pytest-asyncio, Python standard library `subprocess`, `json`, `re`, `os`
- 007-rungraph-tree-ops: Added Python 3.11 + pathlib, pydantic v2, python-ulid, pytest, pytest-asyncio, standard-library `fcntl`, existing `atelier.util.fs` helpers

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

## Demo App: Rate limit failed POST /login attempts
_Source: issue_text | w23-demo-login-rate-limit | demo/issue.md_

# Demo App: Rate limit failed `POST /login` attempts

## User Story

As a demo operator, I want repeated failed sign-in attempts throttled by client IP so the demo app shows a realistic security control that can be exercised through both the browser flow and `curl`.

## Problem

The current demo app accepts unlimited failed `POST /login` attempts. That makes the auth path too forgiving for the Phase 0 end-to-end run and gives the Reviewer very little legitimate attack surface.

## Scope

- Add rate limiting to failed `POST /login` attempts.
- Allow at most 5 failed attempts per client IP in a rolling 60-second window.
- Return `429 Too Many Requests` plus a `Retry-After` header when the limit is active.
- Keep the demo UAT path tied to the existing browser login flow and the credentials from `demo/app/.env.example`.
- For this demo only, process-local in-memory tracking is acceptable.

## Acceptance Criteria

1. For one client IP, failed login attempts 1 through 5 are processed normally; if 5 failed attempts already exist for that IP in the immediately preceding rolling 60-second window, the next `POST /login` returns `429 Too Many Requests` instead of evaluating credentials.
2. While an IP remains blocked under that rolling window, every additional `POST /login` from that IP returns `429`, and the browser flow shows a human-readable wait message instead of silently failing.
3. Every `429` response includes `Retry-After` as an integer number of seconds computed by rounding up the remaining wait until the oldest counted failed attempt ages out of the rolling 60-second window; while the IP is still blocked, the value must never be `0`.
4. Once fewer than 5 failed attempts remain for that IP in the immediately preceding rolling 60-second window, the next login attempt is processed normally, and a correct login still follows the existing happy path: `303 See Other`, session cookie set, then access to `/notes`.
5. The rate limit is UAT-able on localhost in 6 failed submissions or fewer by using the demo account email from `demo/app/.env.example` with an incorrect password.

## Clarified Constraints

- Count failed attempts only.
- A successful login resets that IP's failed-attempt bucket if the IP is not already blocked.
- The limit uses a rolling window, not a fixed-duration ban. An IP becomes eligible again as soon as the oldest counted failed attempt falls outside the last 60 seconds.
- Once an IP is blocked, even a correct password from that same IP receives `429` until the rolling window no longer contains 5 failed attempts.
- The tracked identity for this issue is the client IP observed by the app during local development. Proxy-aware behavior and trusted forwarded headers are out of scope.
- `Retry-After` rounds up fractional seconds to the next integer and stays at `1` or greater while the IP is still blocked.

## Security Considerations

- Keep the invalid-login response generic. Do not reveal whether the email exists or whether only the password was wrong.
- Preserve the current session behavior for successful logins; the change should only affect throttling around `POST /login`.
- `Retry-After` must reflect the remaining wait until the oldest counted failed attempt leaves the rolling 60-second window and must not be missing on `429` responses.
- This is a demo safeguard, not a production-grade distributed limiter. Process restart and multi-instance drift are accepted limitations for Phase 0.

## Reviewer Attack Surface

- Off-by-one behavior between the 5th and 6th failed attempt.
- `Retry-After` math at the 60-second boundary or under small clock skew.
- Localhost IP bucketing differences such as `127.0.0.1` vs `::1`.
- Per-process storage means two app instances will not share counters.

## UAT Notes

1. Start the app using `demo/app/README.md`.
2. Open `http://127.0.0.1:8000/login`.
3. Use the demo email from `demo/app/.env.example` and intentionally submit a wrong password 6 times.
4. Confirm the 6th submission is rate limited and exposes `Retry-After`.
5. Wait the indicated number of seconds, then sign in with the correct password and confirm redirect to `/notes`.

Default demo credentials today are `demo@atelier.dev` / `demo1234`, but the file in `demo/app/.env.example` remains the source of truth.

## Sample `curl` Requests

```bash
# Single failed attempt against the real login route
curl -i -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'email=demo@atelier.dev' \
  --data-urlencode 'password=wrong-password'
```

```bash
# Trigger the limit locally: attempts 1-5 should stay on the normal invalid-login path,
# attempt 6 should return 429 and include Retry-After
for i in 1 2 3 4 5 6; do
  echo "== Attempt $i =="
  curl -i -s -X POST http://127.0.0.1:8000/login \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode 'email=demo@atelier.dev' \
    --data-urlencode 'password=wrong-password' \
  | sed -n '1,12p'
done
```

```bash
# After waiting the reported Retry-After seconds, the normal login flow should work again
curl -i -c cookies.txt -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'email=demo@atelier.dev' \
  --data-urlencode 'password=demo1234'
```

## Demo App README
_Source: sample_doc | demo-app-readme | demo/app/README.md_

# Demo App
1. `cd demo/app && cp .env.example .env`
2. `uv sync`
3. `uv run uvicorn app.main:app --reload --port 8000 --env-file .env`
4. Open `http://127.0.0.1:8000/login`
5. Sign in with `demo@atelier.dev` / `demo1234` (or the values in `.env`)
6. Run tests with `uv run pytest`

## Run Worktree
_Source: worktree_ref | run_01KPT1YDEK0F9MYKW4R1VMY7XY | /home/fei/fei/code/hackathon/worktrees/run_01KPT1YDEK0F9MYKW4R1VMY7XY_

Run worktree: /home/fei/fei/code/hackathon/worktrees/run_01KPT1YDEK0F9MYKW4R1VMY7XY

## Exact Commands
_Source: exact_commands | integration-commands | -_

- `uv run pytest tests/integration -q`
- `skill=speckit.plan`
- `run_id=run_01KPT1YDEK0F9MYKW4R1VMY7XY`

## Acceptance Gate
_Source: acceptance_gate | demo-acceptance | -_

If 5 failed attempts already exist in the prior rolling 60 seconds for one IP, the next POST /login returns 429 with Retry-After
Blocked IP continues receiving 429 until fewer than 5 failed attempts remain in the prior rolling 60 seconds
Retry-After is rounded up to an integer and is never 0 while blocked
Correct credentials work again once the rolling window no longer blocks the IP and preserve the existing redirect + session-cookie flow
Local UAT can reproduce the limit within 6 failed submissions

## Provenance

| source_type | source_id | path |
| --- | --- | --- |
| objective | objective | - |
| repo_rule | integration-rules | AGENTS.md |
| issue_text | w23-demo-login-rate-limit | demo/issue.md |
| sample_doc | demo-app-readme | demo/app/README.md |
| worktree_ref | run_01KPT1YDEK0F9MYKW4R1VMY7XY | /home/fei/fei/code/hackathon/worktrees/run_01KPT1YDEK0F9MYKW4R1VMY7XY |
| exact_commands | integration-commands | - |
| acceptance_gate | demo-acceptance | - |
