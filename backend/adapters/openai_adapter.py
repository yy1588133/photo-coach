import base64
import httpx


async def call_openai_vision(
    image_bytes: bytes | None,
    mime_type: str | None,
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> str:
    """调用 OpenAI 兼容 API，支持 Vision 图片分析和纯文本调用。"""
    if base_url is None or base_url.strip() == "":
        base_url = "https://api.openai.com"
    base_url = base_url.rstrip("/")

    if base_url.endswith("/v1"):
        url = f"{base_url}/chat/completions"
    else:
        url = f"{base_url}/v1/chat/completions"

    # 构建 user 消息内容
    user_content = []
    if user_message:
        user_content.append({"type": "text", "text": user_message})

    if image_bytes is not None and mime_type is not None:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"
        user_content.append({"type": "image_url", "image_url": {"url": data_url}})

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content if len(user_content) > 1 else user_content[0]["text"] if user_content else ""},
        ],
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()
        return body["choices"][0]["message"]["content"]
