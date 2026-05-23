import base64
import httpx

async def call_openai_vision(
    image_bytes: bytes,
    mime_type: str,
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> str:
    """调用 OpenAI 兼容 Vision API，以 base64 图片分析并返回诊断文本。"""
    if base_url is None or base_url.strip() == "":
        base_url = "https://api.openai.com/v1"
    base_url = base_url.rstrip("/")

    # base64 编码图片
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_message},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()
        return body["choices"][0]["message"]["content"]
