# Data Model: Council Tiebreaker

## Verdict

- **Purpose**: Represents the only legal outcomes for both individual voters and the overall council result.
- **Values**:
  - `COMPATIBLE_WITH_CODER`
  - `COMPATIBLE_WITH_REVIEWER`
  - `NEITHER`
  - `HUMAN_REQUIRED`
- **Validation rules**:
  - Individual voters may only emit the first three values.
  - The final council result may use all four values.

## CouncilVote

- **Purpose**: Captures one model’s vote and normalized metadata for debugging and audit.
- **Fields**:
  - `model`: Requested model id such as `gpt-5`
  - `provider`: Provider resolved from the manifest
  - `verdict`: One of the three legal voter verdicts
  - `response_id`: Provider response identifier when available
  - `usage`: Normalized token counters
  - `cost`: Normalized cost fields
- **Validation rules**:
  - `verdict` must not be `HUMAN_REQUIRED`.
  - `model` must correspond to a resolved manifest used for the council run.

## CouncilReport

- **Purpose**: Represents one persisted council escalation outcome.
- **Fields**:
  - `id`: Stable record identifier for the report
  - `created_at`: UTC timestamp for the council run
  - `coder_position`: The position submitted on behalf of Coder
  - `reviewer_position`: The position submitted on behalf of Reviewer
  - `context`: Rendered shared context sent to the voters
  - `models`: The three model ids selected for this run
  - `votes`: Ordered list of the three `CouncilVote` entries
  - `final_verdict`: The majority verdict or `HUMAN_REQUIRED`
  - `memory_path`: Filesystem path written for the report, when persisted
- **Validation rules**:
  - `models` must contain exactly three distinct entries.
  - `votes` must contain exactly three items.
  - The ordered `votes[*].model` set must match `models`.
  - `final_verdict` must equal the majority result when one exists, otherwise `HUMAN_REQUIRED`.

## CouncilReport Memory Record

- **Purpose**: Defines how `CouncilReport` is stored on disk for Phase 0.
- **Frontmatter fields**:
  - `id`
  - `type` with value `council_report`
  - `created_at`
  - `final_verdict`
  - `models`
- **Markdown body sections**:
  - `## Positions`
  - `## Context`
  - `## Votes`
- **Validation rules**:
  - The filename uses the report id and remains stable after write.
  - The body must preserve the full per-model vote breakdown.
