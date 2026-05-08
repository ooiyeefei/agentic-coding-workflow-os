from __future__ import annotations

import pytest
from spanweave.security.redaction import redact


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("OPENAI_API_KEY=sk-abc123xyz", "OPENAI_API_KEY=[REDACTED:openai-key]"),
        ('openai_api_key="sk-abc123xyz"', 'openai_api_key="[REDACTED:openai-key]"'),
        ("STRIPE_SECRET_KEY=pk_live_12345abcde", "STRIPE_SECRET_KEY=[REDACTED:pk-token]"),
        ("ghp_abcd1234efgh5678", "[REDACTED:github-pat]"),
        ("GITHUB_TOKEN=ghp_abcd1234efgh5678", "GITHUB_TOKEN=[REDACTED:github-pat]"),
        ("ghs_abcd1234efgh5678", "[REDACTED:github-server-token]"),
        ("xoxb-123456789012-abcdefghij", "[REDACTED:slack-bot-token]"),
        ("xoxp-123456789012-abcdefghij", "[REDACTED:slack-user-token]"),
        (
            "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.xxx",
            "Bearer [REDACTED:bearer-token]",
        ),
        (
            "authorization: Bearer abcd1234.token-value",
            "authorization: Bearer [REDACTED:bearer-token]",
        ),
        (
            "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
            "AWS_ACCESS_KEY_ID=[REDACTED:aws-access-key-id]",
        ),
        ("AKIAIOSFODNN7EXAMPLE", "[REDACTED:aws-access-key-id]"),
        ("PASSWORD=hunter2", "PASSWORD=[REDACTED:password]"),
        ('password = "hunter2"', 'password = "[REDACTED:password]"'),
        ("TOKEN='abc123xyz'", "TOKEN='[REDACTED:token]'"),
        ("session_token=abc123xyz", "session_token=[REDACTED:token]"),
        ("SECRET=supersecretvalue", "SECRET=[REDACTED:secret]"),
        ("DB_SECRET_KEY=supersecretvalue", "DB_SECRET_KEY=[REDACTED:secret]"),
        (
            "PRIVATE_KEY=-----BEGIN PRIVATE KEY-----abc-----END PRIVATE KEY-----",
            "PRIVATE_KEY=[REDACTED:private-key]",
        ),
        ("-----BEGIN PRIVATE KEY-----abc-----END PRIVATE KEY-----", "[REDACTED:private-key]"),
        (
            '{"private_key_id":"1234abcd5678efgh"}',
            '{"private_key_id":"[REDACTED:gcp-private-key-id]"}',
        ),
        (
            (
                '{"private_key":"-----BEGIN PRIVATE KEY-----\\\\nabc\\\\n'
                '-----END PRIVATE KEY-----\\\\n"}'
            ),
            '{"private_key":"[REDACTED:private-key]"}',
        ),
        (
            "DATABASE_URL=postgres://user:pass@host/db",
            "DATABASE_URL=postgres://[REDACTED:url-username]:[REDACTED:url-password]@host/db",
        ),
        (
            "postgres://user:pass@host/db",
            "postgres://[REDACTED:url-username]:[REDACTED:url-password]@host/db",
        ),
        (
            "OPENAI_API_KEY=sk-abc123xyz GITHUB_TOKEN=ghp_abcd1234efgh5678",
            "OPENAI_API_KEY=[REDACTED:openai-key] GITHUB_TOKEN=[REDACTED:github-pat]",
        ),
        (
            "xoxb-123456789012-abcdefghij and xoxp-123456789012-abcdefghij",
            "[REDACTED:slack-bot-token] and [REDACTED:slack-user-token]",
        ),
        (
            "token=postgres://user:pass@host/db",
            "token=[REDACTED:token]",
        ),
        ("export API_KEY=plain-secret-value", "export API_KEY=[REDACTED:api-key]"),
        ('api_key="plain-secret-value"', 'api_key="[REDACTED:api-key]"'),
        ("PRIVATE_KEY_ID=abc123xyz", "PRIVATE_KEY_ID=[REDACTED:private-key]"),
        (
            "Bearer abcdef12 and AKIAIOSFODNN7EXAMPLE",
            "Bearer [REDACTED:bearer-token] and [REDACTED:aws-access-key-id]",
        ),
        (
            'OPENAI_API_KEY="sk-abc123xyz" # keep comment',
            'OPENAI_API_KEY="[REDACTED:openai-key]" # keep comment',
        ),
    ],
)
def test_redact_positive_cases(raw_text: str, expected: str) -> None:
    assert redact(raw_text) == expected


