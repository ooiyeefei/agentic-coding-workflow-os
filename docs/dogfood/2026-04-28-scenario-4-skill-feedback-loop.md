---
date: 2026-04-28
scenario: 4 — Skill self-improvement loop
operator: claude-code (autonomous)
result: works end-to-end; both bugs found are now fixed in #69
---

# Dogfood — Skill Self-Improvement Loop

> **Status (2026-04-28, post-fix)**: both bugs found in this scenario were filed as #65 and shipped in **PR #69** (merged). The cumulative-rule-application path now dedupes per-rule rather than by marker presence, and the appended heading carries a leading blank line.

## What I ran

Three synthetic `SkillOutcome` JSON entries staged in `/tmp/skill_outcomes/`:

1. `strong_match.json` — `error_type: missed_bug` + message mentioning "Public API contract changed"
2. `weak_match.json` — `error_type: root_cause_missed` + message about timeout vs lock contention
3. `fallback_no_match.json` — novel `error_type: ui_regression_unknown_category`

Then exercised the four code paths:

```bash
uv run spanweave skill_feedback derive --entry <each entry>      # derive only
uv run spanweave skill_feedback derive --entry strong_match.json \
  --skill-file /tmp/skill_outcomes/test_skill/SKILL.md --apply  # apply first time
# (re-run to test idempotency)
# (apply different entry to test additivity)
```

## What worked

- All three derivation paths produced the rule the design predicts:
  - **strong**: matched `api_contract_change` (score 2 from error_type + 1+ pattern hits) — exact rule from `.spanweave/defaults/feedback_rules/api_contract_change.yaml`
  - **weak**: matched `root_cause_vs_symptom` (score 2 from error_type alone)
  - **fallback**: no rule scored above 0 → generic FALLBACK_RULE with the failure message appended (truncated to 140 chars per design)
- Output is human-readable: error_type, error_message, derived rule, rationale, matched pattern id, fallback flag — all printed.
- `--apply` produces a clear unified diff *before* writing, then writes. Good operator UX.
- **Idempotency on same rule**: re-running `--apply` with the same entry produces "(no changes)" and the file is unchanged.
- The `<!-- Added by spanweave.learning.feedback_loop -->` marker is the dedupe sentinel — clear, greppable, machine-readable.

## What broke

### Bug 1 — `patch_skill_file` drops second rule silently (HIGH) — FIXED in #69

When a SKILL.md already had any learned rule applied, applying a *different* rule did nothing — silently. Caused by too-coarse idempotency in `patch_skill_file` (bailing on marker presence alone). Fixed by dedupe at per-rule granularity (checking if the rendered bullet line is already present) and appending under a single `## Learned Rules` section.

### Bug 2 — Missing blank line before appended `## Learned Rules` heading (LOW) — FIXED in #69

`build_rule_block` opened with `"\n"` while `patch_skill_file` did `skill_text.rstrip() + rule_block`, eating the blank line. Fixed by opening with `"\n\n"` and ensuring the heading is preceded by a blank line when extending an existing section.

## What surprised me

- **The YAML rule library is small but well-aimed**: only 5 rules cover the most common `error_type` values (`missed_bug`, `root_cause_missed`, `regression_missed`, `api_contract`, `insufficient_verification`, `wrong_fix`). This matches the "files first, indexes second" principle — the rule set is auditable, not opaque.
- **Scoring is intentionally simple**: error_type +2, each regex match +1. No weighting, no semantic similarity, no embeddings. This is correct for the substrate-not-platform thesis: a user can read the YAML and predict what will match without running the system.
- **The fallback rule embeds the original failure message** (truncated to 137 chars + ellipsis). This means even the "no match" path produces a *traceable* rule. A reviewer reading the SKILL.md can see exactly what failure prompted the generic rule.

## Bugs filed

- **#65** (closed when #69 merged) — both bugs above filed together
- **#69** (merged) — fix shipped: per-rule dedupe + leading-blank-line for heading

## Did not try

- Real `SkillOutcome` written to `.spanweave/memory/skill_outcomes/` (the dir doesn't exist; would have created it; held off to keep this scenario non-mutating to real memory)
- Multiple entries chained
- The `learned_rule_candidate` explicit-override path (third branch in `derive_rule_from_outcome`)

## Verdict

The feature works as designed for first-application. After #69 the loop also accumulates rules across multiple failures, so a corpus of SkillOutcomes can now meaningfully shape SKILL.md over time.
