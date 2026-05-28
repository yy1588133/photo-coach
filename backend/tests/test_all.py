"""
Tests: rate limiter, EXIF parser, challenges, report parsers, API endpoints.
"""
import io
import json
import os
import sys
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend dir is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock env before importing app
os.environ["DEFAULT_API_KEY"] = "test-key-12345"
os.environ["DEFAULT_PROVIDER"] = "openai"
os.environ["DEFAULT_MODEL"] = "gpt-4o"

from main import app
from rate_limiter import RateLimiter
from exif_analyzer import parse_exif, analyze_params
from challenges import get_daily_challenge, get_challenge_by_id, CHALLENGES
from main import parse_scores_from_report, parse_annotations

client = TestClient(app)


# ============================================================================
# Rate Limiter
# ============================================================================

class TestRateLimiter:
    def test_allows_within_limit(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert rl.is_allowed("client-1") is True

    def test_blocks_over_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert rl.is_allowed("client-2") is True
        assert rl.is_allowed("client-2") is False

    def test_remaining_count(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        rl.is_allowed("client-3")
        rl.is_allowed("client-3")
        assert rl.remaining("client-3") == 3

    def test_isolated_per_key(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        # Exhaust client-A
        rl.is_allowed("A")
        rl.is_allowed("A")
        assert rl.is_allowed("A") is False
        # Client-B still has quota
        assert rl.is_allowed("B") is True
        assert rl.is_allowed("B") is True
        assert rl.is_allowed("B") is False


# ============================================================================
# EXIF Analyzer
# ============================================================================

class TestExifAnalyzer:
    def test_no_exif_jpeg(self):
        """JPEG with no EXIF returns empty dict."""
        # Minimal 1x1 JPEG (no EXIF)
        from PIL import Image
        buf = io.BytesIO()
        img = Image.new("RGB", (1, 1), color="red")
        img.save(buf, format="JPEG")
        result = parse_exif(buf.getvalue())
        assert result == {}

    def test_analyze_params_empty(self):
        result = analyze_params([])
        assert result == "无照片数据"

    def test_analyze_params_with_data(self):
        photos = [
            {"filename": "test.jpg", "exif": {"aperture": "f/2.8", "iso": 400, "focal_length": "50mm"}}
        ]
        result = analyze_params(photos)
        assert "test.jpg" in result
        assert "f/2.8" in result
        assert "ISO: 400" in result

    def test_analyze_params_no_exif(self):
        photos = [{"filename": "noexif.jpg", "exif": {}}]
        result = analyze_params(photos)
        assert "无 EXIF 数据" in result


# ============================================================================
# Challenges
# ============================================================================

class TestChallenges:
    def test_has_15_challenges(self):
        assert len(CHALLENGES) == 15

    def test_daily_deterministic(self):
        c1 = get_daily_challenge()
        c2 = get_daily_challenge()
        assert c1["id"] == c2["id"]

    def test_all_challenges_have_required_fields(self):
        for c in CHALLENGES:
            assert "id" in c
            assert "title" in c
            assert "description" in c
            assert "criteria" in c
            assert "difficulty" in c
            assert 1 <= c["difficulty"] <= 3

    def test_get_by_id_found(self):
        c = get_challenge_by_id("rule-of-thirds")
        assert c is not None
        assert c["title"] == "三分法构图"

    def test_get_by_id_not_found(self):
        assert get_challenge_by_id("nonexistent") is None


# ============================================================================
# Report Parsers
# ============================================================================

SAMPLE_REPORT = """### 得分总览

| 维度 | 评分 | 简评 |
|------|------|------|
| 构图 | 85分 | 主体鲜明 |
| 曝光 | 72分 | 略暗 |
| 色彩 | 80分 | 和谐 |
| 对焦 | 90分 | 锐利清晰 |
| 锐度 | 88分 | 细节好 |
| 白平衡 | 75分 | 轻微偏暖 |
| 面部表情 | 60分 | 略僵硬 |
| 眼神 | 65分 | 可更锐利 |
| 肢体语言 | 70分 | 自然 |
| 整体印象 | 78分 | 不错 |

### 核心改进方向

> 🎯 提升曝光准确度是当前最关键改进方向

## 标注区域

| 类型 | 标签 | 位置描述 | 问题与建议 |
|------|------|----------|------------|
| overexposed | 天空过曝 | 画面顶部1/3 | 降1档曝光 |
| underexposed | 前景暗部 | 画面左下角 | 补光 |
"""


class TestParseScores:
    def test_parses_10_dimensions(self):
        scores = parse_scores_from_report(SAMPLE_REPORT)
        assert len(scores) == 10

    def test_score_values(self):
        scores = parse_scores_from_report(SAMPLE_REPORT)
        by_name = {s["name"]: s["score"] for s in scores}
        assert by_name["构图"] == 85
        assert by_name["曝光"] == 72
        assert by_name["整体印象"] == 78

    def test_empty_report(self):
        scores = parse_scores_from_report("")
        assert len(scores) == 10
        for s in scores:
            assert s["score"] == 0

    def test_na_dimension(self):
        """N/A dimensions get score 0."""
        report = """### 得分总览
| 维度 | 评分 | 简评 |
|------|------|------|
| 构图 | 85分 | ok |
| 曝光 | 72分 | ok |
| 色彩 | 80分 | ok |
| 对焦 | 90分 | ok |
| 锐度 | 88分 | ok |
| 白平衡 | 75分 | ok |
| 面部表情 | N/A | 非人像 |
| 眼神 | N/A | 非人像 |
| 肢体语言 | N/A | 非人像 |
| 整体印象 | 78分 | ok |
"""
        scores = parse_scores_from_report(report)
        face = [s for s in scores if s["name"] == "面部表情"][0]
        assert face["score"] == 0
        assert "非人像" in face["comment"]


class TestParseAnnotations:
    def test_parses_annotations(self):
        annos = parse_annotations(SAMPLE_REPORT)
        assert len(annos) == 2
        assert annos[0]["type"] == "overexposed"
        assert annos[0]["label"] == "天空过曝"
        assert annos[1]["type"] == "underexposed"
        assert annos[1]["position"] == "画面左下角"

    def test_no_annotations_section(self):
        annos = parse_annotations("### 得分总览\n\n无标注区域")
        assert annos == []


# ============================================================================
# API Endpoints
# ============================================================================

class TestHealthAPI:
    def test_health(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "Photo Coach API"

    def test_readiness(self):
        resp = client.get("/api/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    def test_health_has_request_id(self):
        resp = client.get("/api/health")
        assert "X-Request-ID" in resp.headers


class TestChallengeAPI:
    def test_get_today(self):
        resp = client.get("/api/challenge/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "challenge" in data
        assert "id" in data["challenge"]

    def test_judge_missing_challenge(self):
        """Missing challenge_id returns 422 (FastAPI validation)."""
        # No file, no challenge_id — validation error
        resp = client.post("/api/challenge/judge")
        assert resp.status_code == 422


class TestExtractExifAPI:
    def test_no_file_returns_422(self):
        resp = client.post("/api/extract-exif")
        assert resp.status_code == 422


class TestRateLimitAPI:
    def test_health_not_rate_limited(self):
        """Health endpoint should still work under rate limit."""
        for _ in range(10):
            resp = client.get("/api/health")
            assert resp.status_code == 200
