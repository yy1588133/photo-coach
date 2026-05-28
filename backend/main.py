"""
Photo Coach — FastAPI backend (production-hardened).

Features:
- POST /api/analyze       — photo diagnosis (10-dimension)
- GET  /api/challenge/today
- POST /api/challenge/judge
- POST /api/params/analyze — multi-photo EXIF analysis
- POST /api/extract-exif
- GET  /api/health         — liveness + readiness
- Rate limiting (per-IP, 60 req/min)
- Request-ID tracing + structured logging
- AI adapter: timeout + retry
- Graceful shutdown
"""
import asyncio
import json
import logging
import os
import re
import signal
import time
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

# ---------------------------------------------------------------------------
# Early init
# ---------------------------------------------------------------------------
from logging_config import setup_logging, set_request_id, get_request_id

setup_logging()
logger = logging.getLogger(__name__)

# Load .env
env_paths = [
    Path(__file__).parent / ".env",
    Path(__file__).parent / ".env.example",
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, encoding="utf-8")
        break

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(title="Photo Coach API", version="1.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limit middleware
from rate_limiter import rate_limit_middleware

app.middleware("http")(rate_limit_middleware)

# Request-ID middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or set_request_id()
    set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = get_request_id()
    return response

# ---------------------------------------------------------------------------
# Imports (after app init so logging works)
# ---------------------------------------------------------------------------
from adapters.openai_adapter import call_openai_vision
from adapters.anthropic_adapter import call_anthropic_vision
from prompts.diagnosis import SYSTEM_PROMPT, USER_MESSAGE_TEMPLATE
from prompts.challenge_judge import (
    SYSTEM_PROMPT_CHALLENGE,
    USER_MESSAGE_TEMPLATE_CHALLENGE,
)
from exif_analyzer import parse_exif as parse_exif_data, analyze_params
from challenges import get_daily_challenge, get_challenge_by_id

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_IMAGE_SIZE_MB = float(os.getenv("MAX_IMAGE_SIZE_MB", "15"))
MAX_IMAGE_SIZE_BYTES = int(MAX_IMAGE_SIZE_MB * 1024 * 1024)
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
AI_TIMEOUT = float(os.getenv("AI_TIMEOUT_SECONDS", "120"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "2"))


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_shutting_down = False


def _install_signal_handlers():
    """Handle SIGTERM / SIGINT for graceful shutdown."""

    def _handler(sig, _frame):
        global _shutting_down
        if not _shutting_down:
            _shutting_down = True
            logger.info("Received signal %s, starting graceful shutdown...", sig)

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _install_signal_handlers()
    yield
    global _shutting_down
    _shutting_down = True
    logger.info("Lifespan shutdown — draining in-flight requests...")

app.router.lifespan_context = lifespan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve_engine(provider, model, api_key, base_url):
    """Resolve engine config: request params > env vars > defaults."""
    return (
        provider or os.getenv("DEFAULT_PROVIDER", "anthropic"),
        model or os.getenv("DEFAULT_MODEL", "claude-sonnet-4-20250514"),
        api_key or os.getenv("DEFAULT_API_KEY", ""),
        base_url or os.getenv("DEFAULT_BASE_URL", "") or None,
    )


def _validate_engine(provider, api_key):
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 API Key")
    if provider not in ("openai", "anthropic"):
        raise HTTPException(status_code=400, detail=f"不支持的 provider: {provider}。支持: openai, anthropic")


async def _call_ai(provider, image_bytes, mime_type, system_prompt, user_message,
                   model, api_key, base_url):
    """Route AI call to correct adapter with timeout + retries."""
    try:
        if provider == "openai":
            return await call_openai_vision(
                image_bytes=image_bytes,
                mime_type=mime_type,
                system_prompt=system_prompt,
                user_message=user_message,
                model=model,
                api_key=api_key,
                base_url=base_url,
                timeout=AI_TIMEOUT,
                max_retries=AI_MAX_RETRIES,
            )
        else:
            return await call_anthropic_vision(
                image_bytes=image_bytes,
                mime_type=mime_type,
                system_prompt=system_prompt,
                user_message=user_message,
                model=model,
                api_key=api_key,
                base_url=base_url,
                timeout=AI_TIMEOUT,
                max_retries=AI_MAX_RETRIES,
            )
    except Exception as e:
        logger.error("AI call failed: provider=%s model=%s error=%s", provider, model, str(e))
        raise HTTPException(status_code=502, detail=f"AI API 调用失败: {str(e)}")


async def _read_and_validate_image(image: UploadFile) -> tuple[bytes, str, float, dict, float, Image.Image]:
    """Read image bytes, validate, compress if needed. Returns (bytes, mime_type, size_mb, compress_info, original_size_mb, pil_image)."""
    mime_type = image.content_type or "image/jpeg"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {mime_type}。支持: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    image_bytes = await image.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    original_size_mb = len(image_bytes) / (1024 * 1024)

    # Open once so EXIF parsing can reuse this object
    pil_image = Image.open(BytesIO(image_bytes))

    compress_info = {"compressed": False}
    image_size_mb = original_size_mb

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        image_bytes, compress_info = compress_image(image_bytes, MAX_IMAGE_SIZE_MB)
        mime_type = "image/jpeg"
        image_size_mb = len(image_bytes) / (1024 * 1024)
        logger.info(
            "Image compressed: %.1fMB -> %.1fMB (quality=%s, resized=%s)",
            original_size_mb,
            image_size_mb,
            compress_info.get("quality"),
            compress_info.get("resized_to"),
        )

    return image_bytes, mime_type, image_size_mb, compress_info, original_size_mb, pil_image


def compress_image(image_bytes: bytes, max_mb: float = 15) -> tuple[bytes, dict]:
    """Compress image to target size. Returns (bytes, info)."""
    max_size = int(max_mb * 1024 * 1024)
    original_size = len(image_bytes)

    if original_size <= max_size:
        return image_bytes, {"compressed": False}

    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    # Phase 1: reduce quality only
    for quality in (85, 75, 65, 55, 45, 35, 30):
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_size:
            return buf.getvalue(), {
                "compressed": True,
                "original_size_bytes": original_size,
                "quality": quality,
            }

    # Phase 2: scale down + reduce quality
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

    # Phase 3: fallback — 1024px long edge, quality 30
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
    """Parse score overview table from Markdown report."""
    scores = []
    dimension_names = [
        "构图", "曝光", "色彩", "对焦", "锐度",
        "白平衡", "面部表情", "眼神", "肢体语言", "整体印象",
    ]

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
        scores.append({"name": dim_name, "score": score, "comment": comment})
        found_names.add(dim_name)

    for dim_name in dimension_names:
        if dim_name in found_names:
            continue
        num_pattern = rf"{dim_name}[ \t]*\|[ \t]*(\d+)[ \t]*分?[ \t]*\|[ \t]*(.+?)(?:\||$)"
        m = re.search(num_pattern, report)
        if m:
            scores.append({"name": dim_name, "score": int(m.group(1).strip()), "comment": m.group(2).strip()})
            continue
        na_pattern = rf"{dim_name}[ \t]*\|[ \t]*N/?A[ \t]*\|[ \t]*(.+?)(?:\||$)"
        m = re.search(na_pattern, report, re.IGNORECASE)
        if m:
            scores.append({"name": dim_name, "score": 0, "comment": m.group(1).strip()})
            continue
        scores.append({"name": dim_name, "score": 0, "comment": "无法解析"})

    return scores


def parse_annotations(report: str) -> list[dict]:
    """Parse annotation region data from report."""
    annotations = []
    section_match = re.search(r"##\s*标注区域\s*\n(.+)", report, re.DOTALL)
    if not section_match:
        return annotations

    section = section_match.group(1)
    rows = re.findall(
        r"\|\s*(\w+)\s*\|"
        r"\s*(.+?)\s*\|"
        r"\s*(.+?)\s*\|"
        r"\s*(.+?)\s*\|",
        section,
    )
    for row in rows:
        annotations.append({
            "type": row[0].strip(),
            "label": row[1].strip(),
            "position": row[2].strip(),
            "description": row[3].strip(),
        })
    return annotations


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/analyze")
async def analyze_photo(
    image: UploadFile = File(...),
    provider: str | None = Form(None),
    model: str | None = Form(None),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
):
    """Analyze uploaded photo — returns AI diagnosis report with scores, annotations, EXIF."""
    logger.info("POST /api/analyze filename=%s content_type=%s", image.filename, image.content_type)

    image_bytes, mime_type, image_size_mb, compress_info, original_size_mb, pil_image = await _read_and_validate_image(image)

    engine_provider, engine_model, engine_api_key, engine_base_url = _resolve_engine(
        provider, model, api_key, base_url
    )
    _validate_engine(engine_provider, engine_api_key)

    report = await _call_ai(
        engine_provider, image_bytes, mime_type,
        SYSTEM_PROMPT, USER_MESSAGE_TEMPLATE,
        engine_model, engine_api_key, engine_base_url,
    )

    scores = parse_scores_from_report(report)
    annotations = parse_annotations(report)
    exif = parse_exif_data(image_bytes, pil_image=pil_image)

    logger.info(
        "POST /api/analyze OK provider=%s model=%s scores=%d annotations=%d exif_keys=%d",
        engine_provider, engine_model, len(scores), len(annotations), len(exif),
    )

    return {
        "success": True,
        "report": report,
        "scores": scores,
        "annotations": annotations,
        "exif": exif,
        "meta": {
            "provider": engine_provider,
            "model": engine_model,
            "image_size_mb": round(image_size_mb, 2),
            "mime_type": mime_type,
            "compressed": compress_info["compressed"],
            "original_size_mb": round(original_size_mb, 2),
        },
    }


@app.get("/api/challenge/today")
async def challenge_today():
    """Return today's challenge (deterministic rotation)."""
    challenge = get_daily_challenge()
    logger.info("GET /api/challenge/today id=%s", challenge["id"])
    return {"success": True, "challenge": challenge}


@app.post("/api/challenge/judge")
async def challenge_judge(
    image: UploadFile = File(...),
    challenge_id: str = Form(...),
    provider: str | None = Form(None),
    model: str | None = Form(None),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
):
    """Judge a challenge submission photo."""
    logger.info("POST /api/challenge/judge challenge_id=%s filename=%s", challenge_id, image.filename)

    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail=f"挑战不存在: {challenge_id}")

    image_bytes, mime_type, image_size_mb, _, _, _ = await _read_and_validate_image(image)

    engine_provider, engine_model, engine_api_key, engine_base_url = _resolve_engine(
        provider, model, api_key, base_url
    )
    _validate_engine(engine_provider, engine_api_key)

    user_message = USER_MESSAGE_TEMPLATE_CHALLENGE.format(
        title=challenge["title"],
        description=challenge["description"],
        criteria=challenge["criteria"],
    )

    result_text = await _call_ai(
        engine_provider, image_bytes, mime_type,
        SYSTEM_PROMPT_CHALLENGE, user_message,
        engine_model, engine_api_key, engine_base_url,
    )

    try:
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = re.sub(r"^```\w*\n?", "", result_text)
            result_text = re.sub(r"\n?```$", "", result_text)
        result = json.loads(result_text)
    except json.JSONDecodeError:
        logger.warning("Challenge judge response not valid JSON: %.200s", result_text)
        result = {
            "passed": False,
            "comment": "AI 返回格式异常，请重试",
            "highlights": [],
            "suggestions": [],
        }

    logger.info("POST /api/challenge/judge OK passed=%s", result.get("passed"))
    return {"success": True, "challenge_id": challenge_id, "judgment": result}


