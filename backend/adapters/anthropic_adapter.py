import base64
import httpx


async def call_anthropic_vision(
    image_bytes: bytes,
    mime_type: str,
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> str:
    """调用 Anthropic 兼容 Messages API，以 base64 图片分析并返回诊断文本。"""
    if base_url is None or base_url.strip() == "":
        base_url = "https://api.anthropic.com"
    base_url = base_url.rstrip("/")

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_message},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": b64,
                        },
                    },
                ],
            }
        ],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}/v1/messages", json=payload, headers=headers
        )
        resp.raise_for_status()
        body = resp.json()
        return body["content"][0]["text"]
