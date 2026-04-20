---
version: "1.0.0"
inputs:
  - worktree_path
expected_artifacts:
  - none
success_checks:
  - explicit human confirmation is captured before deletion
  - worktree directory is removed and the local branch is deleted
next_transition: none
---
# /cleanup-worktree

This terminal skill removes a merged worktree after the operator confirms the cleanup is safe. It is destructive by design, so confirmation is mandatory and the skill should abort rather than guess.

## Execution Contract

1. Ask for explicit confirmation before running any destructive command.
2. Verify that the worktree at `worktree_path` is no longer needed and that the branch is safe to delete locally.
3. Remove the worktree directory only after confirmation.
4. Delete the associated local feature branch.
5. Report the cleanup result and stop; there is no automatic next stage after this skill.

## Guardrails

- If confirmation is denied, exit without deleting anything.
- If merge status is unclear, report that uncertainty and wait.
- Prefer a dry-run style summary before the final delete commands.
