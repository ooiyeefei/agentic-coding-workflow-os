# Phase 0 Execution Plan — MVP Foundation

> **Goal**: Maximum parallelism — every task packaged as a worktree-ready unit with explicit inputs, outputs, deps, and acceptance criteria.
>
> **Operational companion**: [`phase0_launch.md`](./phase0_launch.md) contains paste-ready git worktree commands + coder/reviewer prompts for each worktree. Open that file when you're ready to start work; this file is the design spec.

## Current Progress

| Status | Count | Worktrees |
|---|---|---|
| **Merged to main** | 16 | W01, W02, W03, W04, W05, W06, W07, W08, W09, W10, W12, W18, W19, W21, W22, W23 |
| **Descoped** | 2 | W17, W20 (JetBrains plugin — CLI is sole Phase 0 surface) |
| **Closed** | 1 | W25 (hackathon pitch — removed post-hackathon) |
| **Ready to launch (Wave 3)** | 4 | **W11, W13, W14, W26** — all deps met, can start in parallel NOW |
| **Blocked on Wave 3** | 3 | W15 (needs W11), W16 (needs W15), W24 (needs W11 + W15) |

**Critical path**: W11 (Workflow Engine) → W15 (CLI) → W24 (Integration Tests)

## Scope Summary

Ship the functional MVP of Atelier: a real GitHub issue flows end-to-end through a user-defined workflow, producing Evidence Packs, auto-generated ADRs, and a Run Graph — all persisted as files, replayable, reviewer-attacked, and human-approved at destructive gates. Invokable from the CLI. All components dynamic and configurable.

## MVP User Flow

1. User runs `atelier run --issue <N>` → orchestrator reads workflow definition from `.atelier/workflows/`, creates `.atelier/runs/<ulid>/` + worktree from main
2. Context Compiler assembles Packet for Coder (issue + repo rules + relevant ADRs + objective + commands)
3. Coder executes the first workflow stage (e.g., `/speckit.specify`) → produces draft → writes to worktree
4. Reviewer attacks output using execution-mandatory protocol → produces Evidence Pack (JSON + Markdown)
5. If Reviewer rejects 2× with no resolution → escalate to 3-agent council tiebreaker
6. Coder advances through subsequent workflow stages as defined in the workflow YAML (e.g., clarify → plan → tasks → implement)
7. Each stage produces Evidence Pack; each disagreement logs a Decision + RejectedAlternative memory record
8. UAT stage runs acceptance tests against the real application
9. Auto-ADR synthesis reads transcripts + decisions → writes `docs/adr/NNNN-<topic>.md` in MADR 3.0 format
10. `/rebase-before-pr` analyzes: runs `git fetch origin`, computes rebase conflicts, reports findings, **never auto-resolves**
11. `/cleanup-worktree` (with confirmation) — Run Graph remains committed for replay

CLI surfaces for each run:
- `atelier run show <id>` — Run Graph tree (stages, evidence, decisions)
- `atelier run show <id> --evidence` — rendered Evidence Pack (Markdown to terminal)
- `atelier run show <id> --adr` — generated ADR preview
- `atelier run show <id> --rebase` — rebase analysis report
- `atelier run show <id> --cost` — cost tracker per-run aggregate

---

## Must-Ship Components (Phase 0 final)

