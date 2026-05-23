"""
Photo Coach — FastAPI 后端入口。
提供 POST /api/analyze 接口，接收照片文件和引擎参数，返回 AI 诊断报告。
"""
import re
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 加载 .env 文件（如果存在），优先级从高到低
env_paths = [
    Path(__file__).parent / ".env",
    Path(__file__).parent / ".env.example",
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, encoding="utf-8")
        break

from adapters.openai_adapter import call_openai_vision
from adapters.anthropic_adapter import call_anthropic_vision
from prompts.diagnosis import SYSTEM_PROMPT, USER_MESSAGE_TEMPLATE

app = FastAPI(title="Photo Coach API", version="1.0.0")

# CORS 全开（MVP 阶段）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置
MAX_IMAGE_SIZE_MB = 15
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


def parse_scores_from_report(report: str) -> list[dict]:
    """从 Markdown 报告中解析评分总览表格，提取得分卡数据。"""
    scores = []
    dimension_names = [
        "构图", "曝光", "色彩", "对焦", "锐度",
        "白平衡", "面部表情", "眼神", "肢体语言", "整体印象",
    ]

    # 尝试匹配表格行：| 维度名 | ⭐⭐⭐⭐ | 简评 |
    table_pattern = r"\|\s*(.+?)\s*\|\s*(⭐+)\s*\|\s*(.+?)\s*\|"
    matches = re.findall(table_pattern, report)

    for match in matches:
        dim_name = match[0].strip()
        stars = match[1].strip()
        comment = match[2].strip()

        score = len(stars)  # 每个 ⭐ 算 1 分
        scores.append({
            "name": dim_name,
            "score": score,
            "stars": stars,
            "comment": comment,
        })

    # 如果表格解析失败，用维度名称兜底匹配
    if not scores:
        for dim_name in dimension_names:
            pattern = rf"{dim_name}\s*\|\s*(⭐+)\s*\|\s*(.+?)(?:\||$)"
            m = re.search(pattern, report)
            if m:
                stars = m.group(1).strip()
                comment = m.group(2).strip()
                scores.append({
                    "name": dim_name,
                    "score": len(stars),
                    "stars": stars,
                    "comment": comment,
                })
            else:
                scores.append({
                    "name": dim_name,
                    "score": 0,
                    "stars": "N/A",
                    "comment": "无法解析",
                })

    return scores


@app.post("/api/analyze")
async def analyze_photo(
    image: UploadFile = File(...),
    provider: str | None = Form(None),
    model: str | None = Form(None),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
):
    """分析上传的照片，返回 AI 诊断报告。

    参数：
        image: 照片文件（必填，最大 15MB，支持 JPEG/PNG/WebP/HEIC）
        provider: LLM 提供商（"openai" 或 "anthropic"，可选，默认读取 .env）
        model: 模型名称（可选，默认读取 .env）
        api_key: API 密钥（可选，默认读取 .env）
        base_url: 自定义 API 地址（可选，默认读取 .env）

    返回：
        {
            "success": true,
            "report": "Markdown 格式的完整诊断报告",
            "scores": [{name, score, stars, comment}, ...],
            "meta": {provider, model, image_size_mb, mime_type}
        }
    """
    # 校验文件类型
    mime_type = image.content_type or "image/jpeg"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {mime_type}。支持: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    # 读取图片字节并校验大小
    image_bytes = await image.read()
    image_size_mb = len(image_bytes) / (1024 * 1024)

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小 {image_size_mb:.1f}MB 超过上限 {MAX_IMAGE_SIZE_MB}MB",
        )

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    # 解析引擎配置（优先级：请求参数 > 环境变量）
    engine_provider = provider or os.getenv("DEFAULT_PROVIDER", "anthropic")
    engine_model = model or os.getenv("DEFAULT_MODEL", "claude-sonnet-4-20250514")
    engine_api_key = api_key or os.getenv("DEFAULT_API_KEY", "")
    engine_base_url = base_url or os.getenv("DEFAULT_BASE_URL", "") or None

    if not engine_api_key:
        raise HTTPException(
            status_code=400,
            detail="未配置 API Key。请在请求中提供 api_key 参数，或在 .env 中设置 DEFAULT_API_KEY",
        )

    if engine_provider not in ("openai", "anthropic"):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 provider: {engine_provider}。支持: openai, anthropic",
        )

    # 调用适配器
    try:
        if engine_provider == "openai":
            report = await call_openai_vision(
                image_bytes=image_bytes,
                mime_type=mime_type,
                system_prompt=SYSTEM_PROMPT,
                user_message=USER_MESSAGE_TEMPLATE,
                model=engine_model,
                api_key=engine_api_key,
                base_url=engine_base_url,
            )
        else:
            report = await call_anthropic_vision(
                image_bytes=image_bytes,
                mime_type=mime_type,
                system_prompt=SYSTEM_PROMPT,
                user_message=USER_MESSAGE_TEMPLATE,
                model=engine_model,
                api_key=engine_api_key,
                base_url=engine_base_url,
            )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI API 调用失败: {str(e)}",
        )

    # 解析得分
    scores = parse_scores_from_report(report)

    return {
        "success": True,
        "report": report,
        "scores": scores,
        "meta": {
            "provider": engine_provider,
            "model": engine_model,
            "image_size_mb": round(image_size_mb, 2),
            "mime_type": mime_type,
        },
    }


@app.get("/api/health")
async def health_check():
    """健康检查接口。"""
    return {"status": "ok", "service": "Photo Coach API", "version": "1.0.0"}
