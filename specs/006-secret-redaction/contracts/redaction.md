# Contract: `atelier.security.redaction`

## Public Function

- `redact(text: str, extra_patterns: list[str] | None = None) -> str`

## Contract

- `redact(...)` is pure: it reads only its arguments and returns a new string.
- Built-in secret families produce markers in the format `[REDACTED:<pattern-name>]`.
- Sensitive environment-variable names are matched case-insensitively.
- Environment assignments preserve the key name and assignment shape while redacting the secret value.
- Bearer headers preserve the `Bearer ` prefix while redacting the token value.
- URL credentials preserve the overall URL structure while redacting username and password components.
- `extra_patterns` extend the built-in catalog for a single call and produce stable labels `extra-pattern-1`, `extra-pattern-2`, and so on.
- Safe strings that do not satisfy a full secret pattern return unchanged.
- Already redacted markers remain readable on repeated calls.

## Representative Examples

- `redact("OPENAI_API_KEY=sk-abc123xyz")` returns a string that keeps `OPENAI_API_KEY=` visible and replaces the secret value with a `[REDACTED:...]` marker.
- `redact("Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.xxx")` returns a string that keeps `Bearer ` visible and replaces the token value with `[REDACTED:bearer-token]`.
- `redact("DATABASE_URL=postgres://user:pass@host/db")` returns a string that preserves `postgres://`, `host`, and `/db` while redacting both credential components.
- `redact("hello world")` returns `hello world`.