@app.post("/api/params/analyze")
async def params_analyze(
    photos_data: str = Form(...),
    provider: str | None = Form(None),
    model: str | None = Form(None),
    api_key: str | None = Form(None),
    base_url: str | None = Form(None),
):
    """Analyze EXIF parameter patterns across multiple photos."""
    logger.info("POST /api/params/analyze")

    try:
        photos = json.loads(photos_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="photos_data 不是有效的 JSON")

    if not photos or len(photos) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 张照片的参数数据")

    summary = analyze_params(photos)

    system_prompt = """你是一位摄影数据分析师。根据用户提供的多张照片 EXIF 参数数据，分析参数规律并给出建议。

输出格式要求：
1. 找出用户最常使用的参数组合
2. 分析不同场景/时段下的参数变化规律
3. 给出具体的参数调整建议
用中文回复，简洁专业，不超过 500 字。"""

    user_message = f"""以下是我多张照片的 EXIF 参数数据：

{summary}

请分析我的拍摄参数规律，并给出改进建议。"""

    engine_provider, engine_model, engine_api_key, engine_base_url = _resolve_engine(
        provider, model, api_key, base_url
    )
    _validate_engine(engine_provider, engine_api_key)

    # Text-only call (no image)
    analysis = await _call_ai(
        engine_provider, None, None,
        system_prompt, user_message,
        engine_model, engine_api_key, engine_base_url,
    )

    logger.info("POST /api/params/analyze OK photos=%d", len(photos))
    return {"success": True, "photos_count": len(photos), "analysis": analysis}


