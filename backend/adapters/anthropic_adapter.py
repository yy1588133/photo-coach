"""
Anthropic-compatible Messages API adapter with timeout and retry support.
"""
import asyncio
import base64
import logging

import httpx

logger = logging.getLogger(__name__)


async def call_anthropic_vision(
    image_bytes: bytes | None,
    mime_type: str | None,
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    timeout: float = 120.0,
    max_retries: int = 2,
) -> str:
    """Call Anthropic-compatible Messages API.

    Supports vision (image) and text-only calls.
    Retries on transient HTTP errors (5xx, 429, connection errors).
    """
    if base_url is None or base_url.strip() == "":
        base_url = "https://api.anthropic.com"
    base_url = base_url.rstrip("/")

    if base_url.endswith("/v1"):
        url = f"{base_url}/messages"
    else:
        url = f"{base_url}/v1/messages"

    user_content = []
    if user_message:
        user_content.append({"type": "text", "text": user_message})

    if image_bytes is not None and mime_type is not None:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        user_content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": b64,
                },
            }
        )

    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": user_content,
            }
        ],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "5")
                    wait = float(retry_after) if retry_after.isdigit() else 5.0
                    logger.warning(
                        "Anthropic rate-limited (429). Waiting %.1fs, attempt %d/%d",
                        wait,
                        attempt + 1,
                        max_retries + 1,
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                if resp.status_code >= 500 and attempt < max_retries:
                    wait = (attempt + 1) * 2.0
                    logger.warning(
                        "Anthropic server error (%d). Retrying in %.1fs, attempt %d/%d",
                        resp.status_code,
                        wait,
                        attempt + 1,
                        max_retries + 1,
                    )
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                body = resp.json()
                return body["content"][0]["text"]
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_error = e
            if attempt < max_retries:
                wait = (attempt + 1) * 2.0
                logger.warning(
                    "Anthropic connection/timeout. Retrying in %.1fs, attempt %d/%d: %s",
                    wait,
                    attempt + 1,
                    max_retries + 1,
                    e,
                )
                await asyncio.sleep(wait)
                continue
            raise
        except httpx.HTTPStatusError as e:
            last_error = e
            if attempt < max_retries and (
                e.response.status_code >= 500 or e.response.status_code == 429
            ):
                continue
            raise

    raise last_error  # type: ignore[misc]
