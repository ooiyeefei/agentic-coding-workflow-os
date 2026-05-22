"""Shared Ollama HTTP client for extraction and reflection."""

from __future__ import annotations

import httpx

OLLAMA_BASE = "http://localhost:11434"


class OllamaNotAvailableError(Exception):
    """Raised when Ollama is not running or unreachable."""


def call_ollama(
    prompt: str,
    model: str,
    *,
    options: dict | None = None,
    timeout: float = 120.0,
) -> str:
    """Send a prompt to Ollama and return the response text.

    Args:
        prompt: The text prompt to send.
        model: Ollama model name (e.g. "gemma4:e4b").
        options: Optional model parameters (temperature, top_p, etc.).
        timeout: HTTP timeout in seconds.

    Returns:
        The model's response text.

    Raises:
        OllamaNotAvailableError: If Ollama is not running or unreachable.
    """
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if options is not None:
        payload["options"] = options

    try:
        response = httpx.post(
            f"{OLLAMA_BASE}/api/generate",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.ConnectError as exc:
        raise OllamaNotAvailableError(
            f"Ollama not running. Install: https://ollama.ai then `ollama pull {model}`"
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaNotAvailableError(
            f"Ollama not running. Install: https://ollama.ai then `ollama pull {model}`"
        ) from exc
    return response.json()["response"]


__all__ = [
    "OLLAMA_BASE",
    "OllamaNotAvailableError",
    "call_ollama",
]