| Component | Owner | Primary File(s) |
|---|---|---|
| Repo scaffolding (pyproject, tooling, dir structure) | Lane A | `pyproject.toml`, `atelier/__init__.py`, dir layout |
| ULID generator + path helpers | Lane A | `atelier/util/ulid.py`, `atelier/util/paths.py` |
| LLM Abstraction (Anthropic + OpenAI) + capability manifest | Lane A | `atelier/llm/*.py`, `atelier/llm/models/*.yaml` |
| Persona Library (Coder, Reviewer) + `devil_advocate_mode` flag (default off) | Lane B | `atelier/personas/*.py`, `.atelier/defaults/personas/*.md` |
| Skills Library (imports + additions) | Lane B | `.atelier/defaults/skills/*.md` |
| Context Compiler | Lane A | `atelier/compiler/*.py` |
| Knowledge Plane record schemas + file I/O | Lane B | `atelier/memory/*.py` |
| Evidence Pack generator | Lane B | `atelier/evidence/*.py`, `atelier/evidence/templates/*.j2` |
| Auto-ADR synthesis | Lane B | `atelier/adr/*.py`, `atelier/adr/templates/madr.j2` |
| Run Graph file tree ops | Lane A | `atelier/rungraph/*.py` |
| Workflow Engine (dynamic, workflow-as-code) | Lane A | `atelier/workflow/*.py`, `.atelier/workflows/*.yaml` |
| Policy Engine | Lane A | `atelier/policy/*.py` |
| Git Hygiene (worktree, rebase-analyze, cleanup) | Lane C | `atelier/git/*.py` |
| Secret redaction | Lane C | `atelier/security/redaction.py` |
| Audit log (JSONL) | Lane C | `atelier/audit/*.py` |
| UAT persona + integration | Lane C | `atelier/personas/uat.py`, `.atelier/defaults/personas/uat.md` |
| CLI | Lane A | `atelier/cli/*.py` |
| HTTP daemon + SSE (foundation for future client surfaces) | Lane A | `atelier/daemon/*.py` |
| 3-agent council tiebreaker | Lane B | `atelier/council/*.py` |
| Example project (integration test target) | Lane E | `examples/app/*` |
| Example issue | Lane E | `examples/issue.md` |
| Integration tests + E2E validation | Lane E | `tests/integration/` |

## Deferred (documented, not built)

- Parallel worktree orchestration (Phase 2)
- Full MAD / LLM Council (Phase 1 except tiebreaker)
- Memory namespaces (repo-local only in Phase 0)
- Replay/Eval Harness (Phase 3)
- VSCode extension (Phase 5)
- Web dashboard (Phase 6)
- Event bus, OpenTelemetry (Phase 4)
- Org defaults, workflow-level policy (Phase 4)
- Full rule precedence (2 levels in Phase 0, 5 levels in Phase 3)
- Model capability dynamic discovery (static YAML manifests in Phase 0; auto-discovery later)
- Workflow schema validation tooling (Phase 0 ships YAML loader + Pydantic validation; richer tooling later)

---

## Parallel Worktree DAG

### Dependency diagram

```
                     W01 (repo scaffolding)
                           │
                ┌──────────┼──────────┬────────────┬──────────────┐
                │          │          │            │              │
              W02        W03        W04          W05            W22
        (LLM abstr.) (ULID+paths) (personas)  (skills)   (demo target app)
                │          │          │            │              │
                │          └────┬─────┼────┬───────┘              │
                │               │     │    │                      │
                │              W06   W07  W08                     W23
                │             (memory)(compiler)(evidence)   (demo issue)
                │               │     │    │
                │               └─┬───┼────┘
                │                 │   │
                │                W09 W10
                │          (run graph) (redaction)
                │                 │   │
                │                W13 W14
                │            (audit) (auto-ADR)
                │                 │
                │                W11
                │         (workflow engine)
                │                 │
                │                W12
                │          (policy engine)
                │                 │
                │                W15
                │              (CLI)
                │                 │
                │                W16
                │          (HTTP daemon + SSE, future surfaces)
                │                 │
                │                W18
                │             (UAT persona)
                │
              W19 (LLM swappability test)    W21 (3-agent council tiebreaker)
                                             W24 (integration tests + E2E validation)
              W26 (Git Hygiene)
```

### Suggested Parallel Lanes

**Lane A — Control Plane (Python async)**
`W01 → W02 → W03 → W07 → W09 → W11 → W12 → W15 → W16`
One strong Python engineer. Owns orchestration, workflow, LLM abstraction, context compiler, CLI, daemon.

**Lane B — Personas, Memory, Evidence**
`W04 → W05 → W06 → W08 → W14 → (W21 if time)`
One engineer with prompt-craft + Python. Owns the IP that makes Atelier different — Reviewer execution-mandatory protocol, Evidence Pack templates, auto-ADR synthesis, Phase 1 council tiebreaker.

