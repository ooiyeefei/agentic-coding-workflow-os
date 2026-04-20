# Quickstart: Secret Redaction

## Verify the feature

1. Run `uv run pytest tests/test_redaction.py -v`.
2. Run `uv run ruff check atelier/security/patterns.py atelier/security/redaction.py tests/test_redaction.py`.
3. Run `uv run pyright atelier/security/patterns.py atelier/security/redaction.py tests/test_redaction.py`.

## Manual spot checks

1. Evaluate `redact("OPENAI_API_KEY=sk-abc123xyz")` and confirm the variable name remains visible while the value becomes a `[REDACTED:<pattern-name>]` marker.
2. Evaluate `redact("hello world")` and confirm the output is unchanged.
3. Evaluate `redact("Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.xxx")` and confirm only the token portion is redacted.
4. Evaluate `redact("DATABASE_URL=postgres://user:pass@host/db")` and confirm the scheme, host, and path remain visible while both credential components are redacted.
5. Evaluate `redact("ACME_VALUE=abc-123", extra_patterns=[r"abc-123"])` and confirm the custom token is redacted using an `extra-pattern-*` marker.
