---
version: "1.0.0"
inputs:
  - worktree_path
  - target_branch
expected_artifacts:
  - conflict_report.md if conflicts exist
success_checks:
  - rebase completes cleanly or a human-approved conflict resolution is applied
  - git push --force-with-lease runs only after the rebase is complete and the human explicitly approves the push
next_transition: cleanup-worktree
---
# /rebase-before-pr

This skill packages the current worktree state, rebases it onto the mainline, and stops for human input if conflicts appear. It is explicitly an analyze-first workflow: conflict inspection and suggestion are required, automatic conflict resolution is not allowed.

The preserved prompt block below captures the user's exact wording. The workflow contract for Atelier adds one extra requirement on top of that preserved text: a successful rebase must still stop for explicit human approval before any force-with-lease push is executed.

## Required Prompt Block

```text
First, git add . to add ALL updates and commit changes we have, then run git fetch origin and git rebase origin/main. If there is any conflict, please do not decide for me first, analyse thru all conflicts if any, report back with what are the conflicts and resolution suggestions. After rebasing, push with git push --force-with-lease <feature-branch-name>.
```

## Execution Contract

1. Run `git add .` to stage all updates in the worktree.
2. Create a commit that snapshots the current branch before rebasing.
3. Run `git fetch origin` and `git rebase origin/main`.
4. If conflicts appear, stop the rebase flow and inspect every conflicted file.
5. Write `conflict_report.md` with each conflict, the competing changes, and concrete resolution suggestions.
6. Wait for the human to choose the resolution approach before continuing the rebase.
7. After the rebase completes successfully, stop and request explicit human approval for the push.
8. Only after that approval is granted, push with `git push --force-with-lease <feature-branch-name>`.

## Guardrails

- Do not auto-resolve merge conflicts.
- Do not auto-push after a clean rebase; approval is required before the final push.
- Do not hide or skip conflicted files in the report.
- If the rebase cannot continue safely, report the blocker and wait for human direction.
