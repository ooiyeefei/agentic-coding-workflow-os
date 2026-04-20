from __future__ import annotations

import re
from dataclasses import dataclass
from re import Pattern


@dataclass(frozen=True, slots=True)
class SecretPattern:
    name: str
    regex: Pattern[str]


REDACTION_MARKER_PATTERN = re.compile(r"\[REDACTED:[^\]\r\n]+\]")

URL_CREDENTIALS_PATTERN = re.compile(
    r"(?P<scheme>\b[a-z][a-z0-9+.\-]*://)"
    r"(?P<username>[^:/@\s]+):(?P<password>[^@/\s]+)@(?P<rest>[^\s'\"<>]+)",
    re.IGNORECASE,
)

BEARER_TOKEN_PATTERN = re.compile(
    r"(?P<prefix>\bBearer\s+)"
    r"(?P<token>[A-Za-z0-9._~+/=-]{8,})",
    re.IGNORECASE,
)

GCP_PRIVATE_KEY_ID_PATTERN = re.compile(
    r'(?P<prefix>"private_key_id"\s*:\s*")(?P<value>[^"\r\n]+)(?P<suffix>")',
    re.IGNORECASE,
)

SENSITIVE_ENV_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<key>\b[A-Za-z_][A-Za-z0-9_]{0,63}\b)(?P<sep>\s*=\s*)(?P<value>\"[^\"]*\"|'[^']*'|[^\s]+)"
)

SENSITIVE_ENV_NAME_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    ("api-key", re.compile(r"(?:^|_)API_KEY(?:_|$)", re.IGNORECASE)),
    ("private-key", re.compile(r"(?:^|_)PRIVATE_KEY(?:_|$)", re.IGNORECASE)),
    ("password", re.compile(r"(?:^|_)PASSWORD(?:_|$)", re.IGNORECASE)),
    ("token", re.compile(r"(?:^|_)TOKEN(?:_|$)", re.IGNORECASE)),
    ("secret", re.compile(r"(?:^|_)SECRET(?:_|$)", re.IGNORECASE)),
)

WHOLE_MATCH_PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern(
        name="openai-key",
        regex=re.compile(
            r"(?<![A-Za-z0-9])sk-(?=[A-Za-z0-9._\-]{7,})(?=[A-Za-z0-9._\-]*\d)[A-Za-z0-9._\-]+(?![A-Za-z0-9])"
        ),
    ),
    SecretPattern(
        name="pk-token",
        regex=re.compile(
            r"(?<![A-Za-z0-9])pk_(?=[A-Za-z0-9._\-]{7,})(?=[A-Za-z0-9._\-]*\d)[A-Za-z0-9._\-]+(?![A-Za-z0-9])"
        ),
    ),
    SecretPattern(
        name="github-pat",
        regex=re.compile(r"(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{8,}(?![A-Za-z0-9])"),
    ),
    SecretPattern(
        name="github-server-token",
        regex=re.compile(r"(?<![A-Za-z0-9])ghs_[A-Za-z0-9]{8,}(?![A-Za-z0-9])"),
    ),
    SecretPattern(
        name="slack-bot-token",
        regex=re.compile(r"(?<![A-Za-z0-9])xoxb-[A-Za-z0-9-]{10,}(?![A-Za-z0-9])"),
    ),
    SecretPattern(
        name="slack-user-token",
        regex=re.compile(r"(?<![A-Za-z0-9])xoxp-[A-Za-z0-9-]{10,}(?![A-Za-z0-9])"),
    ),
    SecretPattern(
        name="aws-access-key-id",
        regex=re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
    ),
    SecretPattern(
        name="private-key",
        regex=re.compile(
            r"-----BEGIN (?P<label>(?:RSA|DSA|EC|OPENSSH|ENCRYPTED)\s+PRIVATE KEY|PRIVATE KEY)-----"
            r"[\s\S]+?"
            r"-----END (?P=label)-----"
            r"(?:\\\\r\\\\n|\\\\n|\\\\r|[\r\n])*"
        ),
    ),
)


__all__ = [
    "BEARER_TOKEN_PATTERN",
    "GCP_PRIVATE_KEY_ID_PATTERN",
    "REDACTION_MARKER_PATTERN",
    "SENSITIVE_ENV_ASSIGNMENT_PATTERN",
    "SENSITIVE_ENV_NAME_PATTERNS",
    "SecretPattern",
    "URL_CREDENTIALS_PATTERN",
    "WHOLE_MATCH_PATTERNS",
]
