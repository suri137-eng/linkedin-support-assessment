"""OpenAI-compatible LLM client (works with OpenAI, Azure OpenAI, or any compatible base URL).

Only infrastructure lives here. Prompt content is built in prompts.py.
"""
from __future__ import annotations

import httpx

from . import config


class LLMError(RuntimeError):
    pass


def _endpoint_and_headers() -> tuple[str, dict[str, str], dict[str, object]]:
    """Return (url, headers, extra_body) for the configured provider."""
    if config.PROVIDER == "azure":
        url = (
            f"{config.AZURE_OPENAI_ENDPOINT}/openai/deployments/"
            f"{config.AZURE_OPENAI_DEPLOYMENT}/chat/completions"
            f"?api-version={config.AZURE_OPENAI_API_VERSION}"
        )
        headers = {"api-key": config.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"}
        return url, headers, {}
    # Default: OpenAI-compatible
    url = f"{config.OPENAI_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    return url, headers, {"model": config.OPENAI_MODEL}


async def complete_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    response_format_json: bool = False,
) -> str:
    """Call the chat-completions endpoint and return the assistant text."""
    if not config.LLM_ENABLED:
        raise LLMError("LLM is not configured (running in demo mode).")

    url, headers, extra = _endpoint_and_headers()
    body: dict[str, object] = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or config.LLM_MAX_TOKENS,
        **extra,
    }
    if response_format_json:
        body["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:  # network/timeout
        raise LLMError(f"LLM request failed: {exc}") from exc

    if resp.status_code >= 400:
        raise LLMError(f"LLM returned HTTP {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected LLM response shape: {str(data)[:500]}") from exc
