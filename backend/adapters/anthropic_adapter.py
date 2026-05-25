import base64
import httpx


async def call_anthropic_vision(
    image_bytes: bytes | None,
    mime_type: str | None,
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> str:
    """调用 Anthropic 兼容 Messages API，支持 Vision 图片分析和纯文本调用。"""
    if base_url is None or base_url.strip() == "":
        base_url = "https://api.anthropic.com"
    base_url = base_url.rstrip("/")

    if base_url.endswith("/v1"):
        url = f"{base_url}/messages"
    else:
        url = f"{base_url}/v1/messages"

    # 构建 user 消息内容
    user_content = []
    if user_message:
        user_content.append({"type": "text", "text": user_message})

    if image_bytes is not None and mime_type is not None:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        user_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": b64,
            },
        })

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

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()
        return body["content"][0]["text"]
