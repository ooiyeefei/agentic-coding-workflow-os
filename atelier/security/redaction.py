from __future__ import annotations

import re
from collections.abc import Iterable
from re import Match

from .patterns import (
    BEARER_TOKEN_PATTERN,
    GCP_PRIVATE_KEY_ID_PATTERN,
    REDACTION_MARKER_PATTERN,
    SENSITIVE_ENV_ASSIGNMENT_PATTERN,
    SENSITIVE_ENV_NAME_PATTERNS,
    SENSITIVE_JSON_VALUE_PATTERN,
    URL_CREDENTIALS_PATTERN,
    WHOLE_MATCH_PATTERNS,
    SecretPattern,
)


def redact(
    text: str,
    extra_patterns: list[str] | None = None,
    *,
    secrets: Iterable[str] | None = None,
) -> str:
    if not text:
        return text

    redacted = text
    for secret in _sorted_secrets(secrets):
        redacted = redacted.replace(secret, _marker("secret"))

    compiled_extra_patterns = tuple(
        SecretPattern(name=f"extra-pattern-{index}", regex=re.compile(pattern))
        for index, pattern in enumerate(extra_patterns or (), start=1)
    )

    parts = re.split(f"({REDACTION_MARKER_PATTERN.pattern})", redacted)
    return "".join(
        part
        if REDACTION_MARKER_PATTERN.fullmatch(part)
        else _redact_segment(part, compiled_extra_patterns)
        for part in parts
        if part
    )


def _redact_segment(text: str, extra_patterns: tuple[SecretPattern, ...]) -> str:
    redacted = URL_CREDENTIALS_PATTERN.sub(_replace_url_credentials, text)
    redacted = GCP_PRIVATE_KEY_ID_PATTERN.sub(
        lambda match: _replace_wrapped_value(match, "gcp-private-key-id"),
        redacted,
    )
    redacted = BEARER_TOKEN_PATTERN.sub(_replace_bearer_token, redacted)

    for pattern in WHOLE_MATCH_PATTERNS:
        redacted = pattern.regex.sub(_replace_whole_match(pattern.name), redacted)

    redacted = SENSITIVE_ENV_ASSIGNMENT_PATTERN.sub(_replace_sensitive_env_assignment, redacted)
    redacted = SENSITIVE_JSON_VALUE_PATTERN.sub(_replace_sensitive_json_value, redacted)

    for pattern in extra_patterns:
        redacted = pattern.regex.sub(_replace_whole_match(pattern.name), redacted)

    return redacted


def _replace_url_credentials(match: Match[str]) -> str:
    return (
        f"{match.group('scheme')}{_marker('url-username')}:"
        f"{_marker('url-password')}@{match.group('rest')}"
    )


def _replace_wrapped_value(match: Match[str], marker_name: str) -> str:
    value = match.group("value")
    if REDACTION_MARKER_PATTERN.fullmatch(value):
        return match.group(0)

    return f"{match.group('prefix')}{_marker(marker_name)}{match.group('suffix')}"


def _replace_whole_match(marker_name: str):
    marker = _marker(marker_name)

    def replacer(match: Match[str]) -> str:
        return match.group(0) if REDACTION_MARKER_PATTERN.fullmatch(match.group(0)) else marker

    return replacer


def _replace_sensitive_env_assignment(match: Match[str]) -> str:
    key = match.group("key")
    marker_name = _marker_name_for_env_key(key)
    if marker_name is None:
        return match.group(0)

    value = match.group("value")
    opening_quote, inner_value, closing_quote = _unwrap_quoted_value(value)
    if not inner_value:
        return match.group(0)

    return (
        f"{key}{match.group('sep')}{opening_quote}"
        f"{_env_value_marker(inner_value, marker_name)}{closing_quote}"
    )


def _replace_sensitive_json_value(match: Match[str]) -> str:
    key = match.group("key")
    marker_name = _marker_name_for_env_key(key)
    if marker_name is None:
        return match.group(0)

    value = match.group("value")
    if REDACTION_MARKER_PATTERN.fullmatch(value):
        return match.group(0)

    return f'"{key}"{match.group("sep")}"{_marker(marker_name)}"'


def _replace_bearer_token(match: Match[str]) -> str:
    token = match.group("token")
    if not _should_redact_bearer_token(token):
        return match.group(0)

    return f"{match.group('prefix')}{_marker('bearer-token')}"


def _should_redact_bearer_token(token: str) -> bool:
    if REDACTION_MARKER_PATTERN.fullmatch(token):
        return False

    if any(not character.isalpha() for character in token):
        return True

    return len(token) >= 20


def _marker_name_for_env_key(key: str) -> str | None:
    for marker_name, pattern in SENSITIVE_ENV_NAME_PATTERNS:
        if pattern.search(key):
            return marker_name

    return None


def _unwrap_quoted_value(value: str) -> tuple[str, str, str]:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        quote = value[0]
        return quote, value[1:-1], quote

    return "", value, ""


def _env_value_marker(value: str, marker_name: str) -> str:
    marker_matches = REDACTION_MARKER_PATTERN.findall(value)
    if len(marker_matches) == 1 and marker_name == "api-key":
        return marker_matches[0]

    if len(marker_matches) == 1 and REDACTION_MARKER_PATTERN.fullmatch(value):
        return marker_matches[0]

    return _marker(marker_name)


def _marker(name: str) -> str:
    return f"[REDACTED:{name}]"


def _sorted_secrets(secrets: Iterable[str] | None) -> list[str]:
    unique_values = {secret for secret in secrets or () if secret}
    return sorted(unique_values, key=len, reverse=True)


__all__ = ["redact"]