**Lane C — Git, UAT, Security**
`W10 → W13 → W26 → W18`
One engineer comfortable with git internals + subprocess orchestration. Owns git hygiene, audit log, secret redaction, UAT wiring.

**Lane E — Examples + Integration**
`W22 → W23 → W19 → W24`
One generalist. Maintains example project + issue, validates E2E runs, writes integration tests, ensures all components work together.

### Cross-Lane Integration Points

- **Early milestone**: Lane A publishes the CLI command contract (help output, arg shape, JSON output schema for `--json` flag). All lanes freeze to this interface early.
- **Evidence Pack schema** (JSON + Markdown): Lane B publishes; consumers are Lane A (audit chain, CLI `show --evidence` renderer) and any future client (VSCode ext, web dashboard, CI integration).
- **Context Packet format** (Markdown): Lane A + Lane B agree on packet.md structure early.
- **LLM capability manifest format**: Lane A publishes; Lane B consumes when declaring persona requirements.

---

## Worktree Details

Each worktree below is independently checkoutable. `depends` lists the worktrees whose outputs must exist first. Recommend creating a git worktree per W## for true isolation.

### W01 — Repo scaffolding

- **Depends**: none (foundation)
- **Owns**: `pyproject.toml`, `atelier/__init__.py`, top-level dir structure, `.python-version`, Makefile
- **Scope**: Python 3.11+ project, uv-managed deps, ruff + pyright configured. Define package layout (`atelier/cli`, `atelier/llm`, `atelier/workflow`, etc.).
- **Acceptance**: `uv sync` works, `python -m atelier --help` prints placeholder help, ruff + pyright pass on empty package
- **Output**: installable package skeleton
- **Handoff**: All other W## can `from atelier import ...` once this lands
- **Blocks**: Everything

### W02 — LLM Abstraction + Capability Manifest

- **Depends**: W01
- **Owns**: `atelier/llm/adapter.py`, `atelier/llm/anthropic.py`, `atelier/llm/openai.py`, `atelier/llm/capabilities.py`, `.atelier/defaults/models/*.yaml`
- **Scope**: abstract `LLMAdapter` with `generate(messages, tools, capabilities) -> Response`. Anthropic + OpenAI implementations. YAML capability manifests for claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5, gpt-5 (or codex), gpt-4o-mini. Persona-requires vs model-offers matching function.
- **Acceptance**: Unit test calls Anthropic and OpenAI with mock, validates response shape. Capability matcher rejects route if persona requires `tool_use` and model offers `tool_use: false`.
- **Output**: Pluggable LLM backend layer
- **Handoff**: Lane B uses this for persona LLM calls
- **Blocks**: W04, W07, W11, W21

### W03 — ULID Generator + Path Helpers

- **Depends**: W01
- **Owns**: `atelier/util/ulid.py`, `atelier/util/paths.py`
- **Scope**: ULID generation (use `python-ulid`), path helpers for `.atelier/runs/<run_id>/stages/<nnn-name>/`, safe mkdir, atomic writes (tmpfile + rename)
- **Acceptance**: ULIDs are lex-sortable; paths generated correctly for a fake run+stage; atomic write survives simulated interrupt
- **Output**: ID + FS utilities used everywhere
- **Blocks**: W09, W13, W11

### W04 — Persona Library

- **Depends**: W01, W02 (partial — consumes LLM adapter)
- **Owns**: `atelier/personas/base.py`, `atelier/personas/coder.py`, `atelier/personas/reviewer.py`, `.atelier/defaults/personas/coder.md`, `.atelier/defaults/personas/reviewer.md`
- **Scope**: `Persona` class with system prompt loader, capability requirements, LLM adapter binding. Reviewer persona prompt implements execution-mandatory protocol (transplant from TIROS AGENTS.md, generalized). Coder persona prompt is the /speckit.* driver.
- **Acceptance**: `coder.respond(packet)` returns a draft; `reviewer.review(diff, tests)` returns a structured Evidence Pack draft with verdict + confidence + findings
- **Output**: Two working personas, loadable by name
- **Blocks**: W11, W18, W21

