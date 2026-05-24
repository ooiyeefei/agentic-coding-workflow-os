"""Shared Ollama HTTP client for extraction and reflection."""

from __future__ import annotations

from typing import Any

import httpx

OLLAMA_BASE = "http://localhost:11434"


class OllamaNotAvailableError(Exception):
    """Raised when Ollama is not running or unreachable."""


class OllamaTimeoutError(OllamaNotAvailableError):
    """Raised when Ollama is running but the model didn't respond in time.

    Subclasses ``OllamaNotAvailableError`` so existing graceful-degradation
    handlers (the Stop hook, manual commands) catch it automatically — but it
    carries a distinct message so users aren't misled into thinking the server
    is *down* when it's really *up but slow* (common with large models on
    CPU-only machines, e.g. gemma4:e4b).
    """


def ollama_available(base_url: str = OLLAMA_BASE, timeout: float = 2.0) -> bool:
    """Return True if an Ollama server answers /api/version quickly.

    Used by hook-invoked commands to fail fast and quietly instead of
    attempting extraction and erroring when no local model server is running.
    """
    try:
        resp = httpx.get(f"{base_url}/api/version", timeout=timeout)
        return resp.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def call_ollama(
    prompt: str,
    model: str,
    *,
    options: dict[str, Any] | None = None,
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
        OllamaTimeoutError: If Ollama is running but the model didn't respond
            within ``timeout`` seconds (up-but-slow).
        OllamaNotAvailableError: If Ollama is not running / unreachable, or any
            other HTTP error occurs.
    """
    payload: dict[str, Any] = {
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
        # Connection refused → the server genuinely isn't listening.
        raise OllamaNotAvailableError(
            f"Ollama not running. Install: https://ollama.ai then `ollama pull {model}`"
        ) from exc
    except httpx.TimeoutException as exc:
        # Connection established (or attempted) but no response in time → the
        # server is up but the model is too slow, NOT down. Distinct message
        # so we don't tell the user to "install Ollama" when it's installed.
        raise OllamaTimeoutError(
            f"Ollama is running but model '{model}' did not respond within "
            f"{timeout:.0f}s. On CPU-only machines try a smaller/faster model, "
            f"e.g. --model qwen2.5:1.5b."
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaNotAvailableError(f"Ollama request failed: {exc}") from exc
    return response.json()["response"]


__all__ = [
    "OLLAMA_BASE",
    "OllamaNotAvailableError",
    "OllamaTimeoutError",
    "call_ollama",
    "ollama_available",
]
