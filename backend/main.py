"""
Photo Coach — FastAPI 后端入口。
提供 POST /api/analyze 接口，接收照片文件和引擎参数，返回 AI 诊断报告。
"""
import re
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

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


def compress_image(image_bytes: bytes, max_mb: float = 15) -> tuple[bytes, dict]:
    """压缩图片到目标大小以内，返回 (图片字节, 压缩信息)。

    策略：先降质量（85→30），仍超限则逐步缩小尺寸，最低长边 1024px、质量 30%。
    """
    max_size = int(max_mb * 1024 * 1024)
    original_size = len(image_bytes)

    if original_size <= max_size:
        return image_bytes, {"compressed": False}

    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    # 阶段一：仅降质量（保持原始分辨率）
    for quality in (85, 75, 65, 55, 45, 35, 30):
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_size:
            return buf.getvalue(), {
                "compressed": True,
                "original_size_bytes": original_size,
                "quality": quality,
            }

    # 阶段二：缩放 + 降质量
    long_edge = max(img.width, img.height)
    for scale in (0.8, 0.6, 0.5, 0.4, 0.3):
        new_long = int(long_edge * scale)
        if new_long < 1024:
            new_long = 1024
        ratio = new_long / long_edge
        if ratio >= 0.95:
            continue
        new_size = (int(img.width * ratio), int(img.height * ratio))
        resized = img.resize(new_size, Image.LANCZOS)
        for quality in (60, 45, 30):
            buf = BytesIO()
            resized.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= max_size:
                return buf.getvalue(), {
                    "compressed": True,
                    "original_size_bytes": original_size,
                    "quality": quality,
                    "resized_to": list(new_size),
                }

    # 阶段三：兜底 — 1024px 长边 + 质量 30
    if long_edge > 1024:
        ratio = 1024 / long_edge
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=30, optimize=True)
    return buf.getvalue(), {
        "compressed": True,
        "original_size_bytes": original_size,
        "quality": 30,
        "resized_to": [img.width, img.height],
    }


def parse_scores_from_report(report: str) -> list[dict]:
    """从 Markdown 报告中解析得分总览表格，提取得分卡数据。"""
    scores = []
    dimension_names = [
        "构图", "曝光", "色彩", "对焦", "锐度",
        "白平衡", "面部表情", "眼神", "肢体语言", "整体印象",
    ]

    # 先用主表格模式批量匹配数值分数行
    # 使用 [ \t] 而非 \s，防止跨行匹配
    table_pattern = r"\|[ \t]*(.+?)[ \t]*\|[ \t]*(\d+)[ \t]*分?[ \t]*\|[ \t]*(.+?)[ \t]*\|"
    table_matches = re.findall(table_pattern, report)

    found_names = set()
    for match in table_matches:
        dim_name = match[0].strip()
        try:
            score = int(match[1].strip())
        except ValueError:
            score = 0
        comment = match[2].strip()
        scores.append({
            "name": dim_name,
            "score": score,
            "comment": comment,
        })
        found_names.add(dim_name)

    # 对未匹配到的维度，逐行兜底（含 N/A 分值处理）
    for dim_name in dimension_names:
        if dim_name in found_names:
            continue
        # 先尝试匹配数值分数
        num_pattern = rf"{dim_name}[ \t]*\|[ \t]*(\d+)[ \t]*分?[ \t]*\|[ \t]*(.+?)(?:\||$)"
        m = re.search(num_pattern, report)
        if m:
            scores.append({
                "name": dim_name,
                "score": int(m.group(1).strip()),
                "comment": m.group(2).strip(),
            })
            continue
        # 再尝试匹配 N/A 分值
        na_pattern = rf"{dim_name}[ \t]*\|[ \t]*N/?A[ \t]*\|[ \t]*(.+?)(?:\||$)"
        m = re.search(na_pattern, report, re.IGNORECASE)
        if m:
            scores.append({
                "name": dim_name,
                "score": 0,
                "comment": m.group(1).strip(),
            })
            continue
        # 完全无法解析
        scores.append({
            "name": dim_name,
            "score": 0,
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
        image: 照片文件（必填，超大图片会自动压缩，支持 JPEG/PNG/WebP/HEIC）
        provider: LLM 提供商（"openai" 或 "anthropic"，可选，默认读取 .env）
        model: 模型名称（可选，默认读取 .env）
        api_key: API 密钥（可选，默认读取 .env）
        base_url: 自定义 API 地址（可选，默认读取 .env）

    返回：
        {
            "success": true,
            "report": "Markdown 格式的完整诊断报告",
            "scores": [{name, score, comment}, ...],
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

    # 读取图片字节并校验大小，超限自动压缩
    image_bytes = await image.read()
    image_size_mb = len(image_bytes) / (1024 * 1024)
    original_size_mb = image_size_mb
    compress_info = {"compressed": False}

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        image_bytes, compress_info = compress_image(image_bytes, MAX_IMAGE_SIZE_MB)
        mime_type = "image/jpeg"
        image_size_mb = len(image_bytes) / (1024 * 1024)

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
            "compressed": compress_info["compressed"],
            "original_size_mb": round(original_size_mb, 2),
        },
    }


@app.get("/api/health")
async def health_check():
    """健康检查接口。"""
    return {"status": "ok", "service": "Photo Coach API", "version": "1.0.0"}


# 生产环境：serve 前端 SPA（API 路由未匹配时 fallback 到静态文件）
if os.getenv("ENVIRONMENT") == "production":
    static_dir = Path(__file__).parent.parent / "frontend" / "dist"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
