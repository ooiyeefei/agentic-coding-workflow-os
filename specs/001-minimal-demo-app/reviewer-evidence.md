# Reviewer Evidence: W22 Demo Target App

**Reviewed**: 2026-04-20  
**Status**: Needs revision on workflow closure; code accepted

## Verified Behavior

- `.env.example` provides `TEST_USER=demo@atelier.dev` and `TEST_PASSWORD=demo1234`
- `demo/app/README.md` stays within the 10-line setup constraint
- `uv run pytest` passes locally
- Live server startup, login redirect, session cookie, protected `401`, and authenticated notes CRUD all work
- `specs/001-minimal-demo-app/` contains the expected `speckit` artifacts

## Reviewer Notes

- No blocking code findings were reported
- The original `spec-kit` branch name was inconsistent with the repo's `feat/W22-*` convention
- Workflow closure was incomplete because the branch had not been cleaned up, committed, rebased, or prepared for PR

## Post-Review Actions

- Renamed the working branch target in project docs to `feat/W22-demo-app`
- Kept the deliverable scope focused on `demo/` and `specs/`
- Prepared the branch for commit, rebase analysis, and PR creation