@pytest.mark.parametrize(
    "raw_text",
    [
        "hello world",
        "skateboard",
        "tokenizer",
        "public_keynote",
        "xoxo-party",
        "gh-pages",
        "pk_notes_only",
        "sk-inspection",
        "Bearer plainword",
        "DATABASE_URL=postgres://host/db",
        "MY_TOKENIZER_MODE=fast",
        "PRIVATE_KEYWORDS=notes",
    ],
)
def test_redact_negative_cases(raw_text: str) -> None:
    assert redact(raw_text) == raw_text


def test_redact_keeps_existing_markers_readable() -> None:
    text = "TOKEN=[REDACTED:token] and OPENAI_API_KEY=[REDACTED:openai-key]"

    assert redact(text) == text


def test_redact_supports_extra_patterns_with_stable_labels() -> None:
    text = "ACME_VALUE=foo BAR_VALUE=bar"

    redacted = redact(text, extra_patterns=[r"foo", r"bar"])

    assert (
        redacted
        == "ACME_VALUE=[REDACTED:extra-pattern-1] BAR_VALUE=[REDACTED:extra-pattern-2]"
    )


def test_redact_applies_builtin_and_extra_patterns_together() -> None:
    text = "OPENAI_API_KEY=sk-abc123xyz ACME_VALUE=foo"

    redacted = redact(text, extra_patterns=[r"foo"])

    assert (
        redacted
        == "OPENAI_API_KEY=[REDACTED:openai-key] ACME_VALUE=[REDACTED:extra-pattern-1]"
    )


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        (
            "PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\\nabc\\n-----END RSA PRIVATE KEY-----",
            "PRIVATE_KEY=[REDACTED:private-key]",
        ),
        (
            "PRIVATE_KEY=-----BEGIN EC PRIVATE KEY-----\\nabc\\n-----END EC PRIVATE KEY-----",
            "PRIVATE_KEY=[REDACTED:private-key]",
        ),
        (
            "PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----\\nabc\\n"
            "-----END OPENSSH PRIVATE KEY-----",
            "PRIVATE_KEY=[REDACTED:private-key]",
        ),
        (
            "-----BEGIN RSA PRIVATE KEY-----\\nabc\\n-----END RSA PRIVATE KEY-----",
            "[REDACTED:private-key]",
        ),
    ],
)
def test_redact_covers_private_key_variants(raw_text: str, expected: str) -> None:
    assert redact(raw_text) == expected


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("PASSWORD=abc#def", "PASSWORD=[REDACTED:password]"),
        ("TOKEN=abc#def", "TOKEN=[REDACTED:token]"),
        ("SECRET=abc#def", "SECRET=[REDACTED:secret]"),
        ("API_KEY=abc#def", "API_KEY=[REDACTED:api-key]"),
        ("OPENAI_API_KEY=sk-abc123xyz#def", "OPENAI_API_KEY=[REDACTED:openai-key]"),
    ],
)
def test_redact_covers_unquoted_env_values_with_hash_characters(
    raw_text: str,
    expected: str,
) -> None:
    assert redact(raw_text) == expected


def test_redact_alphabetic_bearer_tokens() -> None:
    raw_text = "Authorization: Bearer abcdefghijklmnopqrstuvwxyzABCDEFG"

    assert redact(raw_text) == "Authorization: Bearer [REDACTED:bearer-token]"
