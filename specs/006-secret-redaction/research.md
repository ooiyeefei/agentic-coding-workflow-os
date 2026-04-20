# Research: Secret Redaction

## Decision 1: Use audit-visible markers with named pattern families

- **Decision**: Replace matched secrets with markers in the format `[REDACTED:<pattern-name>]` rather than removing text or using one anonymous placeholder.
- **Rationale**: The issue explicitly prefers audit visibility. A named marker preserves enough information for reviewers to understand what kind of secret was removed without exposing the value itself.
- **Alternatives considered**:
  - Use `<REDACTED>` for everything: rejected because it hides which pattern family fired and weakens debugging.
  - Delete matched text entirely: rejected because it destroys artifact readability and makes troubleshooting harder.

## Decision 2: Model the built-in catalog as ordered named regex rules

- **Decision**: Define the built-in secret coverage as an ordered list of named regex rules that the redaction function applies from most specific to most general.
- **Rationale**: Ordered named rules keep the behavior predictable and make it easy to attach stable marker names to individual secret families.
- **Alternatives considered**:
  - One giant alternation regex: rejected because replacement logic becomes harder to reason about and marker naming becomes brittle.
  - Independent unordered substitutions: rejected because broad patterns could consume text before more specific rules preserve the intended context.

## Decision 3: Treat environment-variable names as context, not as the secret itself

- **Decision**: Preserve the environment-variable name and assignment shape while redacting only the sensitive value, and match sensitive variable names case-insensitively.
- **Rationale**: The acceptance criteria want `OPENAI_API_KEY=...` to remain structurally recognizable. Keeping the key visible makes logs useful while still removing the credential.
- **Alternatives considered**:
  - Redact the entire assignment: rejected because it hides which field contained the secret.
  - Match env names case-sensitively: rejected because common `.env` usage mixes case and the clarification explicitly prefers case-insensitive matching.

## Decision 4: Preserve URL shape by redacting credential components separately

- **Decision**: Detect URL credentials in authority sections and replace the username and password components separately while leaving scheme, host, port, path, query, and fragment intact.
- **Rationale**: The acceptance criteria explicitly require `DATABASE_URL=postgres://user:pass@host/db` to keep its overall URL shape visible. Component-level replacement meets that requirement better than collapsing the whole URL.
- **Alternatives considered**:
  - Replace the whole URL value with one marker: rejected because it loses the host/database context reviewers need.
  - Leave usernames visible and redact only passwords: rejected because usernames can also be sensitive credentials in service accounts.

## Decision 5: Label caller-provided extra patterns by stable list order

- **Decision**: Redactions produced by `extra_patterns` use marker families `extra-pattern-1`, `extra-pattern-2`, and so on, based on the order supplied by the caller.
- **Rationale**: The function signature only accepts raw regex strings, not named pattern objects. Stable ordinal labels preserve audit visibility without changing the API.
- **Alternatives considered**:
  - Change the API to accept named mappings: rejected because the issue fixes the function signature to `list[str] | None`.
  - Use one shared `extra-pattern` label for all custom regexes: rejected because it loses which extra pattern matched when multiple customs are supplied.

## Decision 6: Prefer strict token-shape regexes over broad word-based matching

- **Decision**: Built-in patterns should match full credential shapes such as prefix-plus-length tokens, bearer tokens, AWS access keys, and known service-account fields, while negative tests guard against English-word false positives.
- **Rationale**: Regex-based redaction only works if patterns are conservative. The feature brief explicitly rejects false positives on words that merely resemble token prefixes.
- **Alternatives considered**:
  - Match any occurrence of words like `token` or `secret`: rejected because it would redact ordinary prose constantly.
  - Rely on entropy heuristics now: rejected because entropy detection is deferred to a later phase.
