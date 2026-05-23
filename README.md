# Photo Coach — AI 摄影教练

上传照片，AI 自动进行 10 维度摄影诊断（构图、曝光、色彩、对焦、面部表情、眼神、肢体语言等），即时生成结构化诊断报告。

## 项目结构

```
photo-coach/
├── backend/          # FastAPI 后端
│   ├── main.py       # API 入口
│   ├── adapters/     # AI 引擎适配器（OpenAI / Anthropic）
│   ├── prompts/      # 诊断 Prompt 模板
│   ├── .env.example  # 内置引擎配置模板
│   └── requirements.txt
├── frontend/         # Vite + React PWA 前端
│   ├── src/
│   │   ├── pages/        # 上传页 / 报告页
│   │   ├── components/   # 得分卡 / 诊断区 / 设置
│   │   └── hooks/        # 设置持久化
│   └── public/           # manifest / favicon
└── README.md
```

## 快速启动

### 1. 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置内置引擎（复制 .env.example 为 .env 并填写 API Key）
cp .env.example .env
# 编辑 .env，填写 DEFAULT_API_KEY

# 启动
uvicorn main:app --reload --port 8000
```

API 接口：`POST http://localhost:8000/api/analyze`

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 开发模式启动
npm run dev
```

默认启动在 `http://localhost:5173`，API 请求自动代理到 `http://localhost:8000`。

### 3. 生产构建

```bash
cd frontend
npm run build   # 输出到 dist/
```

## 引擎配置

### 内置引擎（.env）

用户不提供 API Key 时使用：

```env
DEFAULT_PROVIDER=anthropic          # 或 openai
DEFAULT_MODEL=claude-sonnet-4-20250514
DEFAULT_API_KEY=sk-xxx              # 你的 API Key
DEFAULT_BASE_URL=                   # 留空 = 官方默认
```

### 自定义引擎

用户在前端设置中填写自己的 API Key / Base URL / Model，支持任意 OpenAI 或 Anthropic 兼容接口（包括中转站、代理、本地模型）。

## 技术栈

| 层 | 方案 |
|---|------|
| 前端 | Vite + React + react-router-dom |
| PWA | vite-plugin-pwa |
| 后端 | FastAPI + httpx |
| AI 适配 | 纯 HTTP 调用，不依赖官方 SDK |
| 设计 | 暗色主题，纯 CSS 变量 |

## 支持的 AI 提供商

- **OpenAI 兼容**：OpenAI 官方、Ollama、vLLM、任意 OpenAI 格式中转站
- **Anthropic 兼容**：Anthropic 官方、prismapi.site、任意 Anthropic 格式中转站

API Key 和 Base URL 均可自定义，无锁定。
