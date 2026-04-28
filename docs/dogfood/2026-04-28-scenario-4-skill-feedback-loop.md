---
date: 2026-04-28
scenario: 4 — Skill self-improvement loop
operator: claude-code (autonomous)
result: works end-to-end with one real bug found
---

# Dogfood — Skill Self-Improvement Loop

## What I ran

Three synthetic `SkillOutcome` JSON entries staged in `/tmp/skill_outcomes/`:

1. `strong_match.json` — `error_type: missed_bug` + message mentioning "Public API contract changed"
2. `weak_match.json` — `error_type: root_cause_missed` + message about timeout vs lock contention
3. `fallback_no_match.json` — novel `error_type: ui_regression_unknown_category`

Then exercised the four code paths:

```bash
uv run atelier skill_feedback derive --entry <each entry>      # derive only
uv run atelier skill_feedback derive --entry strong_match.json \
  --skill-file /tmp/skill_outcomes/test_skill/SKILL.md --apply  # apply first time
# (re-run to test idempotency)
# (apply different entry to test additivity)
```

## What worked

- All three derivation paths produced the rule the design predicts:
  - **strong**: matched `api_contract_change` (score 2 from error_type + 1+ pattern hits) — exact rule from `.atelier/defaults/feedback_rules/api_contract_change.yaml`
  - **weak**: matched `root_cause_vs_symptom` (score 2 from error_type alone)
  - **fallback**: no rule scored above 0 → generic FALLBACK_RULE with the failure message appended (truncated to 140 chars per design)
- Output is human-readable: error_type, error_message, derived rule, rationale, matched pattern id, fallback flag — all printed.
- `--apply` produces a clear unified diff *before* writing, then writes. Good operator UX.
- **Idempotency on same rule**: re-running `--apply` with the same entry produces "(no changes)" and the file is unchanged.
- The `<!-- Added by atelier.learning.feedback_loop -->` marker is the dedupe sentinel — clear, greppable, machine-readable.

## What broke

### BUG #1 — `patch_skill_file` drops second rule silently (HIGH severity)

When a SKILL.md already has any learned rule applied, applying a *different* rule does nothing — silently. Repro:

```bash
# Apply rule A — works, file gets one rule.
uv run atelier skill_feedback derive --entry strong_match.json --skill-file SKILL.md --apply
# Apply rule B (different rule) — output says "(no changes) / No changes to apply."
uv run atelier skill_feedback derive --entry weak_match.json --skill-file SKILL.md --apply
# SKILL.md still has only rule A. Rule B is lost without warning.
```

Root cause is `atelier/learning/feedback_loop.py:182-184`:

```python
if APPEND_MARKER in skill_text:
    return skill_text  # too-coarse idempotency: bails on marker presence alone
```

The marker dedupes at the wrong granularity: any prior application blocks all future ones. Likely intent was per-rule dedupe.

**Suggested fix shape (do not implement during dogfood):** dedupe by checking if the *specific rule_text* is already present in the file rather than just the marker. Or insert under a single `## Learned Rules` block that accumulates multiple bullet lines.

### BUG #2 — Missing blank line before appended `## Learned Rules` heading (LOW severity)

After `--apply`, the file looks like:

```markdown
Some pre-existing skill content here.
## Learned Rules
```

No blank line between body content and the new heading. Markdown spec is forgiving but some strict parsers (CommonMark with paragraph-extension off) won't recognize this as a heading. `build_rule_block` starts with `"\n"` but `patch_skill_file` does `skill_text.rstrip() + rule_block`, eating the blank line that the source content provided.

**Suggested fix shape:** in `build_rule_block`, change leading `"\n"` to `"\n\n"`.

## What surprised me

- **The YAML rule library is small but well-aimed**: only 5 rules cover the most common `error_type` values (`missed_bug`, `root_cause_missed`, `regression_missed`, `api_contract`, `insufficient_verification`, `wrong_fix`). This matches the "files first, indexes second" principle — the rule set is auditable, not opaque.
- **Scoring is intentionally simple**: error_type +2, each regex match +1. No weighting, no semantic similarity, no embeddings. This is correct for the substrate-not-platform thesis: a user can read the YAML and predict what will match without running the system.
- **The fallback rule embeds the original failure message** (truncated to 137 chars + ellipsis). This means even the "no match" path produces a *traceable* rule. A reviewer reading the SKILL.md can see exactly what failure prompted the generic rule.

## Bugs filed

- **#65** — both bugs above filed together: HIGH (cumulative rule application broken) + LOW (missing blank line)

## Did not try

- Real `SkillOutcome` written to `.atelier/memory/skill_outcomes/` (the dir doesn't exist; would have created it; held off to keep this scenario non-mutating to real memory)
- Multiple entries chained
- The `learned_rule_candidate` explicit-override path (third branch in `derive_rule_from_outcome`)

## Verdict

The feature works as designed for first-application. The "second rule" bug is the only thing blocking real use of the loop on a corpus of failures.
