# Agentic Coding Workflow OS

> Working name: **Atelier** (final naming TBD)

A **reproducibility system** for AI-assisted software engineering. Every decision traceable. Every review replayable. Every context reconstructable. LLM-agnostic by design. Files-first by philosophy.

**Origin**: Distilled from a battle-tested workflow on a safety-critical HAZOP/LOPA AI system where wrong outputs could kill people.

## The Thesis

Coding agents don't lack capability — they lack **workflow, discipline, and memory**. This product provides all three as an opinionated-but-extensible control plane that turns vibe coding into production engineering.

Not an agent framework. A reproducibility system for agentic engineering work.

## Core Ideas (one-liners)

- **Packet Engine + Context Compiler** — context assembled deterministically with priority tiers, dedupe, token budgets, and provenance
- **Execution-mandatory review** — Reviewer MUST paste real command output; approval without evidence is incomplete
- **Evidence Pack** — named artifact (JSON + Markdown) capturing every review's proof of execution
- **Typed Memory** — Decision, ReviewFinding, RejectedAlternative records auto-derive ADRs and changelogs
- **MAD at gates** — Multi-Agent Debate only on escalation (Coder↔Reviewer deadlock, complex clarifications, significant ADRs)
- **Filesystem-first** — markdown + YAML frontmatter is source of truth; git is the audit trail
- **Human-in-the-loop at destructive gates** — never auto-resolve conflicts, never auto-push
- **Steering without locking** — opinionated defaults; users override with explicit reason; deviations logged
- **LLM-agnostic** — Claude, Codex, Qwen, DeepSeek, local models, via capability manifest

## Structure

- [`roadmap.md`](./roadmap.md) — full end-to-end product roadmap, Phase 0 through Phase 8+
- [`phase0_plan.md`](./phase0_plan.md) — Phase 0 execution plan with parallel worktree DAG
- [`phase0_launch.md`](./phase0_launch.md) — paste-ready git worktree commands + coder/reviewer prompts
- `atelier/` — Python control plane
- `.atelier/defaults/` — shipped opinionated defaults (personas, skills, rules, workflows, policy)
- `examples/` — reference project + issue for integration testing and onboarding
- `tests/` — unit + integration tests
- `docs/adr/` — Architecture Decision Records (MADR 3.0)

## Status

Phase 0 build in progress. 16 of 24 components merged to main. Remaining: Workflow Engine (dynamic), Audit Log, Auto-ADR Synthesis, Git Hygiene, CLI, HTTP Daemon, Integration Tests.

## License

Apache 2.0 — see [LICENSE](./LICENSE)

## Inspirations

- [GitHub spec-kit](https://github.com/github/spec-kit) — spec-driven development
- [MADR 3.0](https://adr.github.io/madr/) — ADR format
- [Karpathy LLM Council](https://github.com/karpathy/llm-council) — 3-stage ensemble with anonymized peer ranking
- [Du et al. 2023 Multi-Agent Debate (MAD)](https://arxiv.org/abs/2305.14325)
- [SARIF](https://sarifweb.azurewebsites.net/) — inspiration for Evidence Pack as an open spec
- TIROS HAZOP engineering discipline — execution-mandatory review, data integrity, safety fallback conventions
