# Research: Policy Engine

## Decision 1: Signal approval gates with boolean returns instead of exceptions

- **Decision**: Keep `requires_approval(stage, context)` as a pure boolean query and leave pause-and-approval orchestration to the workflow layer.
- **Rationale**: The feature brief already defines `requires_approval(...) -> bool`, and a query-style API keeps policy logic separate from workflow control flow.
- **Alternatives considered**:
  - Raise an approval-needed exception: rejected because it would mix policy evaluation with stage-execution mechanics.
  - Return a richer enum in Phase 0: rejected because the accepted contract is already a boolean and no additional states are required yet.

## Decision 2: Default unknown `git-*` operations to dry run unless explicitly known to be read-only

- **Decision**: Treat any `git-*` operation as dry-run by default except for a small allowlist of known read-only operations such as `git-status`, `git-diff`, and `git-fetch`.
- **Rationale**: Phase 0 is intentionally conservative, and under-classifying a mutating git operation is riskier than unnecessarily marking an unknown operation as dry-run.
- **Alternatives considered**:
  - Maintain only a mutating allowlist: rejected because an unlisted mutating operation would silently lose dry-run protection.
  - Force dry-run for every `git-*` operation including read-only ones: rejected because it would distort behavior for inspection commands that do not mutate state.

## Decision 3: Aggregate spend from JSONL audit files with flexible cost-field extraction

- **Decision**: Read cost totals from per-run and daily JSONL audit logs, accepting either direct numeric fields like `cost_usd` or nested structures like `data.cost.total_usd`.
- **Rationale**: W13 is adjacent work that may evolve event schemas slightly, so the policy layer should be tolerant of the normalized cost locations already implied by existing LLM response objects.
- **Alternatives considered**:
  - Require one exact audit schema now: rejected because W13 is not merged yet and strict coupling would create avoidable churn.
  - Read from a database or service: rejected because Phase 0 is explicitly files-only.

## Decision 4: Enforce caps on projected totals and allow equality at the cap

- **Decision**: `check_cost(run_id, proposed_cost)` computes projected run and daily totals by adding the proposed incremental cost to current aggregates, allows totals equal to the cap, and raises only when a projected total exceeds the cap.
- **Rationale**: A cap is conventionally inclusive, and the acceptance criteria explicitly call for boundary coverage around $4.99, $5.00, and $5.01.
- **Alternatives considered**:
  - Reject when projected total is equal to the cap: rejected because it would make the configured cap behave like a strict upper bound below the documented value.
  - Record costs after the call and check later: rejected because policy should stop the overspend before it happens.

## Decision 5: Fail loudly on malformed audit lines

- **Decision**: Raise an error when an audit log line contains invalid JSON instead of silently skipping it.
- **Rationale**: Silent undercounting would weaken the safety guarantee of cost caps, while a hard failure surfaces log corruption immediately.
- **Alternatives considered**:
  - Skip malformed lines and continue: rejected because it can produce false negatives for cap enforcement.
  - Count malformed lines as zero cost: rejected because it hides data quality issues and still undercounts.
