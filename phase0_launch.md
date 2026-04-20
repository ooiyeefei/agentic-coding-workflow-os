# Phase 0 Launch Commands & Prompts

> **Purpose**: Paste-ready operational doc. For each of 26 worktrees in [`phase0_plan.md`](./phase0_plan.md), this file gives you:
> 1. Git commands to spawn the worktree
> 2. **Coder prompt** to paste into terminal 1 (your Coder LLM)
> 3. **Reviewer prompt** to paste into terminal 2 (your Reviewer LLM)
>
> This is Phase 0's manual stand-in for the Packet Engine + Context Compiler that Atelier will automate in Phase 2+. Dogfood it now; replace it with itself later.

## How to use

1. From the main repo checkout, run the `git worktree add` command for a worktree. Example:
   ```bash
   cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
   git worktree add ../acw-w01 -b acw-w01 main
   cd ../acw-w01
   ```
2. Open two side-by-side terminals in that worktree directory.
3. Paste the **Coder prompt** into terminal 1 (suggested: Codex, OpenAI Codex CLI, or Claude Code).
4. Paste the **Reviewer prompt** into terminal 2 (suggested: the OTHER LLM than the coder — for hackathon demos we're pairing 2 Codex instances but any pair works).
5. Work the agents through the flow: `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`.
6. After each phase, paste Reviewer feedback into Coder's terminal. Iterate until Reviewer APPROVES.
7. Disagreement between Coder and Reviewer? Ask them to debate. Don't converge until consensus. If stuck after 2 rounds, invoke the 3-agent tiebreaker (W21 peek — once built).
8. When implementation is green: `/uat-test` (for user-facing features) → `/rebase-before-pr` (analyze only — never auto-resolve) → create PR → merge.
9. After merge: `git worktree remove ../acw-w##`.

## Conventions

- **Branches**: `acw-w##` (e.g., `acw-w02`, `acw-w15`)
- **Worktree paths**: `../acw-w##/` — sibling directory of `agentic-coding-workflow-os/`, not a nested subdirectory
- **Starting base**: always `main`. Before creating any worktree: `cd <main repo>; git fetch origin; git rebase origin/main`
- **Credentials**: `.env.local` in the main repo root (gitignored). Load via `set -a; source ../../.env.local; set +a`
- **Sample docs**: `docs/samples/` in the main worktree (once we add them — see W01 and W22). Agents should search this directory for any format samples they need.

## Shared strategic context (every agent gets this)

Atelier (working name) is a **reproducibility system for AI-assisted software engineering**. Every decision traceable. Every review replayable. Every context reconstructable.

**Non-negotiable design principles** — agents steer by these, flag drift as RED:

1. **Files first, indexes second** — markdown + YAML frontmatter for all persistence. No DB in Phase 0 core.
2. **CLI is the real product**; plugins are thin surfaces.
3. **LLM-agnostic** via capability manifest matching. No hardcoded model strings.
4. **Human-in-the-loop at destructive gates** — never auto-resolve merge conflicts, never auto-push, never auto-accept council verdicts on significant changes.
5. **Steering without locking** — ship opinionated defaults; users override with explicit `reason:`. Deviations logged to audit.
6. **Parallelization as default** — workflow engine scans for parallelizable work first.
7. **Dry-run first** — every destructive action has `--dry-run`. Live execution requires explicit confirmation.
8. **Evidence over vibes** — Reviewer MUST paste real command output.
9. **MAD at gates only** — Multi-Agent Debate is expensive; reserve for disagreement escalation.

Full architecture: [`roadmap.md`](./roadmap.md). Full Phase 0 scope: [`phase0_plan.md`](./phase0_plan.md).

## Wave structure (dependency graph)

| Wave | Worktrees | Depends on |
|---|---|---|
| **0** — start now | W01, W22 | nothing |
| **1a** — after W01 | W02, W03, W05, W10, W12 | W01 |
| **1b** — short chains | W04 (+W02), W06 (+W03), W08 (+W03), W09 (+W03), W26 (+W03, W13) | Wave 1a pieces |
| **1c** | W07 (+W02, W03) | Wave 1a |
| **2** | W11 (+W04, W05, W06, W07, W08, W09), W13 (+W03, W10), W14 (+W06) | Wave 1 |
| **3** | W15 (+W11), W16 (+W15, optional — future surfaces), W18 (+W04), W19 (+W02, W04), W21 (+W02, W04) | Wave 2 |
| **Demo** | W23 (+W22), W24 (+W11, W15, W22, W23), W25 (+W24) | Wave 3 |

At any time, multiple worktrees across different waves can be running in parallel as long as each worktree's own dependencies have landed.

### Parallelizing beyond wave boundaries via the stub pattern

Some Wave 1b/2/3 worktrees depend on INTERFACES from prior waves (e.g., W04 needs `LLMAdapter` from W02), not full implementations. For these, you can parallelize beyond the wave boundary by **stubbing the interface locally**:

1. The downstream Coder writes a local Protocol/ABC matching the contract defined in `phase0_plan.md` for the upstream worktree.
2. Works against the stub until the upstream worktree merges.
3. Post-merge, swaps imports from local stub → real module in a follow-up commit.

Worktrees where stubbing is recommended (each Coder prompt below includes the stub snippet):
- **W04** → stub `LLMAdapter` from W02
- **W07** → stub `LLMAdapter` from W02 (reuse W04's stub if both run concurrently)
- **W18** → stub `Persona` base from W04 (reuse W04's if that landed)
- **W21** → stub `LLMAdapter` from W02

Without stubbing, treat wave boundaries as strict ordering: Wave 1a must merge before Wave 1b starts, etc.

---

# Wave 0 — Start immediately (no dependencies)

## W01: Repo scaffolding

**Issue**: [#1](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/1)
**Depends on**: nothing (foundation)
**Blocks**: W02, W03, W04, W05, W06, W07, W08, W09, W10, W12, W26

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w01 -b acw-w01 main
cd ../acw-w01
```

**Coder prompt**:
```
You are the Coder agent for W01 — Repo scaffolding.

GitHub issue: https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/1

Strategic context: We are building Atelier — a reproducibility system for AI-assisted software engineering. This worktree establishes the Python package foundation every other worktree (W02–W26) depends on. See ../../roadmap.md for architecture and ../../phase0_plan.md section W01 for detailed scope.

Objective: Initialize the `atelier/` Python package with full tooling so other worktrees can `from atelier import ...` from day one.

Files you own:
- pyproject.toml (uv-managed; Python 3.11+; deps: pydantic>=2, python-ulid, fastapi, sse-starlette, click (or typer), jinja2, anthropic, openai, pyyaml, python-frontmatter, httpx, python-dotenv, pytest, pytest-asyncio, ruff, pyright)
- atelier/__init__.py (version string)
- atelier/{cli,daemon,llm,workflow,personas,compiler,memory,evidence,adr,rungraph,policy,audit,git,security,council,util}/__init__.py (empty package stubs)
- Makefile (targets: install, test, lint, type, run, daemon, clean)
- ruff config + pyright config (inside pyproject.toml [tool.ruff] and [tool.pyright])
- tests/conftest.py
- .python-version
- Bootstrap `.claude/commands/` by copying speckit.*.md files from /home/fei/fei/code/tiros-hazop/yf-hazop/.claude/commands/ so all downstream worktrees have the slash commands available. (W05 will refine these into Atelier's skills library later.)

How to start:
1. Run /speckit.specify "scaffold the atelier python package with uv, full tooling, empty subpackage layout, and bootstrap .claude/commands from TIROS"
   (If /speckit.specify isn't available, read ../../.claude/commands/speckit.specify.md — bootstrapped into this worktree — or pull from https://github.com/github/spec-kit.)
2. /speckit.clarify — answer questions referencing ../../phase0_plan.md section W01 and ../../roadmap.md design principles.
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. After each phase, paste Reviewer feedback; iterate until APPROVED.
5. When green: /rebase-before-pr (analyze only), then create PR.

Acceptance criteria:
- `uv sync` succeeds
- `uv run python -m atelier --help` prints a placeholder help message
- `uv run ruff check .` returns 0 errors
- `uv run pyright` returns 0 errors (strict mode acceptable)
- `uv run pytest` reports 0 tests, 0 errors
- `ls .claude/commands/` shows all imported speckit.*.md files
- All subpackage __init__.py files exist (empty)

Credentials: not needed for this worktree.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W01 — Repo scaffolding (GitHub issue #1).

Strategic context — where we are heading:
Atelier is a reproducibility system for AI-assisted software engineering. W01 is the foundation every other worktree depends on. Getting module layout and tool config right here pays back 20× later; getting it wrong means every downstream worktree eats the tax.

Full architecture: ../../roadmap.md. Full W01 scope: ../../phase0_plan.md section W01.

Review scope: pyproject.toml, atelier/ package layout, Makefile, ruff + pyright config, .claude/commands/ bootstrap, tests scaffold.

Review guidelines (execution-mandatory — paste real output):
1. Run `uv sync` — paste output. Should succeed.
2. Run `uv run ruff check .` — paste output. Should report 0 errors.
3. Run `uv run pyright` — paste output. Should report 0 errors.
4. Run `uv run pytest` — paste output. Should report 0 tests.
5. Run `uv run python -m atelier --help` — paste output.
6. Run `uv run python -c "import atelier.cli, atelier.daemon, atelier.llm, atelier.workflow, atelier.personas, atelier.compiler, atelier.memory, atelier.evidence, atelier.adr, atelier.rungraph, atelier.policy, atelier.audit, atelier.git, atelier.security, atelier.council, atelier.util"` — paste output.
7. Run `tree atelier/ -L 2` and `ls .claude/commands/`. Confirm match to phase0_plan.md W01.

Domain findings to apply:
- If pyproject.toml includes sqlite|sqlalchemy|sqlmodel|databases|asyncpg|psycopg: flag as RED (Phase 0 is filesystem-first — roadmap.md storage philosophy)
- If any hardcoded model string appears in __init__.py or Makefile: flag as ORANGE
- If __init__.py files contain non-trivial code beyond imports/version: flag as YELLOW (should be empty placeholders)
- If .claude/commands/ is missing speckit.specify.md, speckit.clarify.md, speckit.plan.md, speckit.tasks.md, speckit.implement.md: flag as RED

Output format:
APPROVAL STATUS: [APPROVED | NEEDS REVISION | REJECTED]

Findings:
RED: [file:line | description | verification]
ORANGE: ...
YELLOW: ...

Verification (execution evidence — REQUIRED):
- uv sync: <paste>
- ruff check: <paste>
- pyright: <paste>
- pytest: <paste>
- help: <paste>
- import sweep: <paste>
- layout diff: <paste>

Confidence: [0.0–1.0]

Learnings carried (steering context — do not suggest these):
- DB primitives (all kinds). We chose files-first after 7 rounds of design.
- "Let's add X feature while we're here" — scope creep. W01 is foundation only.
- Hardcoded model strings. Always capability-manifest driven (W02).
```

---

## W22: Curated demo target app

**Issue**: [#22](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/22)
**Depends on**: nothing (parallel lane, no code deps)
**Blocks**: W23, W24

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w22 -b acw-w22 main
cd ../acw-w22
mkdir -p demo/app
```

**Coder prompt**:
```
You are the Coder agent for W22 — Curated demo target app.

GitHub issue: https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/22

Strategic context: This is the app we will dogfood Atelier against in the Phase 0 demo. It must be small enough to reason about end-to-end in 90 seconds, but complete enough that a Coder+Reviewer loop has real material to work on. See ../../phase0_plan.md Demo Scenario for how it fits.

Objective: Build a minimal Next.js (App Router, TS) or FastAPI app under `demo/app/` with:
- One auth flow (login form + session cookie, can be in-memory for demo)
- One CRUD endpoint protected by auth (e.g., /api/notes with GET/POST/DELETE)
- Existing test suite (vitest or pytest) — at least 4 tests covering auth + CRUD happy path
- README.md in demo/app/ explaining how to run locally and test account creds

Choose Next.js or FastAPI — recommend FastAPI for smaller surface area, but Next.js gives a richer demo if team has time. Decide in /speckit.clarify.

Files you own: everything under demo/app/

How to start:
1. /speckit.specify "minimal demo app with one auth flow and one protected CRUD endpoint"
2. /speckit.clarify — answer by preferring FastAPI unless team votes Next.js. Decide auth mechanism (simple session cookie is fine; no JWT overkill).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Reviewer iterations.
5. Verify by running the app locally and clicking through login + CRUD.

Acceptance criteria:
- `cd demo/app; <run command>` starts the app locally on a known port
- Login works with hardcoded test account (e.g., user: demo@atelier.dev / pass: demo1234)
- Protected endpoint rejects unauthenticated requests with 401
- Protected endpoint works after login
- All tests pass
- README explains setup + creds in 10 lines or fewer

Credentials: Create `demo/app/.env.example` with TEST_USER + TEST_PASSWORD for UAT W18 to consume.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W22 — Demo target app (GitHub issue #22).

Strategic context — where we are heading:
This app is Atelier's dogfood target for the Phase 0 demo. It needs to survive a live end-to-end run where Coder implements a new feature, Reviewer attacks it, UAT drives it through a browser, and an ADR gets generated. If the app is fragile, unrealistic, or too complex, the demo fails. Simple, robust, realistic beat.

Full plan: ../../phase0_plan.md W22.

Review scope: everything in demo/app/.

Review guidelines (execution-mandatory):
1. Start the app: paste startup command and output (no errors).
2. Run test suite. Paste output (all pass).
3. Click-through smoke test (curl the login endpoint, curl the protected endpoint without + with session cookie). Paste outputs.
4. Verify README explains setup in <=10 lines.

Domain findings to apply:
- If app depends on external services (DB, Redis, cloud APIs): flag as ORANGE — Phase 0 demo runs locally; no external infra.
- If creds are hardcoded in source (not env.example): flag as RED.
- If tests mock the auth instead of exercising the real flow: flag as ORANGE — UAT needs a real login.
- If the "obvious feature to add" isn't obvious (open demo/app/README and look for a hinted next step): flag as YELLOW.

Output format:
APPROVAL STATUS: [APPROVED | NEEDS REVISION | REJECTED]
RED/ORANGE/YELLOW: ...
Verification: startup, tests, smoke curl outputs.
Confidence: 0.0–1.0

Learnings carried:
- Demo realism matters. Synthetic toys don't land.
- Keep surface area small. UAT will run against this; complexity = demo risk.
```

---

# Wave 1a — After W01 lands (foundation consumers)

## W02: LLM Abstraction + Capability Manifest

**Issue**: [#2](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/2)
**Depends on**: W01
**Blocks**: W04, W07, W11, W19, W21

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git fetch origin && git checkout main && git pull --rebase
git worktree add ../acw-w02 -b acw-w02 main
cd ../acw-w02
set -a; source ../../.env.local; set +a
```

**Coder prompt**:
```
You are the Coder agent for W02 — LLM Abstraction + Capability Manifest (issue #2).

Strategic context: Atelier is LLM-agnostic by design. Every persona (Coder, Reviewer, UAT) must be able to run against Claude, Codex, or any model that offers the required capabilities (tool use, long context, structured outputs). This worktree defines the adapter layer that makes swappability real, not claimed. Hardcoded model strings are forbidden. See ../../roadmap.md design principles #3 + #10.

Objective: Build atelier/llm/ with pluggable LLM adapters and a capability manifest system.

Files you own:
- atelier/llm/adapter.py — abstract `LLMAdapter` class with async `generate(messages, tools, required_capabilities) -> Response`
- atelier/llm/anthropic.py — implements LLMAdapter using `anthropic` SDK
- atelier/llm/openai.py — implements LLMAdapter using `openai` SDK
- atelier/llm/capabilities.py — Pydantic model for CapabilityManifest; matcher function `route_persona_to_model(persona_requires, available_models) -> model | raises UnsupportedCapabilityError`
- .atelier/defaults/models/claude-opus-4-7.yaml, claude-sonnet-4-6.yaml, claude-haiku-4-5.yaml, gpt-5.yaml (or codex), gpt-4o-mini.yaml — each declares: offers (tool_use, parallel_tool_use, long_context, code_execution, structured_outputs), cost_per_mtok_in, cost_per_mtok_out
- tests/test_llm_adapter.py — mocked Anthropic + OpenAI tests; capability-match success + failure cases

How to start:
1. /speckit.specify "LLM adapter layer with Anthropic + OpenAI implementations and capability manifest matching"
2. /speckit.clarify — key questions: exact capability vocabulary (list), fallback behavior on capability mismatch (raise vs downgrade), cost tracking granularity (per call vs per run — prefer per call, aggregated elsewhere).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Iterate on Reviewer feedback.

Acceptance criteria:
- Unit tests call Anthropic + OpenAI with mocks, validate response shape
- Capability matcher: given persona requiring `tool_use=True, long_context=128000`, a model with `tool_use=True, long_context=200000` matches; a model with `tool_use=False` raises UnsupportedCapabilityError
- No hardcoded model strings outside .atelier/defaults/models/*.yaml
- Cost per call captured in Response object for audit log consumption (W13)

Credentials: ANTHROPIC_API_KEY, OPENAI_API_KEY from ../../.env.local.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W02 — LLM Abstraction (issue #2).

Strategic context — where we are heading:
LLM-agnosticism is Atelier's strongest moat vs incumbents (Cursor, Devin, Copilot Workspace — all vendor-locked). This worktree must prove swappability is architecturally real, not claimed. W19 will demo it by running Reviewer with Claude, then Codex, on the same input.

Full scope: ../../phase0_plan.md W02. Full roadmap: ../../roadmap.md.

Review scope: atelier/llm/, .atelier/defaults/models/, tests/test_llm_adapter.py.

Review guidelines (execution-mandatory):
1. Run scoped tests: `uv run pytest tests/test_llm_adapter.py -v` — paste output.
2. Run ruff + pyright — paste output.
3. Run capability-match unit tests specifically — paste output.
4. Grep for hardcoded model strings outside .atelier/defaults/: `rg -n 'claude-[a-z0-9-]+|gpt-[a-z0-9-]+|sonnet|haiku|opus' --glob '!.atelier/**' --glob '!tests/**' atelier/` — paste output. Should be empty.
5. Integration sanity (if creds available): write a 5-line script calling both adapters with a dummy prompt, paste actual LLM response. Confirms SDK wiring works.

Domain findings to apply:
- If `anthropic.Anthropic()` or `openai.OpenAI()` is instantiated at module import time (vs inside adapter class): flag as ORANGE — makes testing harder and couples import to env vars.
- If any model name is a Python string constant outside .atelier/defaults/*.yaml: flag as RED.
- If capability matcher silently downgrades (e.g., persona needs tool_use=True, model offers False, but matcher returns model anyway): flag as RED. Must raise.
- If cost tracking absent from Response: flag as ORANGE.
- If SDK-specific error types leak to caller (persona code sees anthropic.BadRequestError instead of a unified atelier error): flag as YELLOW.

Output format + verification + confidence as standard.

Learnings carried:
- Capability manifest is the enforcement mechanism for "steering without locking" at the LLM layer. Don't weaken it.
- Cost tracking is a Phase 0 policy primitive (W12 depends on accurate cost data).
- "We'll add more providers later" — yes, but the interface decision made here binds them all. Take it seriously.
```

---

## W03: ULID generator + path helpers

**Issue**: [#3](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/3)
**Depends on**: W01
**Blocks**: W06, W07, W08, W09, W11, W13, W26

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w03 -b acw-w03 main
cd ../acw-w03
```

**Coder prompt**:
```
You are the Coder agent for W03 — ULID generator + path helpers (issue #3).

Strategic context: Atelier's Run Graph is a directory tree in the filesystem, with every entity (run, stage, packet, action, evidence, decision) identified by a ULID. Lex-sortable identifiers enable time-range queries without separate timestamp columns. Same-directory atomic replacement prevents partial overwrite corruption during local writes and leaves existing destinations untouched if the final replace step fails. This worktree is foundational — many other worktrees will import these utilities.

Objective: Build atelier/util/ with ULID generation and filesystem path helpers.

Files you own:
- atelier/util/ulid.py — wrapper over `python-ulid` library; `new_run_id()`, `new_stage_id()`, `new_packet_id()`, `new_action_id()`, `new_evidence_id()`, `new_decision_id()`; each returns prefixed strings like `run_01HX...`, `stage_01HX...`
- atelier/util/paths.py — Pydantic-validated path constructors: `run_dir(run_id)`, `stage_dir(run_id, stage_seq, stage_name)` (e.g., `.atelier/runs/run_01.../stages/001-specify/`), `packet_path`, `evidence_md_path`, `evidence_json_path`, `transcript_path`, `audit_log_path`
- atelier/util/fs.py — `safe_mkdir(path)` (idempotent); `atomic_write(path, content)` (write to tmpfile in same dir, then os.replace)
- tests/test_ulid.py, tests/test_paths.py, tests/test_fs.py

How to start:
1. /speckit.specify "ULID-prefixed ID generators, validated Atelier filesystem path constructors, atomic write helpers"
2. /speckit.clarify — prefix style (run_ vs run- — prefer underscore), path separator convention (always forward slash even on Windows? — use pathlib.Path throughout).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- `new_run_id()` returns valid ULID-formatted string with `run_` prefix, lex-sorts by creation time
- Path constructors return pathlib.Path; never string concatenation
- atomic_write: a forced failure after tmpfile creation but before the final replace step leaves the destination file untouched (simulate via mock)
- 100% coverage on util/ (small surface area, test everything)

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W03 — ULID + paths (issue #3).

Strategic context: Deterministic IDs + safe filesystem ops are the substrate every other component sits on. A bug here becomes a cross-cutting bug later — run_id collisions, partial-write corruption, path-escaping issues. Test ruthlessly now.

Full scope: ../../phase0_plan.md W03. Roadmap storage philosophy: ../../roadmap.md "Storage: filesystem-first".

Review scope: atelier/util/, tests/test_ulid.py, tests/test_paths.py, tests/test_fs.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_ulid.py tests/test_paths.py tests/test_fs.py -v --cov=atelier.util` — paste output. Expect 100% coverage on util/.
2. `uv run ruff check atelier/util/` — paste output.
3. `uv run pyright atelier/util/` — paste output.
4. Write a 10-line verification script that: generates 100 ULIDs, sorts them lexicographically, confirms they equal sorted-by-generation-time order. Paste output.
5. Atomic write verification: simulate a crash mid-write (mock os.replace to raise), confirm destination file is NOT partially written. Paste output.

Domain findings to apply:
- If `os.makedirs` or `os.path.join` used instead of pathlib: flag as YELLOW (pathlib is idiomatic in 3.11+).
- If ULID prefix is encoded via string concatenation rather than a Pydantic/Enum-validated constant: flag as YELLOW.
- If atomic_write uses `open(path, 'w')` directly (non-atomic): flag as RED.
- If path constructors accept arbitrary user input without validation (path traversal via `..`): flag as RED.
- If tests use random data that isn't seeded: flag as ORANGE (non-deterministic tests).

Output format + verification + confidence as standard.

Learnings carried:
- ULID prefix convention is binding. Once data is written with `run_01HX`, retroactive changes require migrations we'd rather avoid.
- Filesystem is truth; corrupt files cascade. Favor atomicity.
```

---

## W05: Skills Library

**Issue**: [#5](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/5)
**Depends on**: W01
**Blocks**: W11

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w05 -b acw-w05 main
cd ../acw-w05
```

**Coder prompt**:
```
You are the Coder agent for W05 — Skills Library (issue #5).

Strategic context: Skills are versioned workflow specs, not bare prompts. Each skill declares inputs, expected artifacts, success checks, and next transition. This is what makes the workflow engine reliable — it has contracts to check, not just hope.

Objective: Build .atelier/defaults/skills/ with all Phase 0 skills, plus a skill loader + validator in atelier/.

Files you own:
- .atelier/defaults/skills/speckit.specify.md — IMPORT verbatim from /home/fei/fei/code/tiros-hazop/yf-hazop/.claude/commands/speckit.specify.md, add YAML frontmatter: inputs (feature description), expected_artifacts (spec.md), success_checks (spec-quality checklist passes), next_transition (speckit.clarify)
- .atelier/defaults/skills/speckit.clarify.md — same treatment for speckit.clarify
- .atelier/defaults/skills/speckit.plan.md — same for speckit.plan
- .atelier/defaults/skills/speckit.tasks.md — same for speckit.tasks
- .atelier/defaults/skills/speckit.implement.md — same for speckit.implement
- .atelier/defaults/skills/rebase-before-pr.md — AUTHOR this one. Encode the user's exact instructions: git add . → commit → git fetch origin → git rebase origin/main → ANALYZE conflicts without deciding → report with resolution suggestions → wait for human decision → git push --force-with-lease. Frontmatter: inputs (worktree path, target branch), expected_artifacts (conflict_report.md if conflicts exist), success_checks (rebase complete OR human-approved resolution applied), next_transition (cleanup-worktree). The skill MUST include this exact prompt block for the agent to follow: "First, git add . to add ALL updates and commit changes we have, then run git fetch origin and git rebase origin/main. If there is any conflict, please do not decide for me first, analyse thru all conflicts if any, report back with what are the conflicts and resolution suggestions. After rebasing, push with git push --force-with-lease <feature-branch-name>."
- .atelier/defaults/skills/cleanup-worktree.md — AUTHOR. Remove worktree after merge. Confirmation required. Frontmatter: inputs (worktree_path), expected_artifacts (none), success_checks (directory removed, branch deleted locally), next_transition (none, terminal).
- .atelier/defaults/skills/uat-test.md — AUTHOR. Stub that calls the user's existing ccc/skills/uat-testing. Frontmatter: inputs (app_path, test_account_creds_env_var), expected_artifacts (uat_report.md), success_checks (exit code 0 + report present), next_transition (rebase-before-pr).
- atelier/skills/loader.py — reads .atelier/defaults/skills/*.md, validates frontmatter schema, exposes `get_skill(name) -> Skill` to the workflow engine
- atelier/skills/schema.py — Pydantic model for skill frontmatter
- tests/test_skills.py — loads all shipped skills, validates frontmatter, checks content-length > 100 chars

How to start:
1. /speckit.specify "skills library with speckit.* imports + new atelier skills (rebase-before-pr, cleanup-worktree, uat-test) + loader + validator"
2. /speckit.clarify — frontmatter schema details (required vs optional fields), skill versioning (semver in frontmatter?), how to handle skill not found (raise vs warn).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- All 8 skills present in .atelier/defaults/skills/ with valid frontmatter
- `get_skill("rebase-before-pr")` returns a valid Skill object
- `get_skill("nonexistent")` raises SkillNotFoundError
- speckit.* skills preserve original TIROS content (diff check)
- rebase-before-pr.md contains the exact user-provided prompt block verbatim

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W05 — Skills Library (issue #5).

Strategic context: Skills are the contract language between the workflow engine and the agents. If skills are loose prompts, reliability suffers. If overly rigid, they constrain user customization. The frontmatter schema decides how strict we are — lean toward strictness for defaults, with extension points for user-authored skills.

Full scope: ../../phase0_plan.md W05. Roadmap skills: ../../roadmap.md (L0 Skills row).

Review scope: .atelier/defaults/skills/*.md, atelier/skills/, tests/test_skills.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_skills.py -v` — paste output.
2. `uv run python -c "from atelier.skills.loader import get_skill; import json; print([get_skill(n).model_dump() for n in ['speckit.specify','speckit.clarify','speckit.plan','speckit.tasks','speckit.implement','rebase-before-pr','cleanup-worktree','uat-test']])"` — paste output.
3. Diff TIROS speckit.*.md against Atelier's — `diff ../../.claude/commands/speckit.specify.md .atelier/defaults/skills/speckit.specify.md` etc. Only frontmatter additions allowed; body must match.
4. Grep for the exact rebase-before-pr prompt block: `rg -n "analyse thru all conflicts" .atelier/defaults/skills/rebase-before-pr.md` — must match.

Domain findings to apply:
- If a skill's frontmatter is missing a required field: RED.
- If rebase-before-pr auto-resolves conflicts or auto-pushes without human approval: RED. Read the skill carefully.
- If frontmatter schema allows arbitrary keys (no `extra='forbid'` on Pydantic model): ORANGE (encourages drift).
- If speckit.* body drifts from TIROS original: ORANGE (upstream compatibility).
- If uat-test skill invokes ccc/skills/uat-testing directly inline (instead of as a subprocess the workflow engine can monitor): ORANGE.

Output format + verification + confidence as standard.

Learnings carried:
- The rebase-before-pr instruction wording is exact by user intent. Don't paraphrase it. Preserve literally.
- Skills are intentionally user-overridable (Phase 3 rule precedence). Keep defaults opinionated but overridable.
```

---

## W10: Secret redaction

**Issue**: [#10](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/10)
**Depends on**: W01
**Blocks**: W13, W08 (via audit linkage)

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w10 -b acw-w10 main
cd ../acw-w10
```

**Coder prompt**:
```
You are the Coder agent for W10 — Secret redaction (issue #10).

Strategic context: Atelier persists transcripts, packets, evidence, audit logs — all of which can leak secrets if not redacted. A memory system that stores secrets is a liability. Phase 0 uses regex-based redaction (good enough for MVP). Phase 3+ will add entropy detection and pluggable redactors.

Objective: Build atelier/security/redaction.py — a pure function that takes a string, returns a redacted string, applied at every persistence boundary.

Files you own:
- atelier/security/redaction.py — `redact(text: str, extra_patterns: list[str] | None = None) -> str`
- atelier/security/patterns.py — regex patterns: .env assignments (KEY=value forms), known prefixes (sk-, pk_, ghp_, ghs_, xoxb-, xoxp-, Bearer <token>, AWS access keys AKIA..., GCP service account json headers), env var names (API_KEY, SECRET, PASSWORD, TOKEN, PRIVATE_KEY)
- tests/test_redaction.py — fixture with 30+ positive cases (real-looking secret strings) and 10+ negative cases (safe strings that must pass through unchanged)

How to start:
1. /speckit.specify "regex-based secret redactor with pluggable patterns"
2. /speckit.clarify — redaction token format (use <REDACTED> or [REDACTED:<pattern-name>] — prefer the latter for audit visibility), case sensitivity (prefer case-insensitive for env var names).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- `redact("OPENAI_API_KEY=sk-abc123xyz")` returns redacted output
- `redact("hello world")` returns "hello world" unchanged
- `redact("Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.xxx")` redacts token portion
- `redact("DATABASE_URL=postgres://user:pass@host/db")` redacts credentials, keeps URL shape visible
- All patterns tested positively + negatively
- No false positives on common English words that happen to contain pattern-adjacent characters

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W10 — Secret redaction (issue #10).

Strategic context: This function is load-bearing for Atelier's trustworthiness. A missed secret pattern = silent leak. A false positive = garbled audit logs. Error on the side of over-redacting, never under.

Full scope: ../../phase0_plan.md W10.

Review scope: atelier/security/, tests/test_redaction.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_redaction.py -v` — paste output. All tests pass.
2. Fuzz test: generate 100 random strings mixing real secret patterns with filler; count miss rate. Paste.
3. `uv run ruff check atelier/security/` — paste output.
4. Manual review of patterns.py: confirm coverage of at least { sk-, pk_, ghp_, ghs_, xoxb-, xoxp-, Bearer, AKIA, API_KEY, SECRET, PASSWORD, TOKEN, PRIVATE_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY }.

Domain findings to apply:
- If ANY pattern has an un-anchored greedy regex that could blow up on long inputs: RED (ReDoS vulnerability).
- If test fixture has real secrets (accidentally committed): RED.
- If `redact` mutates its input instead of returning a new string: ORANGE.
- If non-trivial state is used (e.g., caching compiled regexes globally without thread safety): YELLOW.
- If false positive rate on negative tests >1%: ORANGE.

Output format + verification + confidence as standard.

Learnings carried:
- Secrets in logs are a liability. Err on side of over-redacting.
- This function runs on every write to disk. Performance matters — compile patterns once, reuse.
```

---

## W12: Policy Engine

**Issue**: [#12](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/12)
**Depends on**: W01
**Blocks**: W11

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w12 -b acw-w12 main
cd ../acw-w12
```

**Coder prompt**:
```
You are the Coder agent for W12 — Policy Engine (issue #12).

Strategic context: Workflow says WHAT happens next; Policy says what is ALLOWED, what requires approval, what evidence is required, what counts as an override. Separating these prevents workflow logic from being contaminated with approval checks. Phase 0 uses hardcoded policies; Phase 3+ makes them config-driven.

Objective: Build atelier/policy/ with primitives for approval gates, dry-run defaults, and cost caps.

Files you own:
- atelier/policy/engine.py — `PolicyEngine` class with `requires_approval(stage, context) -> bool`, `is_dry_run(operation) -> bool`, `check_cost(run_id, proposed_cost) -> bool | raises CostCapExceeded`
- atelier/policy/defaults.py — Phase 0 hardcoded defaults: approval required at `rebase-before-pr` and `cleanup-worktree`; dry-run default True for all git mutate ops; cost cap $5/run, $50/day
- atelier/policy/cost_tracker.py — reads audit.jsonl (W13), sums costs per run and per day
- tests/test_policy.py

How to start:
1. /speckit.specify "policy engine with approval gates, dry-run defaults, cost caps, all hardcoded for Phase 0"
2. /speckit.clarify — cost tracking scope (per-call vs per-run — prefer per-run aggregated from W13 audit), approval UX (how policy signals "needs approval" back to orchestrator — enum return vs exception).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- `requires_approval("rebase-before-pr", ctx)` returns True
- `requires_approval("implement", ctx)` returns False
- `is_dry_run("git-rebase")` returns True (default)
- Cost cap enforcement: a run accumulating $6 when cap is $5 raises CostCapExceeded
- Tests cover: approval gates, dry-run defaults, cost cap at boundary ($4.99 vs $5.00 vs $5.01)

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W12 — Policy Engine (issue #12).

Strategic context — where we are heading:
Policy Engine is the choke point for destructive operations. Auto-approve or auto-push by accident = catastrophic. We err conservative: approvals required by default for anything destructive. Phase 3 makes these configurable; Phase 0 locks them.

Full scope: ../../phase0_plan.md W12.

Review scope: atelier/policy/, tests/test_policy.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_policy.py -v` — paste output.
2. `uv run ruff check atelier/policy/` — paste output.
3. Grep for any hardcoded bypass (e.g., `if os.getenv("SKIP_POLICY"):`) — paste result. Must be empty.
4. Confirm no network calls in policy module (`rg -n "requests|httpx|urllib" atelier/policy/`) — must be empty.

Domain findings to apply:
- If policy can be bypassed via env var: RED.
- If `is_dry_run` defaults to False for any git op: RED.
- If `requires_approval` returns False for `cleanup-worktree`: RED (worktree cleanup is destructive).
- If cost cap lookup queries a DB: RED (Phase 0 is files-only; must read audit.jsonl).
- If cost cap check is missing at LLM call sites: ORANGE — check that W02 adapters will consult policy before making a call.

Output format + verification + confidence as standard.

Learnings carried:
- We agreed: human-in-the-loop at destructive gates. Never auto-approve.
- Policy is the "steering without locking" enforcement layer. If users override, require explicit reason (Phase 3). Phase 0 logs every override attempt.
```

---

# Wave 1b — Short dependency chains

## W04: Persona Library

**Issue**: [#4](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/4)
**Depends on**: W01, W02 (partial — uses LLMAdapter interface)
**Blocks**: W11, W18, W19, W21

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w04 -b acw-w04 main
cd ../acw-w04
```

**Coder prompt**:
```
You are the Coder agent for W04 — Persona Library (issue #4).

Strategic context: Personas are capability-gated, LLM-agnostic roles. Coder implements; Reviewer attacks with execution-mandatory protocol; UAT (later) drives the app. Personas declare their required capabilities; the LLM abstraction routes to a compatible model. This is the concrete realization of "LLM-agnostic" as an architectural property.

**W02 dependency + stub pattern**: W04 imports `LLMAdapter` from W02. If W02 has NOT merged yet when you start, parallelize via the stub pattern:
1. Create `atelier/personas/_llm_proto.py` with a local `LLMAdapter` Protocol matching the W02 contract from phase0_plan.md:
   ```python
   from typing import Any, Protocol
   class LLMAdapter(Protocol):
       async def generate(self, messages: list[dict], tools: list[dict] | None = None, required_capabilities: list[str] | None = None) -> Any: ...
   ```
2. Import from this stub in your persona code.
3. When W02 PR merges to main, open a follow-up commit that swaps `from atelier.personas._llm_proto import LLMAdapter` → `from atelier.llm.adapter import LLMAdapter` and deletes the stub file.
4. If W02 has already merged when you start, skip the stub — import directly from `atelier.llm.adapter`.

Objective: Build atelier/personas/ with Coder + Reviewer personas, bound to the LLMAdapter interface (stubbed or real per above).

Files you own:
- atelier/personas/base.py — abstract Persona: `name`, `system_prompt`, `required_capabilities`, `llm_adapter_name`, async `respond(context_packet) -> AgentResponse`
- atelier/personas/coder.py — Coder persona bound to a default LLM adapter; uses skills library (W05) to know which `/speckit.*` command to issue next
- atelier/personas/reviewer.py — Reviewer persona with execution-mandatory protocol baked into system prompt. Supports `devil_advocate_mode: bool = False` (off by default). When on, Reviewer always produces an explicit "reasons to reject" section even on APPROVE verdicts.
- .atelier/defaults/personas/coder.md — system prompt (markdown), capability requirements (YAML frontmatter)
- .atelier/defaults/personas/reviewer.md — execution-mandatory system prompt (transplanted + generalized from TIROS AGENTS.md), devil-advocate optional hook
- tests/test_personas.py

How to start:
1. /speckit.specify "Coder + Reviewer personas with LLMAdapter binding and devil_advocate_mode flag (default off)"
2. /speckit.clarify — capability requirements per persona (Coder: tool_use, long_context 128k+, code_execution preferred; Reviewer: tool_use, code_execution MANDATORY, structured_outputs), default LLM mappings (hardcoded to first compatible — Phase 0 keeps it simple).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- `Coder()` instantiates and routes to a compatible model via W02's matcher
- `Reviewer()` same, with execution-mandatory protocol in system prompt
- `Reviewer(devil_advocate_mode=True)` adds "reasons to reject" section scaffolding to its prompt
- Calling `persona.respond(packet)` on both returns a structured AgentResponse (will be real when paired with actual LLM via W02)
- Reviewer system prompt passes a manual check: must mention "execute", "paste actual output", "incomplete without execution evidence"

Credentials: ANTHROPIC_API_KEY / OPENAI_API_KEY from ../../.env.local (for optional integration sanity test).
```

**Reviewer prompt**:
```
You are the Reviewer agent for W04 — Persona Library (issue #4).

Strategic context — where we are heading:
Reviewer persona's execution-mandatory protocol is Atelier's biggest pitch differentiator. Every other "AI code review" tool ships hallucination-prone verdicts; ours ships verdicts backed by real command output. If this persona's system prompt is weak, the moat evaporates.

Full scope: ../../phase0_plan.md W04. Reference discipline: TIROS AGENTS.md (source of our review protocol).

Review scope: atelier/personas/, .atelier/defaults/personas/, tests/test_personas.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_personas.py -v` — paste output.
2. Read reviewer.md system prompt. Confirm it contains phrases: "you MUST execute", "paste actual output", "incomplete without". Paste your confirmation with line numbers.
3. Instantiate Coder + Reviewer, call `.respond(fake_packet)` with a mock LLMAdapter. Paste output shape.
4. Verify devil_advocate_mode: `Reviewer(devil_advocate_mode=True).system_prompt` must differ from default — diff the two, paste.

Domain findings to apply:
- If Reviewer system prompt contains "should" instead of "MUST" for execution requirements: RED (TIROS lesson: advisory language gets ignored by LLMs).
- If devil_advocate_mode defaults to True: RED (default off per user decision).
- If LLMAdapter is instantiated in persona __init__ (tightly coupled): ORANGE — prefer dependency injection for testability.
- If no test exercises a Reviewer mis-capability route (persona requires code_execution, model offers False): RED — should raise UnsupportedCapabilityError from W02.
- If Reviewer prompt is <500 chars: probably too terse — YELLOW.

Output format + verification + confidence as standard.

Learnings carried:
- Execution-mandatory is IMPERATIVE language, not advisory. We learned this building TIROS — "should" gets ignored.
- Devil's advocate is opt-in. Don't make it default to avoid Reviewer performative negativity.
- Reviewer always attacks; never approves without verification. This is cultural + technical.
```

---

## W06: Knowledge Plane (typed records)

**Issue**: [#6](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/6)
**Depends on**: W01, W03
**Blocks**: W11, W14

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w06 -b acw-w06 main
cd ../acw-w06
```

**Coder prompt**:
```
You are the Coder agent for W06 — Knowledge Plane (issue #6).

Strategic context: Memory is typed records first, raw transcripts second. Typed records (Decision, ReviewFinding, RejectedAlternative) enable queries and derivations; transcripts preserve raw history. Filesystem-first: each record is a markdown file with YAML frontmatter — grep-able, diffable, committable.

Objective: Build atelier/memory/ with Pydantic schemas, writer, and reader for typed records.

Files you own:
- atelier/memory/records.py — Pydantic models: `Decision`, `ReviewFinding`, `RejectedAlternative`. Each has frontmatter fields (id, type, run_id, stage_id, timestamp, related_issues, related_adrs, tags, confidence, source) and a body (markdown).
- atelier/memory/writer.py — `write_record(record, path) -> Path` using atomic_write (W03) + atelier.security.redaction.redact (W10). Filename pattern: `<type>_<ulid>.md`.
- atelier/memory/reader.py — `read_record(path) -> Record`, `list_records(type, filters) -> list[Record]`. Parses frontmatter via python-frontmatter library.
- tests/test_memory.py — round-trip test: `record → write → read` preserves all fields, including markdown body formatting.

How to start:
1. /speckit.specify "typed memory records (Decision, ReviewFinding, RejectedAlternative) with frontmatter + markdown body, filesystem-first persistence"
2. /speckit.clarify — which fields are required vs optional, frontmatter format (YAML vs TOML — prefer YAML), how to handle schema evolution (Phase 0: just version field in frontmatter; no migrations yet).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- `Decision(...)` instance → `write_record()` → file exists at expected path with valid frontmatter + body
- `read_record(path)` returns an equivalent Decision (all fields match after round-trip)
- `list_records(type="Decision", tags=["safety-critical"])` filters correctly
- Redaction applied: test that writing a Decision with a body containing "OPENAI_API_KEY=sk-xxx" produces a file with redacted content

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W06 — Memory (issue #6).

Strategic context: This is Atelier's long-term memory substrate. Decisions here drive auto-ADR generation (W14), future Reviewer context queries, and eventually cross-project memory. Schema decisions here bind Atelier for years.

Full scope: ../../phase0_plan.md W06.

Review scope: atelier/memory/, tests/test_memory.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_memory.py -v` — paste output.
2. Round-trip a Decision with unicode + emoji + code fences in body; confirm byte-identical body preservation. Paste.
3. `rg -n "sqlite|sqlalchemy|sqlmodel|databases|asyncpg|psycopg" atelier/memory/` — must be empty.
4. Write a Decision; inspect the file with `cat`. Confirm frontmatter is parse-able, body is raw markdown. Paste.

Domain findings to apply:
- If ANY DB primitive imported in atelier/memory/: RED (roadmap: files-first).
- If frontmatter uses TOML or JSON (not YAML): ORANGE (YAML is the convention).
- If `write_record` doesn't apply redaction: RED (W10 must be called).
- If record schemas allow `extra='allow'` (not forbidden): ORANGE (encourages drift).
- If ULIDs aren't validated on input: YELLOW.

Output format + verification + confidence as standard.

Learnings carried:
- Typed first, transcripts second. We agreed on this after considering semantic blob memory and rejecting it.
- Redaction is non-negotiable at every persistence boundary.
```

---

## W08: Evidence Pack generator

**Issue**: [#8](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/8)
**Depends on**: W01, W03
**Blocks**: W04 (Reviewer writes via this)

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w08 -b acw-w08 main
cd ../acw-w08
```

**Coder prompt**:
```
You are the Coder agent for W08 — Evidence Pack generator (issue #8).

Strategic context: Evidence Pack is Atelier's named artifact for proof-of-execution. Dual format: JSON for machines (plugins, CI, future replay harness), Markdown for humans. Every review produces one. This is the output format we'd eventually publish as an open spec (like SARIF for static analyzers).

Objective: Build atelier/evidence/ with Pydantic EvidencePack schema, Jinja2 template for markdown rendering, and a generator that writes both.

Files you own:
- atelier/evidence/schema.py — EvidencePack Pydantic model: `verdict` (APPROVED|NEEDS_REVISION|REJECTED), `confidence` (0.0-1.0), `findings` (list of Finding: severity=RED|ORANGE|YELLOW, description, file, line, verification), `execution` (list of CommandOutput: command, stdout, stderr, exit_code), `audit_chain` (list of ULID references), `timestamp`, `reviewer_persona_id`
- atelier/evidence/templates/evidence.md.j2 — Jinja2 template rendering the above to human markdown
- atelier/evidence/generator.py — `generate(run_id, stage_id, pack: EvidencePack) -> (json_path, md_path)` — writes both to `.atelier/runs/<run_id>/stages/<stage_id>/evidence.{json,md}`
- tests/test_evidence.py — fixture EvidencePack → generate → read back JSON matches; Markdown render matches golden file.

How to start:
1. /speckit.specify "Evidence Pack with JSON + Markdown dual output"
2. /speckit.clarify — JSON schema stability (version field in JSON? Yes — `schema_version: "1.0"`), how to link execution evidence to findings (by finding_id).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- EvidencePack(verdict="REJECTED", findings=[...]) → generate() → both files exist
- JSON is valid, parses back to equivalent EvidencePack
- Markdown renders with: header, verdict banner, findings grouped by severity, execution section with code-block output, audit-chain links
- Golden-file test for markdown (stable across runs)
- Redaction applied on execution outputs (W10)

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W08 — Evidence Pack (issue #8).

Strategic context — where we are heading:
Evidence Pack is Atelier's "receipt" — the artifact that makes reviews replayable and verdicts auditable. The JSON must be machine-ingestible (plugin webview consumes, CI agents check, Phase 3 replay harness reads). The Markdown must be instantly readable to a human judge at a live demo.

Full scope: ../../phase0_plan.md W08. Inspiration: SARIF (sarifweb.azurewebsites.net).

Review scope: atelier/evidence/, tests/test_evidence.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_evidence.py -v` — paste output.
2. Generate an EvidencePack with 5 findings (mix of severities), write, then open both files. Paste JSON + rendered Markdown.
3. Validate JSON against Pydantic schema (reparse). Paste result.
4. Confirm redaction: inject an API_KEY-shaped string into a command output, verify it's redacted in both JSON and Markdown outputs.

Domain findings to apply:
- If JSON schema lacks `schema_version`: ORANGE (forward compat matters).
- If Markdown template has hardcoded styling that would break in a plain terminal viewer: YELLOW.
- If generator writes JSON after Markdown (or vice versa) without atomicity (both must succeed or neither): ORANGE.
- If redaction is NOT applied to execution.stdout/stderr: RED.
- If confidence field is unvalidated (e.g., allows 1.5): ORANGE.

Output format + verification + confidence as standard.

Learnings carried:
- Evidence Pack is a spec candidate, not just an internal artifact. Design cleanly.
- The Markdown is what judges screenshot. Make it beautiful and dense.
```

---

## W09: Run Graph file tree ops

**Issue**: [#9](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/9)
**Depends on**: W01, W03
**Blocks**: W11, W13

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w09 -b acw-w09 main
cd ../acw-w09
```

**Coder prompt**:
```
You are the Coder agent for W09 — Run Graph file tree ops (issue #9).

Strategic context: The Run Graph is a directory tree: runs/<ulid>/stages/<nnn-name>/. Each entity lives as a file. Completion markers enable idempotent resume. Lock files prevent concurrent writers. This is the durable lineage Atelier's reproducibility thesis rests on.

Objective: Build atelier/rungraph/ to create runs, create stages, mark completion, resume cleanly, lock against concurrent writes.

Files you own:
- atelier/rungraph/tree.py — `create_run(issue_ref) -> run_id`, `create_stage(run_id, stage_name) -> stage_id`, `mark_stage_complete(run_id, stage_id)`, `list_runs()`, `list_stages(run_id)`
- atelier/rungraph/cursor.py — `next_stage_to_execute(run_id) -> stage_id | None` (scans for first stage without completion marker)
- atelier/rungraph/lock.py — file-lock context manager (`with run_lock(run_id): ...`) using fcntl or portalocker
- tests/test_rungraph.py — create run, create 3 stages, complete 2, confirm resume picks up #3. Concurrent-write test attempts dual-lock, confirms second writer blocks.

How to start:
1. /speckit.specify "Run Graph filesystem ops: create runs/stages, completion markers, resume cursor, concurrent write locks"
2. /speckit.clarify — stage naming convention (sequence-prefixed: `001-specify`), how to handle orphaned partial stages on resume (treat as incomplete, restart that stage), lock file location (inside run dir: `.lock`).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- create_run + 3 create_stage calls + 2 mark_stage_complete → next_stage_to_execute returns the 3rd
- Dual lock attempt: second process blocks until first releases (test via subprocess + timeout)
- Lost-lock recovery: if a holder crashes, the lock is reclaimable (test stale-lock scenario)
- Run directory layout matches roadmap.md "Storage Philosophy" exactly

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W09 — Run Graph (issue #9).

Strategic context — where we are heading:
Run Graph is Atelier's spine. Lost integrity here = lost reproducibility. Concurrent write bugs are devastating and hard to reproduce. Resume bugs cause double-ADR writes. Test ruthlessly.

Full scope: ../../phase0_plan.md W09. Roadmap storage: ../../roadmap.md.

Review scope: atelier/rungraph/, tests/test_rungraph.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_rungraph.py -v` — paste output.
2. Concurrent-write stress test: spawn 2 subprocesses both trying to create_stage on the same run. Paste result. Second must block or return a clear error, not corrupt.
3. Crash-recovery test: kill a subprocess mid-write (os.kill with SIGKILL) while holding the lock. Confirm next process can acquire after a grace period. Paste.
4. `find .atelier -type f` after fixtures — confirm tree matches roadmap spec.

Domain findings to apply:
- If any SQLite or DB-backed locking used: RED (files-only).
- If locks use Python `threading.Lock` (process-local): RED (must be file-level for multi-process safety).
- If mark_stage_complete writes a non-atomic marker (race vulnerability): RED.
- If stale lock cleanup takes forever (no timeout): ORANGE.
- If cursor returns wrong stage when sequence numbers have gaps: YELLOW.

Output format + verification + confidence as standard.

Learnings carried:
- Idempotency is core to reproducibility. A resumed run must never duplicate side effects.
- Lock files must use OS-level primitives (fcntl/portalocker), never Python threading primitives.
```

---

## W26: Git Hygiene module

**Issue**: [#26](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/26)
**Depends on**: W01, W03, W13 (audit log for conflict reports)
**Blocks**: W11 (integrated at rebase-before-pr stage)

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w26 -b acw-w26 main
cd ../acw-w26
```

**Coder prompt**:
```
You are the Coder agent for W26 — Git Hygiene module (issue #26).

Strategic context: Git is the destructive-op surface of Atelier. Worktree creation, rebase, push, cleanup — all must be safe. Our explicit contract: ANALYZE conflicts, NEVER auto-resolve. Phase 0 rebase is read-only: we compute conflicts (via `git merge-tree`), report structured findings, hand the exact commands to the human to run. This matches the user's stated ethos exactly.

Objective: Build atelier/git/ with worktree lifecycle + rebase-analyze (no auto-resolve) + cleanup.

Files you own:
- atelier/git/worktree.py — `create_worktree(run_id, base_branch="main") -> worktree_path`, `remove_worktree(worktree_path, confirm: bool)`
- atelier/git/rebase_analyzer.py — `analyze_rebase(worktree_path, target="origin/main") -> RebaseReport`. Uses `git fetch origin` then `git merge-tree origin/main HEAD` for conflict simulation (mutation-free). Reports: files_with_conflicts, conflict_hunks, resolution_suggestions (never applied).
- atelier/git/cleanup.py — `cleanup_run_worktrees(run_id, confirm: bool)`
- tests/test_git.py — integration tests against a temporary git repo fixture

How to start:
1. /speckit.specify "git hygiene: worktree creation, rebase analyzer (mutation-free), cleanup — never auto-resolves conflicts"
2. /speckit.clarify — merge-tree vs dry-run-rebase for conflict detection (prefer merge-tree — truly mutation-free), what counts as a resolution suggestion (keep minimal: names of conflicting files + conflict markers + suggestion "prefer ours|theirs|manual").
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- create_worktree creates branch + worktree dir, returns valid path
- analyze_rebase on a clean branch returns empty RebaseReport
- analyze_rebase on a conflicted branch returns structured report with file:line precision
- analyze_rebase NEVER mutates repo state (verify via `git status` before + after)
- remove_worktree with confirm=False raises ConfirmationRequiredError
- cleanup_run_worktrees batches remove_worktree calls

Credentials: not needed for tests; use temporary git repos.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W26 — Git Hygiene (issue #26).

Strategic context — where we are heading:
This module is where we prove our "human-in-the-loop at destructive gates" principle. Any silent state mutation here = a trust-breaking bug. The exact user requirement: "please do not decide for me first, analyse thru all conflicts if any, report back with what are the conflicts and resolution suggestions."

Full scope: ../../phase0_plan.md W26.

Review scope: atelier/git/, tests/test_git.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_git.py -v` — paste output.
2. Before/after state test: snapshot a test repo's `git status --porcelain` before analyze_rebase, run it, snapshot after. Diff must be empty. Paste.
3. Force a conflict scenario, run analyze_rebase, paste the RebaseReport. Confirm it lists conflicting files with line numbers.
4. Attempt `remove_worktree(path, confirm=False)` and expect ConfirmationRequiredError. Paste stack trace.
5. Grep for any `subprocess.run(..., check=True)` with git commands that mutate state (commit, rebase, merge, reset, push, force): `rg -n "git (commit|rebase|merge|reset|push|cherry-pick)" atelier/git/` — analyze each hit.

Domain findings to apply:
- If analyze_rebase calls `git rebase` (not `git merge-tree` or equivalent): RED. git rebase is stateful.
- If analyze_rebase returns suggestion "prefer theirs" without asking human: RED unless wrapped in "suggested — requires approval".
- If any command uses --force without corresponding --force-with-lease: RED.
- If remove_worktree has no confirm parameter: RED.
- If any path interpolation into git commands is user-controlled without escaping: RED (command injection).

Output format + verification + confidence as standard.

Learnings carried:
- User's exact phrasing: "do not decide for me first". Analyze + report + wait.
- merge-tree is preferred for mutation-free simulation. Never shell out to `git rebase --dry-run` blindly.
- force-with-lease, never force. Ever.
```

---

# Wave 1c — Context Compiler

## W07: Context Compiler

**Issue**: [#7](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/7)
**Depends on**: W01, W02, W03
**Blocks**: W11

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w07 -b acw-w07 main
cd ../acw-w07
```

**Coder prompt**:
```
You are the Coder agent for W07 — Context Compiler (issue #7).

Strategic context: The Context Compiler is Atelier's Packet Engine made real. It doesn't just concatenate context — it composes with priority tiers, dedupes, enforces token budgets, and preserves provenance. This is the single biggest productivity multiplier in Atelier: every manual copy-paste we've been doing in this whole Phase 0 launch is what the Compiler will automate.

Objective: Build atelier/compiler/ that assembles Context Packets from prioritized sources.

Files you own:
- atelier/compiler/compiler.py — `compile_packet(objective, sources, budget_tokens) -> Packet` where Packet has body markdown + provenance sidecar
- atelier/compiler/sources.py — Source types: IssueText, RepoRule, ADR, SampleDoc, WorktreeRef, Objective, ExactCommands, AcceptanceGate — each with priority: must | should | nice
- atelier/compiler/budget.py — token estimator (`len * 4 / 3` approximation for Phase 0); enforces budget by dropping nice-tier first, then should-tier, while honoring must-have completeness
- atelier/compiler/provenance.py — each included block tagged with `(source_type, source_id, path)` tuple
- tests/test_compiler.py — given fixture sources, deterministic compilation under various budgets

How to start:
1. /speckit.specify "Context Compiler: priority-tier packet assembly with token budgets and provenance"
2. /speckit.clarify — dedup strategy (exact match vs fuzzy — prefer exact for Phase 0), what happens when must-have tier alone exceeds budget (raise BudgetExceededError — user must intervene), provenance format in packet.md (footer block).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- compile_packet with fixture sources under 8k-token budget produces deterministic packet.md
- Nice-tier gets dropped first when budget tight; should-tier next; must-have is never dropped (raises instead)
- Identical blocks (same source_id) deduped
- Provenance footer lists all included sources
- Unit tests cover: within budget, tight budget (drops), impossible budget (raises)

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W07 — Context Compiler (issue #7).

Strategic context — where we are heading:
Every downstream stage relies on the packet being correct, complete, and within budget. A packet missing required rules = agent drifts. A packet with silent truncation = unpredictable behavior. Deterministic compilation is a requirement, not a nice-to-have.

Full scope: ../../phase0_plan.md W07. Design principle: roadmap.md "Packet Engine → Context Compiler" section.

Review scope: atelier/compiler/, tests/test_compiler.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_compiler.py -v` — paste output.
2. Determinism check: run compile_packet 10× with identical inputs; confirm byte-identical outputs. Paste.
3. Budget boundary check: compile at budget 1000, 999, 1001 tokens — paste packet.md sizes and confirm monotonic.
4. Must-have completeness: craft a packet where must-have sources alone exceed budget; confirm BudgetExceededError is raised, not silent truncation. Paste.

Domain findings to apply:
- If compilation is non-deterministic (dict iteration order affects output): RED. Use sorted() or OrderedDict.
- If token estimator is actually calling an LLM API: ORANGE (Phase 0 uses `len*4/3` approximation).
- If must-have sources are silently truncated: RED.
- If provenance is missing or incomplete: RED (reproducibility thesis requires it).
- If sources module allows string sources without Source class wrapping: ORANGE (type safety).

Output format + verification + confidence as standard.

Learnings carried:
- Phase 0 uses simple budget heuristic. Phase 3+ adds real tokenizer-based counting.
- Provenance is mandatory. Every fact in a packet must trace to a source.
- Determinism is reproducibility's precondition.
```

---

# Wave 2 — Workflow engine + late dependencies

## W11: Workflow Engine

**Issue**: [#11](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/11)
**Depends on**: W04, W05, W06, W07, W08, W09, W12
**Blocks**: W15, W16

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w11 -b acw-w11 main
cd ../acw-w11
```

**Coder prompt**:
```
You are the Coder agent for W11 — Workflow Engine (issue #11).

Strategic context: The engine choreographs the speckit loop: specify → clarify → plan → tasks → implement → (UAT optional) → rebase-analyze → cleanup. Each stage: calls persona, writes Evidence Pack, checks policy gate, transitions or loops. Resume-aware via W09 cursor. Phase 0 is serial; Phase 2 adds parallelism.

Objective: Build atelier/workflow/ that drives one issue end-to-end.

Files you own:
- atelier/workflow/engine.py — `Workflow` class with `start(issue_ref) -> run_id`, `advance(run_id) -> NextStage | Done`, `resume(run_id)`
- atelier/workflow/stages.py — stage functions (one per speckit command + UAT + rebase + cleanup), each: pull context via W07 compiler, call persona (W04), generate Evidence Pack (W08), check policy gate (W12), write memory records (W06), mark stage complete (W09)
- atelier/workflow/transitions.py — logic for deciding next stage from current verdict
- tests/test_workflow.py — integration test with mock LLM: start → run through specify + review → confirm files created on disk

How to start:
1. /speckit.specify "Workflow Engine driving speckit loop serially, with resume-from-cursor"
2. /speckit.clarify — how to handle Reviewer NEEDS_REVISION (loop Coder with feedback embedded in next packet, max 3 iters then escalate to council W21), UAT trigger condition (only if user-facing feature detected — use a simple heuristic for Phase 0: run if /api/ route or UI component in diff).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- start(issue_ref) creates run + first stage, returns run_id
- advance() drives specify → review; on NEEDS_REVISION, loops Coder (max 3 iters)
- resume(run_id) picks up where cursor points
- Files on disk: .atelier/runs/<id>/run.md + stages/001-specify/ with packet.md, transcript.jsonl, evidence.{md,json}
- Mock LLM fixture enables deterministic tests

Credentials: for integration test (optional), ANTHROPIC_API_KEY + OPENAI_API_KEY.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W11 — Workflow Engine (issue #11).

Strategic context — where we are heading:
This engine IS the reproducibility thesis made operational. Every bug here cascades. Resume correctness, transition logic, and stage isolation are load-bearing for the whole product.

Full scope: ../../phase0_plan.md W11.

Review scope: atelier/workflow/, tests/test_workflow.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_workflow.py -v` — paste output.
2. Resume test: start workflow, advance 2 stages, simulate crash (kill process), resume in new process, confirm stage 3 is next. Paste trace.
3. Infinite-loop guard test: force reviewer to NEEDS_REVISION 5x; confirm engine stops at max_iters and either escalates or halts (NEVER runs forever). Paste.
4. Idempotency test: call advance() twice without new state change; confirm no duplicate stage creation. Paste.

Domain findings to apply:
- If engine writes to DB instead of filesystem: RED.
- If NEEDS_REVISION loop has no max-iter cap: RED (runaway cost).
- If policy gate check is missing before rebase or cleanup stages: RED.
- If Evidence Pack generation is optional on any review stage: RED.
- If transcript.jsonl is overwritten (not append-only): RED.

Output format + verification + confidence as standard.

Learnings carried:
- Max iteration cap is cost + sanity protection. Always present.
- Filesystem is truth; engine orchestrates, never stores state in memory beyond session.
- Reviewer must gate every transition. No implicit advance on "Coder says done".
```

---

## W13: Audit log (JSONL)

**Issue**: [#13](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/13)
**Depends on**: W01, W03, W10
**Blocks**: (many consumers; blocks none hard)

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w13 -b acw-w13 main
cd ../acw-w13
```

**Coder prompt**:
```
You are the Coder agent for W13 — Audit log (issue #13).

Strategic context: Append-only JSONL audit trail for per-run and daily logs. Every LLM call, tool call, gate transition, decision written, and override applied gets one line. Replays, debugging, compliance, and cost aggregation all consume this. Phase 0 is file-based; Phase 3+ adds OpenTelemetry integration.

Objective: Build atelier/audit/ with reliable append-safe writes and query helpers.

Files you own:
- atelier/audit/writer.py — `log(run_id, event_type, data)` appends a JSON line to per-run and daily logs; event_type enum: LLM_CALL, TOOL_CALL, GATE_ENTERED, DECISION_LOGGED, OVERRIDE_APPLIED, COST_ACCRUED
- atelier/audit/events.py — Pydantic event schemas (one per event type) with strict validation
- atelier/audit/query.py — helpers: `sum_cost_for_run(run_id) -> float`, `events_for_run(run_id) -> list[Event]`, `events_by_type(event_type, since) -> list[Event]`
- tests/test_audit.py — 1000 concurrent appends from mock producers; assert no corruption.

How to start:
1. /speckit.specify "append-only JSONL audit with redaction applied at write time and query helpers"
2. /speckit.clarify — write strategy for cross-writer safety (O_APPEND is atomic for small lines; use it), daily rollover at local midnight.
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- 1000 concurrent log() calls from N processes produce 1000 valid JSON lines, no corruption
- Every line passes redaction (W10); no secret patterns appear in audit
- sum_cost_for_run aggregates correctly on fixture
- Daily rollover creates next day's file without data loss
- Schema violations (bad event type) raise clearly

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W13 — Audit log (issue #13).

Strategic context: Audit trail is Atelier's compliance + trust primitive. Corrupted lines = unparseable audit = broken reproducibility. Missing redaction = secret leak. Test both stress paths.

Full scope: ../../phase0_plan.md W13.

Review scope: atelier/audit/, tests/test_audit.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_audit.py -v` — paste output.
2. Concurrent write stress: spawn 8 processes each writing 500 events. Paste final line count + parse-all validation.
3. Redaction test: log an event with `{"api_key": "sk-xxx"}` in data; read back raw file; confirm no "sk-xxx" substring present. Paste.
4. Rollover test: mock date, cross midnight, confirm new file created. Paste.

Domain findings to apply:
- If JSONL writes use standard Python open() without O_APPEND: RED (not append-atomic under concurrency).
- If redaction is applied at query time (not write time): RED (secrets persist on disk).
- If sum_cost_for_run loads entire file into memory on large logs (>1M lines): ORANGE (stream instead).
- If event schemas allow extra fields: ORANGE.

Output format + verification + confidence as standard.

Learnings carried:
- O_APPEND is POSIX-atomic for lines under PIPE_BUF (~4KB). Stay under that size per line.
- Redact at write, not at read. Files on disk must be clean.
```

---

## W14: Auto-ADR synthesis

**Issue**: [#14](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/14)
**Depends on**: W01, W03, W06 (templates already seeded: atelier/adr/templates/madr.md.j2)
**Blocks**: (W11 calls at run completion)

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w14 -b acw-w14 main
cd ../acw-w14
```

**Coder prompt**:
```
You are the Coder agent for W14 — Auto-ADR synthesis (issue #14).

Strategic context: ADRs have been written manually in your existing workflow (TIROS docs/adr/). Atelier writes them as a side-effect of the work: reads Decision + RejectedAlternative records from W06, renders through the pre-seeded MADR 3.0 Jinja2 template at atelier/adr/templates/madr.md.j2, writes to docs/adr/NNNN-<slug>.md. Human reviews + commits.

Objective: Build atelier/adr/ to synthesize ADRs from typed memory records.

Files you own:
- atelier/adr/synthesis.py — `synthesize_adr(run_id) -> Path`. Reads all Decision + RejectedAlternative records for a run, groups by topic, renders one ADR per topic, writes to docs/adr/NNNN-<slug>.md with auto-numbering.
- atelier/adr/numbering.py — `next_adr_number(docs_adr_dir) -> int` by scanning existing files.
- atelier/adr/slug.py — title → slug (kebab-case, ASCII-safe)
- tests/test_adr.py — fixture with 3 Decisions + 2 RejectedAlternatives → synthesize → rendered MADR 3.0 file matches golden.

How to start:
1. /speckit.specify "auto-ADR synthesis from memory records using MADR 3.0 template (template already at atelier/adr/templates/madr.md.j2)"
2. /speckit.clarify — topic-grouping strategy (cluster Decisions by shared `tags` or `related_adrs`; for Phase 0, simple: one ADR per distinct topic tag), handling no decisions case (don't generate empty ADR).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- Fixture run with 3 Decisions + 2 RejectedAlternatives → 1 ADR written in MADR 3.0 format
- Frontmatter uses `decision-makers` field (not `deciders` — per MADR 3.0 strict naming)
- Consequences use Good/Bad polarity; Pros and Cons use Good/Neutral/Bad
- Auto-numbering increments correctly (0012 follows 0011)
- Slug generator handles unicode titles
- Golden-file test stable

Credentials: not needed.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W14 — Auto-ADR synthesis (issue #14).

Strategic context — where we are heading:
Auto-ADR is the single biggest productivity win in Atelier's vision. Users stop writing ADRs manually; they approve auto-drafts. Quality here determines whether the feature is loved or hated.

Full scope: ../../phase0_plan.md W14. Template reference: atelier/adr/templates/madr.md.j2 (already committed; verified against upstream MADR 3.0 by prior research agent).

Review scope: atelier/adr/, tests/test_adr.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_adr.py -v` — paste output.
2. Generate an ADR from a fixture; open and compare against upstream MADR 3.0 bare template structurally. Paste diff.
3. Verify frontmatter uses `decision-makers` not `deciders` — `rg -n "decision-makers" docs/adr/ || true`. Paste.
4. Verify polarity strictness: Consequences use only Good/Bad; Pros-and-Cons use Good/Neutral/Bad. Manual check — paste findings.

Domain findings to apply:
- If frontmatter field is `deciders` instead of `decision-makers`: RED (MADR 3.0 strict).
- If polarity "Neutral" appears in Consequences: RED (MADR reserves Neutral for Pros and Cons).
- If synthesis overwrites existing ADR files: RED (auto-numbering must be monotonic).
- If no human-review step documented between synthesis and commit: ORANGE (ADRs should be reviewed — at minimum a /speckit.checklist before commit).
- If slug generator fails on unicode: YELLOW.

Output format + verification + confidence as standard.

Learnings carried:
- MADR 3.0 has strict field and polarity naming. Don't paraphrase.
- Auto-ADR is a DRAFT producer. Human edits + commits; Atelier doesn't commit to docs/adr on its own.
```

---

## W18: UAT persona integration

**Issue**: [#18](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/18)
**Depends on**: W04
**Blocks**: W11 (UAT stage), W24

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w18 -b acw-w18 main
cd ../acw-w18
```

**Coder prompt**:
```
You are the Coder agent for W18 — UAT persona integration (issue #18).

Strategic context: UAT is the stage where Atelier goes beyond "tests pass" into "feature actually works for users." We integrate the user's existing ccc/skills/uat-testing pattern as a subprocess call; parse its output; produce Evidence Pack findings. This is Atelier's proof of shipping, not just coding.

Objective: Build UAT persona that shells out to ccc/skills/uat-testing and produces structured EvidencePack findings.

Files you own:
- atelier/personas/uat.py — UAT persona extending Persona base (W04). Overrides `respond(packet)` to subprocess-invoke the UAT skill.
- .atelier/defaults/personas/uat.md — system prompt
- atelier/personas/uat_runner.py — subprocess wrapper: finds ccc/skills/uat-testing (configurable path via env var), passes app_path + test_account_creds, captures stdout/stderr, parses report → EvidencePack.findings
- tests/test_uat.py — mock subprocess fixture; assert UAT report → EvidencePack mapping

How to start:
1. /speckit.specify "UAT persona that invokes ccc/skills/uat-testing as subprocess and produces Evidence Pack findings"
2. /speckit.clarify — env var for ccc skills path (ATELIER_UAT_SKILL_PATH defaults to /home/fei/fei/code/hackathon/ccc/skills/uat-testing but must be configurable), how to handle UAT skill not present (raise clear error, don't silently skip).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- UAT persona instantiates and respects capability requirements (delegates to LLM for test-case generation but actually runs tests via subprocess)
- Mock subprocess returning a UAT report → EvidencePack with findings populated correctly
- Clear error when UAT skill path invalid (not silent failure)
- Redaction applied to test account creds in Evidence Pack (W10)

Credentials: Test account creds from ../../.env.local (TEST_USER, TEST_PASSWORD).
```

**Reviewer prompt**:
```
You are the Reviewer agent for W18 — UAT persona (issue #18).

Strategic context — where we are heading:
UAT in the demo is a visible beat: a browser opens, an agent clicks through login, tests pass. If UAT breaks silently or leaks creds into logs, the demo fails.

Full scope: ../../phase0_plan.md W18.

Review scope: atelier/personas/uat.py, atelier/personas/uat_runner.py, .atelier/defaults/personas/uat.md, tests/test_uat.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_uat.py -v` — paste output.
2. Confirm redaction of creds in Evidence Pack output path: write a UAT result with TEST_PASSWORD="hunter2" in stdout; confirm final EvidencePack JSON contains "[REDACTED:*" not "hunter2". Paste.
3. Missing-skill test: set ATELIER_UAT_SKILL_PATH to nonexistent path, invoke UAT persona, paste error output — must be clear.

Domain findings to apply:
- If UAT creds logged to any file without redaction: RED.
- If silent fallback to "UAT passed" when skill is missing: RED.
- If subprocess doesn't timeout: ORANGE (hung UAT blocks the run).
- If no capture of stderr separately from stdout: YELLOW.

Output format + verification + confidence as standard.

Learnings carried:
- UAT skill is the user's existing tool. Integrate, don't replace.
- Creds redaction is non-negotiable everywhere secrets could flow.
```

---

# Wave 3 — Interfaces + LLM swappability

## W15: CLI

**Issue**: [#15](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/15)
**Depends on**: W11
**Blocks**: W16

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w15 -b acw-w15 main
cd ../acw-w15
```

**Coder prompt**:
```
You are the Coder agent for W15 — CLI (issue #15).

Strategic context: CLI is the primary user surface. Plugins and web are thin clients over it. A polished CLI with good help text + composable commands is what makes Atelier usable by power users and scriptable in CI.

Objective: Build atelier/cli/ using click or typer.

Files you own:
- atelier/cli/main.py — entry point; subcommands group
- atelier/cli/commands/ — one file per subcommand: init.py, run.py, cleanup.py, daemon.py, grep.py, show.py, list.py
- atelier/cli/formatters.py — pretty output helpers (rich library optional but nice)
- tests/test_cli.py — click's CliRunner tests

How to start:
1. /speckit.specify "atelier CLI with run, resume, show, list, cleanup, daemon, grep commands"
2. /speckit.clarify — click vs typer (prefer click for stability; typer is a nice DX but more magic), output format (default human; --json flag for machine), interactive prompts for destructive ops.
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- `atelier --help` prints overview
- `atelier init` scaffolds .atelier/ in cwd
- `atelier run --issue 42 --repo .` starts a workflow, prints Run ID
- `atelier run list` lists runs with status
- `atelier run show <run_id>` shows tree view of stages
- `atelier cleanup <run_id>` removes worktree with confirmation
- `atelier daemon start|stop|status` controls the HTTP daemon
- `atelier grep <pattern>` greps .atelier/ intelligently

Credentials: passed through from env.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W15 — CLI (issue #15).

Strategic context — where we are heading:
CLI UX matters. If commands are cryptic, users bounce. If outputs are terse, demos flop. If destructive commands skip confirmation, users get burned.

Full scope: ../../phase0_plan.md W15.

Review scope: atelier/cli/, tests/test_cli.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_cli.py -v` — paste output.
2. Run `atelier --help` and each subcommand with --help. Paste output.
3. Destructive command test: `atelier cleanup <fake_id>` without confirm flag — must prompt or error. Paste.
4. JSON output test: `atelier run list --json` — paste output, validate JSON.

Domain findings to apply:
- If `atelier cleanup` deletes without confirmation: RED.
- If help text is blank or single-line for any subcommand: ORANGE.
- If `--json` flag absent on list/show: YELLOW (scriptability matters).
- If CLI imports heavy deps (fastapi, anthropic) at module import: ORANGE (slow startup).

Output format + verification + confidence as standard.

Learnings carried:
- CLI is the product's first impression. Make help text useful.
- Destructive ops prompt by default; --yes flag to bypass.
```

---

## W16: HTTP daemon + SSE

**Issue**: [#16](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/16)
**Depends on**: W15
**Blocks**: (nothing in Phase 0 — optional worktree that unlocks future non-CLI clients)

**Phase 0 scope note**: W16 is OPTIONAL in Phase 0 now that the JetBrains plugin (W17/W20) has been dropped. Build this only if Lane A has time after W15 CLI ships. Its value is enabling future surfaces (VSCode, web dashboard, CI integration).

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w16 -b acw-w16 main
cd ../acw-w16
```

**Coder prompt**:
```
You are the Coder agent for W16 — HTTP daemon + SSE (issue #16).

Strategic context: An optional future-facing worktree. Exposes the Control Plane over localhost HTTP + SSE so non-CLI clients (future VSCode extension, web dashboard, CI integrations) can consume runs in real time. Phase 0 has no concrete consumer — we are establishing the contract for later phases. Skip if CLI priorities crowd it out.

Objective: Build atelier/daemon/ with FastAPI exposing runs + SSE + approval routes.

Files you own:
- atelier/daemon/server.py — FastAPI app
- atelier/daemon/routes.py — POST /runs, GET /runs/<id>, GET /runs/<id>/events (SSE), POST /runs/<id>/approve
- atelier/daemon/events.py — SSE event formatting from audit log tail
- tests/test_daemon.py — httpx AsyncClient tests

How to start:
1. /speckit.specify "FastAPI daemon exposing runs, SSE events stream, approval gates for the plugin client"
2. /speckit.clarify — SSE vs WebSocket (SSE is simpler for unidirectional event flow; use it), CORS (only localhost allowed in Phase 0), auth (shared secret header for local-only daemon).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- POST /runs creates a run, returns ID
- GET /runs/<id> returns run metadata
- GET /runs/<id>/events SSE-streams audit events live
- POST /runs/<id>/approve unblocks a gated stage
- All routes behind localhost-only binding
- Tests pass in CI without network

Credentials: LOCAL_DAEMON_SECRET from env (or auto-generated on first start).
```

**Reviewer prompt**:
```
You are the Reviewer agent for W16 — HTTP daemon (issue #16).

Strategic context — where we are heading:
Daemon is a local-only API. Exposing it to the network = security hole. Clients (plugin, future integrations) must authenticate. SSE stream must be resilient to client disconnects.

Full scope: ../../phase0_plan.md W16.

Review scope: atelier/daemon/, tests/test_daemon.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_daemon.py -v` — paste output.
2. Start daemon locally, curl each endpoint. Paste outputs.
3. Binding check: confirm daemon listens on 127.0.0.1, not 0.0.0.0. `ss -tnlp | grep <port>` — paste.
4. Disconnect test: subscribe to SSE, kill client, confirm daemon doesn't leak the stream.

Domain findings to apply:
- If daemon binds 0.0.0.0 by default: RED (local-only).
- If no auth on mutation endpoints: RED.
- If SSE stream keeps references to dead clients: ORANGE (memory leak).
- If CORS allows any origin: RED for Phase 0.

Output format + verification + confidence as standard.

Learnings carried:
- Local-first, local-only. No network exposure in Phase 0.
- Shared-secret auth is good enough for localhost. Phase 4+ adds OAuth for team deployments.
```

---

## W19: LLM swappability demo

**Issue**: [#19](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/19)
**Depends on**: W02, W04
**Blocks**: W24, W25

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w19 -b acw-w19 main
cd ../acw-w19
```

**Coder prompt**:
```
You are the Coder agent for W19 — LLM swappability demo (issue #19).

Strategic context: Vendor-agnosticism is Atelier's biggest structural moat. Every competitor is vendor-locked. W19 produces the demo beat that proves it: the SAME Reviewer persona runs against Claude, then Codex, producing two Evidence Packs side-by-side. Judge sees: same interface, different brains, both work.

Objective: Produce a scripted demo scenario + side-by-side Evidence Packs demonstrating the swap.

Files you own:
- demo/swap-demo.md — narration script
- demo/swap-demo.py — script that runs the same review against both backends, writes both Evidence Packs
- demo/swap-demo-output/claude/evidence.md, demo/swap-demo-output/codex/evidence.md — captured outputs

How to start:
1. /speckit.specify "swappability demo script + captured Evidence Packs from Claude vs Codex review of same input"
2. /speckit.clarify — what code should Reviewer analyze (use a fixture with a known bug — e.g., a 20-line Python function with an off-by-one), which specific models.
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- `python demo/swap-demo.py` produces both Evidence Packs
- Both packs find the planted bug (proving both models can execute the protocol)
- Capability manifest check: if swapping to a model that doesn't support tool_use, UnsupportedCapabilityError is raised (PROOF that the manifest works)
- Narration script reads in <= 60 seconds

Credentials: ANTHROPIC_API_KEY, OPENAI_API_KEY.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W19 — Swappability demo (issue #19).

Strategic context — where we are heading:
This demo beat needs to be undeniable. If it looks staged or trivial, it fails. Reviewer must find a real bug; both models must succeed; the UnsupportedCapabilityError path must be visible too.

Full scope: ../../phase0_plan.md W19.

Review scope: demo/swap-demo.md, demo/swap-demo.py, demo/swap-demo-output/.

Review guidelines (execution-mandatory):
1. Run `python demo/swap-demo.py`. Paste output.
2. Read both Evidence Packs. Confirm both verdicts find the planted bug. Paste summaries.
3. Capability-failure test: hack the script to route to an incompatible model; paste the expected error.
4. Narration timing: read demo/swap-demo.md aloud; time it. Must fit in 60s for the Phase 0 demo slot.

Domain findings to apply:
- If the bug is so trivial Reviewer can't miss: YELLOW (not convincing enough).
- If outputs are identical (suggesting one was cached not actually run): RED — must be two real LLM calls.
- If swap requires code edit rather than config: ORANGE (architecture says model is configurable).

Output format + verification + confidence as standard.

Learnings carried:
- Swappability must be config-driven, not code-edit-driven.
- Both models must truly run. No caching shortcut.
```

---

## W21: Phase 1 peek: 3-agent tiebreaker

**Issue**: [#21](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/21)
**Depends on**: W02, W04
**Blocks**: W24 (demo includes this visual)

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w21 -b acw-w21 main
cd ../acw-w21
```

**Coder prompt**:
```
You are the Coder agent for W21 — 3-agent tiebreaker (issue #21).

Strategic context: Phase 1 peek — a minimal Council. When Coder ↔ Reviewer deadlock 2×, escalate: send both positions to 3 different models; each votes; majority wins; ties go to human. Full MAD comes in Phase 1; Phase 0 ships this narrow slice as a demo beat.

Objective: Build atelier/council/tiebreaker.py with a minimal voting protocol.

Files you own:
- atelier/council/tiebreaker.py — `tiebreak(coder_position, reviewer_position, context, models: list[str]) -> Verdict`. Calls 3 models via W02 adapters; each returns COMPATIBLE_WITH_CODER | COMPATIBLE_WITH_REVIEWER | NEITHER; majority wins; tie → HUMAN_REQUIRED.
- atelier/council/schema.py — Verdict enum + CouncilReport model
- tests/test_council.py — mock 3 LLMs, varied vote combinations, confirm tie handling

How to start:
1. /speckit.specify "3-agent tiebreaker triggered on Coder↔Reviewer deadlock, majority-wins voting, ties escalate to human"
2. /speckit.clarify — model selection (default: claude-opus + gpt-5 + claude-sonnet; user-overridable), prompt format for voter (structured: must produce one of 3 verdicts only).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- 3 voters, 2 agree, 1 disagrees → majority verdict returned
- 3 voters, each votes differently → HUMAN_REQUIRED
- Records CouncilReport to memory (W06) with full vote breakdown
- Uses W02 capability-check per voter (no silent capability degradation)

Credentials: ANTHROPIC_API_KEY + OPENAI_API_KEY.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W21 — Council tiebreaker (issue #21).

Strategic context — where we are heading:
This is a demo visual AND a Phase 1 stepping stone. Must actually work (not fake majority vote); must produce a CouncilReport memory record (auditability); must respect capability manifest.

Full scope: ../../phase0_plan.md W21. Inspiration: Du 2023 MAD, Karpathy LLM Council.

Review scope: atelier/council/, tests/test_council.py.

Review guidelines (execution-mandatory):
1. `uv run pytest tests/test_council.py -v` — paste.
2. Trigger real council with mock positions; paste CouncilReport.
3. Verify all 3 model calls happen in parallel (concurrent asyncio.gather) — paste timing.
4. Tie handling test: paste output for 1-1-1 vote → HUMAN_REQUIRED.

Domain findings to apply:
- If voter prompts allow freeform response (not enum): RED — parse must never hallucinate a verdict.
- If calls are sequential instead of concurrent: ORANGE — waste.
- If CouncilReport isn't written to memory: RED (audit requirement).
- If anonymization is missing (voters see "Reviewer" / "Coder" labels): YELLOW for Phase 0 (full anonymization is Phase 1).

Output format + verification + confidence as standard.

Learnings carried:
- MAD is escalation-only; never routine.
- Anonymization is Phase 1; for Phase 0 demo, just run 3 voters in parallel with majority logic.
```

---

# Demo prep wave (parallel with Wave 3-4, finalize Sunday)

## W23: Curated demo issue

**Issue**: [#23](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/23)
**Depends on**: W22
**Blocks**: W24

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w23 -b acw-w23 main
cd ../acw-w23
```

**Coder prompt**:
```
You are the Coder agent for W23 — Demo issue (issue #23).

Strategic context: The demo issue drives the Phase 0 end-to-end run. Must be concrete, testable, adversarially-reviewable (Reviewer must find a real edge case to flag), UAT-able (real login/click flow). Suggested: "Add rate limiting to /api/login — max 5 attempts per minute per IP, return 429 with Retry-After header."

Objective: Draft the demo issue as demo/issue.md AND file it on the demo app's GitHub repo (or emulate with a local tracking file).

Files you own:
- demo/issue.md — issue body with: user story, acceptance criteria, security considerations, sample curl requests
- demo/issue.meta.yaml — frontmatter for workflow consumption

How to start:
1. /speckit.specify "demo issue: rate limiting on /api/login with 429 + Retry-After; adversarially reviewable; UAT-able"
2. /speckit.clarify — rate limit storage (in-memory for demo), test account behavior (creds from demo/app/.env.example), what "adversarially reviewable" means (Reviewer should find: off-by-one, clock-skew, IPv6 handling, distributed-instance case).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.

Acceptance criteria:
- Issue has 3+ acceptance criteria each independently testable
- Has at least 2 "obvious" edge cases Reviewer can attack
- UAT: a test account can trigger rate limit within 10 attempts
- Sample curl commands provided
```

**Reviewer prompt**:
```
You are the Reviewer agent for W23 — Demo issue (issue #23).

Strategic context: A weak demo issue = weak demo. Criteria must be crisp, edges must exist, UAT path must be obvious.

Review scope: demo/issue.md, demo/issue.meta.yaml.

Guidelines:
1. Read through issue as a Coder would. Can you write code from this? Paste 3-bullet summary.
2. Identify 3+ concrete bugs a Coder might introduce. Paste.
3. Check UAT path: can you verify with curl? Paste a curl command that would test acceptance criterion #1.

Domain findings:
- If criteria include implementation details: ORANGE (spec should be behavior-focused).
- If no edge cases listed: RED (no Reviewer attack surface = weak demo).
- If UAT is unclear: ORANGE.

Output + verification + confidence as standard.

Learnings carried:
- Concrete, testable, adversarial. All three.
```

---

## W24: E2E dogfood + warm cache

**Issue**: [#24](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/24)
**Depends on**: W11, W15, W22, W23 (ideally also W16, W18, W19, W20, W21)
**Blocks**: W25

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w24 -b acw-w24 main
cd ../acw-w24
```

**Coder prompt**:
```
You are the Coder agent for W24 — E2E dogfood + warm cache (issue #24).

Strategic context: The moment we run Atelier ON the demo issue ON the demo app. Every stage must work. Every failure here is a demo risk. Capture every stage's output to warm-cache/ so that if the live demo hiccups, we drop to cached and the audience doesn't notice.

Objective: Run the full Phase 0 workflow end-to-end. Capture everything.

Files you own:
- demo/warm-cache/* — captured outputs from a successful run
- demo/dogfood.md — replay instructions, fallback triggers per stage
- scripts/run-demo.sh — one-command kickoff

How to start:
1. /speckit.specify "end-to-end dogfood run against demo app + issue, with warm-cache capture per stage"
2. /speckit.clarify — what counts as "successful" per stage (each Evidence Pack approved, UAT pass, ADR generated, rebase-report produced).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Review iterations.
5. RUN THE DEMO at least 3×. Each run should succeed. Cache the 3rd.

Acceptance criteria:
- Full workflow runs without human intervention (except rebase-before-pr approval)
- Every stage produces expected artifacts
- warm-cache/ has replay-ready snapshots of every stage
- scripts/run-demo.sh is one-command executable
- Rehearsed 3+ times

Credentials: full env.
```

**Reviewer prompt**:
```
You are the Reviewer agent for W24 — E2E dogfood (issue #24).

Strategic context: This IS the demo. If it works here, it works Sunday. If it flakes, everything else is lost.

Review scope: demo/warm-cache/, demo/dogfood.md, scripts/run-demo.sh.

Guidelines:
1. Run scripts/run-demo.sh. Paste stdout + stderr.
2. Verify every stage produced artifacts: grep for evidence.md, evidence.json, packet.md, transcript.jsonl, completion markers. Paste counts.
3. Check warm-cache has replay: can you rerun from cache without hitting LLMs? Paste fallback exercise.
4. Run demo 3× back-to-back. Did any run fail? Paste each trace.

Domain findings:
- If any stage skipped: RED.
- If Evidence Pack missing for any review stage: RED.
- If warm-cache has secrets (missed redaction): RED.
- If script requires manual typing beyond approval prompts: ORANGE.

Output + verification + confidence as standard.

Learnings carried:
- Three clean runs = we ship. Two = rehearse more. One = unreliable.
- Cache EVERYTHING. Fallback is worth the disk space.
```

---

## W25: Pitch deck + demo script + fallback video

**Issue**: [#25](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/25)
**Depends on**: W24
**Blocks**: (submission)

**Git commands**:
```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
git worktree add ../acw-w25 -b acw-w25 main
cd ../acw-w25
```

**Coder prompt**:
```
You are the Coder agent for W25 — Pitch deck + demo script + fallback video (issue #25).

Strategic context: Pitch is 10% of the rubric but the tiebreaker. A clear demo with a sharp narrative wins against a better product with a bad pitch. Record fallback video NOW, not Sunday afternoon.

Objective: Deliver pitch deck, demo script, and fallback video.

Files you own:
- demo/pitch.md — 5 slides: problem, solution, demo, moat, ask
- demo/script.md — beat-by-beat narration timed to ≤90s
- demo/fallback.mp4 — recorded screen+narration of a successful dogfood run

How to start:
1. /speckit.specify "pitch deck + demo script + fallback video for Atelier Phase 0"
2. /speckit.clarify — deck format (markdown-only is fine for hackathon judges; no need for fancy slides), voice (calm, confident, one-thesis-per-slide).
3. /speckit.plan → /speckit.tasks → /speckit.implement.
4. Record fallback video with OBS/QuickTime. Rehearse live script 5×.

Acceptance criteria:
- Pitch deck: 5 slides, each ≤50 words
- Script fits in 90s when read aloud
- Fallback video plays the demo narrated over real outputs
- Rehearsed ≥5 times
```

**Reviewer prompt**:
```
You are the Reviewer agent for W25 — Pitch materials (issue #25).

Review scope: demo/pitch.md, demo/script.md, demo/fallback.mp4.

Guidelines:
1. Read pitch aloud, time it. Paste duration.
2. Watch fallback video. Paste 3 critical observations (pacing, clarity, obvious bugs).
3. Confirm deck covers: problem, solution, demo, moat, ask — one per slide.

Domain findings:
- If script exceeds 90s: RED (cut ruthlessly).
- If moat isn't named explicitly (reproducibility + LLM-agnostic + execution-mandatory): ORANGE.
- If fallback video has audio issues: RED (re-record).

Output + verification + confidence as standard.

Learnings carried:
- "I've been building safety-critical AI in HAZOP, where wrong outputs can kill people" is a compelling cold open.
- One clear transition per slide.
```

---

# End

This file is the Phase 0 manual Packet Engine. Once W07 (Context Compiler) ships, Atelier can generate this file automatically from phase0_plan.md + issue metadata. The irony is intentional — we dogfood the pain we're productizing.

**Next step**: Pick your lane (A/B/C/D/E from phase0_plan.md) and start with the Wave 0 worktree for that lane. Open two terminals, paste prompts, go.