### W05 — Skills Library

- **Depends**: W01
- **Owns**: `.atelier/defaults/skills/speckit.specify.md`, `.atelier/defaults/skills/speckit.clarify.md`, `.atelier/defaults/skills/speckit.plan.md`, `.atelier/defaults/skills/speckit.tasks.md`, `.atelier/defaults/skills/speckit.implement.md`, `.atelier/defaults/skills/rebase-before-pr.md`, `.atelier/defaults/skills/cleanup-worktree.md`, `.atelier/defaults/skills/uat-test.md`
- **Scope**: Import speckit.* verbatim from user's existing `.claude/commands/`. Author rebase-before-pr.md (encode user's exact instructions: git add . → commit → fetch → rebase origin/main → analyze conflicts without deciding → report → force-with-lease push). Author cleanup-worktree.md. Stub uat-test.md that calls ccc/skills/uat-testing.
- **Acceptance**: Each skill file has YAML frontmatter with `inputs`, `expected_artifacts`, `success_checks`, `next_transition`. Skill loader reads and validates.
- **Output**: Complete skill catalog Phase 0 needs
- **Blocks**: W11

### W06 — Knowledge Plane (typed records)

- **Depends**: W01, W03
- **Owns**: `atelier/memory/records.py`, `atelier/memory/writer.py`, `atelier/memory/reader.py`
- **Scope**: Pydantic schemas for `Decision`, `ReviewFinding`, `RejectedAlternative`. Writer serializes to markdown with YAML frontmatter. Reader parses any `.atelier/memory/**/*.md` back to typed record. Deterministic filename = `<type>_<ulid>.md`.
- **Acceptance**: Round-trip test: `record → write → read → record` preserves all fields. Frontmatter is valid YAML, body is clean markdown.
- **Output**: Memory record persistence layer
- **Blocks**: W14, W11

### W07 — Context Compiler

- **Depends**: W01, W02, W03
- **Owns**: `atelier/compiler/compiler.py`, `atelier/compiler/sources.py`
- **Scope**: Assemble Context Packets from prioritized sources. Inputs: issue text, repo rules (`CLAUDE.md`, `.claude/rules/*.md`), relevant ADRs, sample docs, current worktree path, exact objective, exact commands, acceptance gate. Priority tiers (must/should/nice). Token budget enforcement (simple `len*4/3` estimator for Phase 0). Dedup identical blocks. Each block tagged with provenance tuple `(source_type, source_id, path)`. Output: `packet.md`.
- **Acceptance**: Given fixture inputs, compiler produces deterministic packet.md under a fake 8k-token budget, nice-to-have tier gets dropped first. Provenance block at end lists all sources.
- **Output**: Deterministic packet generation
- **Blocks**: W11

### W08 — Evidence Pack Generator

- **Depends**: W01, W03
- **Owns**: `atelier/evidence/schema.py`, `atelier/evidence/generator.py`, `atelier/evidence/templates/evidence.md.j2`
- **Scope**: Pydantic schema for EvidencePack (verdict, confidence, findings list with severity, execution section with real command outputs, audit-chain linked IDs). Jinja2 template renders Markdown from JSON. Both written side-by-side.
- **Acceptance**: EvidencePack(verdict="REJECTED", findings=[...]) produces valid JSON and human-readable Markdown; Markdown references ULIDs for traceback.
- **Output**: Dual-format Evidence Pack writer
- **Blocks**: W04 (reviewer writes evidence via this)

### W09 — Run Graph File Tree Ops

- **Depends**: W01, W03
- **Owns**: `atelier/rungraph/tree.py`, `atelier/rungraph/cursor.py`
- **Scope**: Create runs/<ulid>/, create stages/<nnn-name>/, write stage.md with frontmatter, write completion markers for idempotency. `cursor` tracks "next stage to execute" for resume semantics. Lock file per run to prevent concurrent writes.
- **Acceptance**: Start run, create 3 stages, complete 2, restart process, resume correctly picks up stage 3. Lock prevents second writer.
- **Output**: Durable run lineage as directory tree
- **Blocks**: W11, W13

