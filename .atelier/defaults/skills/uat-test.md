---
version: "1.0.0"
inputs:
  - app_path
  - test_account_creds_env_var
expected_artifacts:
  - uat_report.md
success_checks:
  - the ccc/skills/uat-testing subprocess exits with code 0
  - uat_report.md is present with captured execution output
next_transition: rebase-before-pr
---
# /uat-test

This Phase 0 skill is a monitored stub around the user's existing `ccc/skills/uat-testing` workflow. It should launch that existing skill as a subprocess so the workflow engine can observe exit status, capture output, and decide whether to advance.

## Execution Contract

1. Resolve the `ccc/skills/uat-testing` path from the configured environment or the user's existing checkout.
2. Run the UAT workflow as a subprocess instead of copying its instructions inline into the current agent response.
3. Pass the application path from `app_path` and the credential variable named by `test_account_creds_env_var`.
4. Capture stdout, stderr, and the final status in `uat_report.md`.
5. If the subprocess is missing or exits non-zero, report that failure clearly and do not advance.

The workflow should transition to `/rebase-before-pr` only after the subprocess succeeds and `uat_report.md` exists.
