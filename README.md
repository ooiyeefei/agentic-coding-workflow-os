# Spanweave

> **Name**: Spanweave (the agentic coding workflow OS)
>
> _The Python package, CLI command, and `.atelier/` config directory are named `atelier` for historical reasons; a separate Phase 1 task will align them with the product name._

The **shared knowledge substrate** for AI-assisted engineering. Markdown files in git — readable by any agent tool, writable by any agent tool, syncable by git. No new platform to adopt. No switching cost. Decisions persist. Context follows you.

**Origin**: Distilled from a battle-tested workflow on a safety-critical HAZOP/LOPA AI system where wrong outputs could kill people.

## The Thesis

Developers use individual agent tools — Claude Code, Codex, Cursor, ChatGPT, Gemini, Cowork. These are personal and individualistic. Context dies with each session. Decisions evaporate. Switching tools means starting from zero.

Spanweave solves this with **files in git** as the shared substrate. Not a platform. Not another tool to adopt. A `.atelier/` directory in your repo that every agent tool can read, containing decisions, evidence, context, and rules in markdown.

**Session swap**: `atelier resume --agent claude-code` — picks up where Codex left off, full context.
**Multi-agent**: `atelier prompt --role coder --agent codex` + `atelier prompt --role reviewer --agent claude-code` — each gets the right context for their role.
**Team collaboration**: Alice uses Claude Code, Bob uses Codex. Both read/write `.atelier/memory/`. Git syncs. No shared platform needed.

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

Phase 0 build in progress. 21 of 24 original components merged to main. Architectural reframe underway: replacing direct LLM API approach with **Tool Adapter Layer** (Claude Code, Codex adapters) + **Session Continuity** (resume, prompt, context commands). 3 new worktrees added (W27, W28, W29). See [`phase0_plan.md`](./phase0_plan.md) for current progress and next steps.

## License

Apache 2.0 — see [LICENSE](./LICENSE)

## Inspirations

- [GitHub spec-kit](https://github.com/github/spec-kit) — spec-driven development
- [MADR 3.0](https://adr.github.io/madr/) — ADR format
- [Karpathy LLM Council](https://github.com/karpathy/llm-council) — 3-stage ensemble with anonymized peer ranking
- [Du et al. 2023 Multi-Agent Debate (MAD)](https://arxiv.org/abs/2305.14325)
- [SARIF](https://sarifweb.azurewebsites.net/) — inspiration for Evidence Pack as an open spec
- TIROS HAZOP engineering discipline — execution-mandatory review, data integrity, safety fallback conventions