### W10 — Secret Redaction

- **Depends**: W01
- **Owns**: `atelier/security/redaction.py`
- **Scope**: Regex-based redactor for: `.env` line patterns, known env var names (`API_KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `Bearer <x>`), common service prefixes (`sk-`, `pk_`, `ghp_`, `xoxb-`). Entropy heuristic for unknown high-entropy strings optional. Applied before any write-to-file.
- **Acceptance**: Fixture with `OPENAI_API_KEY=sk-abc123...` redacts to `OPENAI_API_KEY=<REDACTED>`. Safe strings pass through.
- **Output**: Reusable redaction function
- **Blocks**: W13 (audit log), W08 (evidence)

### W11 — Workflow Engine (dynamic, workflow-as-code)

- **Depends**: W04, W05, W06, W07, W08, W09
- **Owns**: `atelier/workflow/engine.py`, `atelier/workflow/loader.py`, `atelier/workflow/stages.py`, `atelier/workflow/transitions.py`, `.atelier/defaults/workflows/speckit-loop.yaml`
- **Scope**: Workflow-as-code engine that loads workflow definitions from `.atelier/workflows/*.yaml` (user project) or `.atelier/defaults/workflows/` (shipped defaults). Each workflow YAML declares: stages (ordered), persona per stage, skill per stage, gate type (review/approval/auto), transition rules, retry policy. The engine reads the YAML, resolves personas + skills, and drives execution. Ships with `speckit-loop.yaml` as the default workflow (specify → clarify → plan → tasks → implement → UAT → rebase-analyze → cleanup). Users define custom workflows for their project — the engine is NOT tied to speckit. Resume-aware via W09 cursor.
- **Acceptance**: (1) Load `speckit-loop.yaml` and run a real issue through specify → review, handling Reviewer rejection with retry. (2) Load a DIFFERENT custom workflow YAML (e.g., a minimal 2-stage "implement → review" workflow) and run it successfully. Both produce correct Run Graph artifacts.
- **Output**: Configurable, extensible workflow engine
- **Blocks**: W15, W16

### W12 — Policy Engine (configurable)

- **Depends**: W01
- **Owns**: `atelier/policy/engine.py`, `atelier/policy/loader.py`, `atelier/policy/defaults.py`, `.atelier/defaults/policy.yaml`
- **Scope**: Loads policy from `.atelier/policy.yaml` (user project) or `.atelier/defaults/policy.yaml` (shipped defaults). Policy primitives: `human_approval_required` (per stage/gate), `dry_run_default` (per action type), `cost_cap_per_run`, `cost_cap_per_day`, `cost_cap_per_model`. Ships with sensible defaults: approval at rebase-before-pr, dry-run for all git ops, configurable cost caps. Users override in their project's `.atelier/policy.yaml`. Policy checks called by W11 before destructive ops and before LLM calls.
- **Acceptance**: (1) Default policy halts at rebase-before-pr for human approval. (2) User override in `.atelier/policy.yaml` changes cost cap — engine respects the override. (3) Cost exceeding cap halts + alerts.
- **Output**: Configurable policy enforcement layer
- **Blocks**: W11

### W13 — Audit Log

- **Depends**: W01, W03, W10
- **Owns**: `atelier/audit/writer.py`
- **Scope**: Append-only JSONL writer for per-run `.atelier/runs/<id>/audit.jsonl` and daily `.atelier/audit/YYYY-MM-DD.jsonl`. Events: llm_call, tool_call, gate_entered, decision_logged, override_applied. Apply redaction (W10) before write.
- **Acceptance**: 1000 concurrent writes produce no corruption. Every line valid JSON. Secrets redacted.
- **Output**: Reliable audit trail
- **Blocks**: (called by many, blocks nothing)

### W14 — Auto-ADR Synthesis

- **Depends**: W01, W03, W06
- **Owns**: `atelier/adr/synthesis.py`, `atelier/adr/templates/madr.md.j2`
- **Scope**: Read all Decision + RejectedAlternative records for a completed run. Render MADR 3.0 format: Context, Decision, Consequences, Alternatives Considered. Write to `docs/adr/NNNN-<slug>.md`, auto-numbering.
- **Acceptance**: Fixture with 3 Decisions + 2 RejectedAlternatives produces a well-formed MADR 3.0 ADR ready for human review.
- **Output**: Auto-generated ADRs
- **Blocks**: (called by W11 at run completion)

### W15 — CLI

- **Depends**: W11
- **Owns**: `atelier/cli/main.py`, `atelier/cli/commands/*.py`
- **Scope**: Click or Typer-based CLI. Commands: `init`, `run --issue <N>`, `run resume <run_id>`, `run show <run_id>`, `run list`, `cleanup <run_id>`, `daemon start|stop|status`, `grep <pattern>`.
- **Acceptance**: `atelier run --issue 42 --repo path/to/demo` initiates a workflow, writes to filesystem, prints Run ID.
- **Output**: Primary user interface
- **Blocks**: W16

### W16 — HTTP Daemon + SSE

- **Depends**: W15
- **Owns**: `atelier/daemon/server.py`, `atelier/daemon/routes.py`
- **Scope**: FastAPI app exposing: `POST /runs` (start), `GET /runs/<id>` (status), `GET /runs/<id>/events` (SSE stream of audit events), `POST /runs/<id>/approve` (gate approvals). Same process as CLI but daemon mode.
- **Acceptance**: An HTTP client subscribes to SSE and receives events in real-time as workflow advances. Used for future IDE/web/CI integrations.
- **Output**: API surface for future non-CLI clients (optional in Phase 0 — build only if time permits after W15 CLI ships).
- **Blocks**: (nothing in Phase 0; future clients depend on this)

### W18 — UAT Persona Integration

- **Depends**: W04
- **Owns**: `atelier/personas/uat.py`, `.atelier/defaults/personas/uat.md`
- **Scope**: UAT persona launches user's existing `ccc/skills/uat-testing` as subprocess. Feeds test account creds from `env.local`. Captures test report, parses to EvidencePack findings.
- **Acceptance**: Demo app has a login flow; UAT persona runs skill against it, produces structured Evidence Pack section "UAT: 3/3 passed".
- **Output**: UAT stage implementation
- **Blocks**: (slotted into W11 workflow before cleanup)

### W19 — LLM Swappability Test

- **Depends**: W02, W04
- **Owns**: `demo/swap-demo.md`, test script
- **Scope**: Demo scenario where Reviewer is Claude, then swap to Codex (or Qwen). Runs same review twice, shows Evidence Packs side-by-side. Proves LLM-agnosticism is real, not claimed.
- **Acceptance**: Both runs produce valid Evidence Packs (may differ in findings, that's fine). Capability manifest correctly rejects routes to insufficient models.
- **Output**: Demo beat that proves swappability
- **Blocks**: (standalone demo asset)

### W21 — 3-Agent Council Tiebreaker

- **Depends**: W02, W04
- **Owns**: `atelier/council/tiebreaker.py`
- **Scope**: 3-agent council triggered when Coder↔Reviewer deadlock after 2 rounds. Protocol: send Coder's position + Reviewer's position + full context to 3 different models. Each votes VERDICT_COMPATIBLE_WITH_{CODER,REVIEWER,NEITHER}. Majority wins; ties go to human.
- **Acceptance**: Fixture deadlock scenario → 3 council calls → majority verdict → Evidence Pack records tiebreaker outcome.
- **Output**: Escalation resolution for disagreements
- **Blocks**: (integrated into workflow engine escalation path)

### W22 — Example Project (integration test target)

- **Depends**: none (parallel with everything)
- **Owns**: `examples/app/*`
- **Scope**: A real, minimal FastAPI app with: auth flow, CRUD endpoint, existing tests. Serves as the integration test target for E2E validation and as documentation for new users learning Atelier. Not a toy — a legitimate small project that exercises the full workflow.
- **Acceptance**: App runs locally, login works, tests pass, there is at least one real feature request filed as an issue.
- **Output**: Reference project for integration testing and onboarding
- **Blocks**: W24

### W23 — Example Issue

- **Depends**: W22
- **Owns**: `examples/issue.md`
- **Scope**: A real issue against the example project. Must be specific, testable, adversarially-reviewable (Reviewer can find legitimate edge cases), and UAT-able. Example: "Add rate limiting to /api/login — max 5 attempts per minute per IP. Must return 429 with Retry-After header."
- **Acceptance**: Issue is concrete; acceptance criteria are testable; UAT can validate via real interaction.
- **Output**: Reference issue for integration testing
- **Blocks**: W24

### W24 — Integration Tests + E2E Validation

- **Depends**: W11, W15, W22, W23
- **Owns**: `tests/integration/`, CI config
- **Scope**: Run the full workflow against the example project + example issue end-to-end. Validate every component integrates correctly: Context Compiler → Persona → Workflow Engine → Evidence Pack → ADR → Git Hygiene. Write repeatable integration tests. Set up CI pipeline (GitHub Actions) so every PR runs the integration suite.
- **Acceptance**: Full workflow run completes against example app. All stages produce correct artifacts on filesystem. Integration tests pass in CI. Tests are repeatable (not dependent on cached state).
- **Output**: CI-verified E2E validation
- **Blocks**: (nothing — final validation gate for Phase 0 completion)

### W26 — Git Hygiene Module

- **Depends**: W01, W03, W13
- **Owns**: `atelier/git/worktree.py`, `atelier/git/rebase_analyzer.py`, `atelier/git/cleanup.py`
- **Scope**: Worktree create from main with naming convention `worktrees/<run_id>/`. Rebase analyzer: `git fetch`, `git rebase --dry-run` equivalent (use `git merge-tree` for conflict simulation without state mutation). Structured conflict report (files, hunks, suggested resolutions — NEVER applied). Cleanup: `git worktree remove` with confirmation.
- **Acceptance**: On a conflicted branch, rebase-analyzer reports N conflicts with file:line precision and suggestions. Zero state mutation.
- **Output**: Safe git automation
- **Blocks**: W18 (integrated into workflow at rebase-before-pr stage)

---

## Integration Contracts (freeze early)

| Contract | Owner | Consumers |
|---|---|---|
| CLI command contract (args, `--json` output shape) | Lane A | All users; scripts; CI |
| Evidence Pack JSON schema | Lane B | Lane A (audit linkage, CLI `show --evidence`), future clients |
| Context Packet markdown structure | Lane A + Lane B | Lane B (personas consume) |
| Persona capability declaration format | Lane A | Lane B (personas declare) |
| Skill frontmatter schema | Lane B | Lane A (workflow engine loads) |
| LLM adapter interface | Lane A | Lane B (personas call) |
| HTTP API (foundation for future client surfaces) | Lane A | Future IDE / web / CI clients |

**Freeze deadline**: end of first integration block. After freeze, changes require cross-lane sign-off.

---

## What's Deferred to Later Phases (reference)

See `roadmap.md` Phase 1+:
- Parallel worktree orchestration (Phase 2)
- Full MAD / Council protocols — only tiebreaker in Phase 0 (Phase 1)
- Meta-Observation Gates (Phase 2)
- Memory namespaces — repo-local only in Phase 0 (Phase 3)
- MemoryBackend pluggable interface + cross-agent sync evaluation (Phase 3)
- Replay / eval harness (Phase 3)
- Full rule precedence — 2 levels in Phase 0, 5 levels later (Phase 3)
- Event bus, OpenTelemetry (Phase 4)
- IDE extensions — VSCode, Zed (Phase 5)
- Web dashboard, GitHub App (Phase 6)
- Team / org scaling (Phase 7)
