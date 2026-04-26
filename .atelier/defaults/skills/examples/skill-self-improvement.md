---
name: "skill-self-improvement"
description: "Example skill demonstrating the SkillOutcome feedback loop. Adaptable to any review-and-improve workflow."
---

# Skill Self-Improvement Loop (Example)

This is an EXAMPLE skill showing how to wire SkillOutcome records and the
feedback loop together for any review/improvement task. The pattern works
for code review, architecture review, document review, test design — any
loop where an agent attempts something, gets feedback, and should learn
from weak outcomes.

## Run Loop

1. **Recall prior `SkillOutcome` feedback before starting.** Pull the most
   recent weak runs (low success_score, negative feedback) for this skill
   and inspect their `error_type`, `error_message`, and `applied_rules`.
   Use `atelier memory list --type SkillOutcome --filter "feedback<-0.3"`.

2. **Extract only the rules relevant to the current task surface.** Ignore
   stale or unrelated rules.

3. **Run the four-role pattern** (rename roles for your domain — these are
   the generic shapes):
   - **Scout**: map the surface area you're about to act on (changed files,
     affected APIs, blast radius)
   - **Critic**: predict the highest-probability failure or miss
   - **Fixer**: propose the smallest change that would address the prediction
   - **Verifier**: run or specify the narrowest check that proves it worked

4. **Produce an evidence-backed summary** with the defect/risk, the smallest
   fix, the proof from verification, and which learned rule (if any) was
   applied.

## Self-Improvement Rule

After scoring, inspect the new `SkillOutcome`.

- If `feedback` is weak (< -0.3), record exactly ONE new rule, ONLY when it
  would have prevented the miss.
- Keep the rule concrete, scoped, and reusable. Format: "When X, do Y."
- Prefer failure-pattern rules: "When a change touches X and Y together,
  always inspect Z."
- Do NOT add generic advice, duplicate existing rules, or add more than one
  rule per weak run.

## Output Expectations

Every run leaves inspectable evidence for:
- Prior feedback recalled
- Scout/Critic/Fixer/Verifier outputs (or your domain-specific role names)
- The decision and reasoning
- One concrete learned rule after weak feedback, OR an explicit note that
  no new rule was warranted

## How this connects to the rest of Atelier

- Skill outcomes persist as `SkillOutcome` records in `.atelier/memory/skill_outcomes/`.
- The feedback loop (`atelier skill_feedback derive`) auto-derives rules
  from weak outcomes, with seed rules in `.atelier/defaults/feedback_rules/`.
- Rules can be applied back to this `SKILL.md` manually or via
  `atelier skill_feedback derive --skill-file SKILL.md --apply`.

## Customize this skill

Copy this file to `.atelier/skills/<your-skill-name>.md` (drop the
`examples/` directory — that's for the shipped reference). Replace the
Scout/Critic/Fixer/Verifier role names with your domain. Adjust the
"Run Loop" steps to your specific task. The self-improvement section
should remain unchanged unless you have a domain reason to deviate.
