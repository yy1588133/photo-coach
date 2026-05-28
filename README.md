# Photo Coach — AI 摄影教练

上传照片，AI 自动进行 10 维度摄影诊断，即时生成结构化诊断报告。支持可视化标注叠加、每日摄影挑战和 EXIF 参数实验室。

## 功能

| 模块 | 说明 |
|------|------|
| **AI 诊断** | 上传照片 → 10维度 0-100 分诊断（构图/曝光/色彩/对焦/锐度/白平衡/面部表情/眼神/肢体语言/整体印象） |
| **可视化诊断** | AI 标注问题区域（过曝/欠曝/模糊/构图），Canvas 半透明叠加 + 九宫格辅助线 |
| **每日挑战** | 15 个预置摄影挑战任务，按日期轮换，AI 评判达标/未达标 |
| **参数实验室** | 上传多张照片 → EXIF 提取 → AI 分析光圈/快门/ISO/焦距使用规律 |
| **引擎切换** | 支持 OpenAI / Anthropic 兼容 API，前端可配置自定义 proxy |

## 项目结构

```
photo-coach/
├── backend/
│   ├── main.py              # FastAPI 入口（限流/日志/优雅关闭）
│   ├── rate_limiter.py      # 滑动窗口限流器（60次/分钟/IP）
│   ├── logging_config.py    # 结构化日志 + 请求ID追踪
│   ├── exif_analyzer.py     # EXIF 解析（Pillow）
│   ├── challenges.py        # 15个预置挑战任务库
│   ├── adapters/            # AI 适配器（超时/重试/退避）
│   ├── prompts/             # 诊断 & 挑战评判 Prompt
│   ├── tests/               # pytest 测试套件（26用例）
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── pages/           # UploadPage / ReportPage / DailyChallenge / ParamsLab
│       ├── components/      # ScoreCard / ReportSection / AnnotationOverlay / SettingsModal
│       ├── hooks/           # useSettings
│       └── App.jsx          # 路由: / /report /challenge /params
├── render.yaml              # Render Blueprint 部署配置
└── README.md
```

## 快速启动

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填写 DEFAULT_API_KEY
uvicorn main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

### 3. 运行测试

```bash
cd backend
pytest tests/test_all.py -v
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze` | 照片诊断（返回 report/scores/annotations/exif） |
| GET | `/api/challenge/today` | 今日挑战 |
| POST | `/api/challenge/judge` | 挑战评判 |
| POST | `/api/params/analyze` | 多图 EXIF 参数分析 |
| POST | `/api/extract-exif` | 单图 EXIF 提取 |
| GET | `/api/health` | 存活检查 |
| GET | `/api/health/ready` | 就绪检查（关闭中返回 503） |

## 生产特性

- **限流**: 滑动窗口，60 次/分钟/IP，超限返回 429 + Retry-After
- **日志**: 结构化 `key=value` 格式，每请求独立 request-id
- **超时重试**: AI API 调用 120s 超时，5xx/429 自动退避重试（最多 2 次）
- **优雅关闭**: SIGTERM 信号处理，`/api/health/ready` 返回 503 通知负载均衡摘流
- **请求追踪**: X-Request-ID 头贯穿所有请求
- **图片压缩**: 超大上传自动压缩（降质量 → 缩尺寸 → 1024px 兜底）
- **PWA**: Service Worker + Web Manifest，支持离线访问

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEFAULT_PROVIDER` | AI 提供商 (openai/anthropic) | anthropic |
| `DEFAULT_MODEL` | 模型名称 | claude-sonnet-4-20250514 |
| `DEFAULT_API_KEY` | API 密钥 | (必填) |
| `DEFAULT_BASE_URL` | 自定义 API 地址 | (空=官方) |
| `ENVIRONMENT` | 设为 `production` 时 serve 前端 | (空) |
| `MAX_IMAGE_SIZE_MB` | 最大上传体积 | 15 |
| `AI_TIMEOUT_SECONDS` | AI 调用超时 | 120 |
| `AI_MAX_RETRIES` | AI 调用最大重试 | 2 |

## 部署

Render Blueprint 一键部署：`render.yaml` 已配置单体 Web Service（serve 前后端），需在 Render Dashboard 手动设置 `DEFAULT_API_KEY` secret。
