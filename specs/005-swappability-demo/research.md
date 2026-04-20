# Research: Swappability Demo

## Decision 1: Reuse the shipped Reviewer prompt body but own a demo-specific review runner

- **Decision**: Load the markdown body from `.atelier/defaults/personas/reviewer.md` for both runs, but implement the W19 review loop directly inside `demo/swap-demo.py` instead of instantiating W04's default `Reviewer` class.
- **Rationale**: W04's default Reviewer routing contract currently requires capabilities beyond the Claude manifests shipped in this repo. W19 only needs to prove the same reviewer protocol and tool contract can run across providers, so the cleanest path is to reuse the prompt body while binding the demo loop to a narrower `tool_use=True` requirement.
- **Alternatives considered**:
  - Change W04's default Reviewer requirements: rejected because it would rewrite another worktree's scope.
  - Fake the Claude run without using the shared prompt: rejected because it weakens the "same persona" claim.

## Decision 2: Generate the buggy review fixture at runtime

- **Decision**: Have the demo script create a small Python fixture and its failing pytest file inside `demo/swap-demo-output/workspace/` on each run.
- **Rationale**: This keeps the owned surface area small, guarantees the review target is reset on each execution, and avoids adding extra repo files outside the user's assigned ownership.
- **Alternatives considered**:
  - Check in a separate fixture source file: rejected because it expands ownership and makes reset behavior less obvious.
  - Embed code only in the prompt: rejected because the reviewer protocol specifically needs file reads and executed checks.

## Decision 3: Use a tiny, fixed tool contract instead of arbitrary shell access

- **Decision**: Expose a minimal pair of tools for the model loop: one tool to read the generated review artifacts and one tool to run the approved failing check.
- **Rationale**: A narrow tool surface reduces backend variance, keeps the demo deterministic, and still proves the swappability story because both providers must use the same tool API to gather evidence.
- **Alternatives considered**:
  - Expose arbitrary command execution and arbitrary file reads: rejected because it introduces needless prompt variance and safety surface for a live demo.
  - Avoid tools and paste the fixture inline: rejected because W19 explicitly needs a manifest-validated tool-use story.

## Decision 4: Support `auto`, `live`, and `mock` run modes

- **Decision**: Default the script to `auto`, meaning live provider calls run when the relevant API keys are present and deterministic mock responders take over when they are not; also allow explicit `--mode live` and `--mode mock`.
- **Rationale**: The checked-in demo needs to remain runnable in review environments where credentials are unavailable, but the live-demo beat still benefits from real provider calls whenever keys are present.
- **Alternatives considered**:
  - Require live credentials unconditionally: rejected because it would block repository review and CI.
  - Ship only mock mode: rejected because it weakens the live swappability story.

## Decision 5: Default to `claude-sonnet-4-6` and `gpt-5`, but keep model selection configurable

- **Decision**: Use the repo's shipped manifests for `claude-sonnet-4-6` and `gpt-5` as the default pair, map the OpenAI side to the public demo label `codex`, and allow overrides via CLI flags or environment variables.
- **Rationale**: These manifests already exist in the repo, align with the issue brief, and make the swap visible without source edits.
- **Alternatives considered**:
  - Hardcode model names with no override path: rejected because it undermines the "configurable swap" claim.
  - Add new manifests just for W19: rejected because the existing shipped manifests are sufficient for the demo scope.

## Decision 6: Render Evidence Packs as standalone markdown for this slice

- **Decision**: Write the W19 outputs as self-contained markdown files that include backend identity, run mode, tool transcript, command output, and final reviewer response.
- **Rationale**: The user-owned outputs are markdown files, and W19 only needs a side-by-side demo artifact rather than a full library-backed evidence schema.
- **Alternatives considered**:
  - Depend on a future Evidence Pack library API: rejected because W19 is a standalone asset today.
  - Write plain stdout logs only: rejected because the issue specifically calls for captured Evidence Packs.