@app.post("/api/extract-exif")
async def extract_exif(image: UploadFile = File(...)):
    """Extract EXIF data from single photo, no AI call."""
    logger.info("POST /api/extract-exif filename=%s", image.filename)

    mime_type = image.content_type or "image/jpeg"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {mime_type}")

    image_bytes = await image.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    exif = parse_exif_data(image_bytes)
    logger.info("POST /api/extract-exif OK exif_keys=%d", len(exif))
    return {"success": True, "exif": exif}


@app.get("/api/health")
async def health_check():
    """Health check — liveness + optional readiness probe."""
    status = {
        "status": "ok",
        "service": "Photo Coach API",
        "version": "1.1.0",
    }
    if _shutting_down:
        status["status"] = "shutting_down"
    return status


@app.get("/api/health/ready")
async def readiness_check():
    """Readiness probe — returns 503 if shutting down."""
    if _shutting_down:
        raise HTTPException(status_code=503, detail="服务正在关闭")
    return {"status": "ready", "service": "Photo Coach API", "version": "1.1.0"}


# ---------------------------------------------------------------------------
# Production: serve frontend SPA
# ---------------------------------------------------------------------------
if os.getenv("ENVIRONMENT") == "production":
    static_dir = Path(__file__).parent.parent / "frontend" / "dist"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
