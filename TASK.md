# Photo Coach — Phase 1 开发任务

## 项目概述
AI 摄影教练 Web App (PWA)。用户上传照片后，AI 自动进行 10 维度摄影诊断，返回结构化诊断报告。

## 后端 (Python FastAPI)

### 核心文件
- `backend/main.py`：FastAPI 入口，POST /api/analyze 接口
- `backend/adapters/openai_adapter.py`：OpenAI 兼容适配器（纯 httpx，不依赖官方 SDK）
- `backend/adapters/anthropic_adapter.py`：Anthropic 兼容适配器（纯 httpx，不依赖官方 SDK）
- `backend/prompts/diagnosis.py`：SYSTEM_PROMPT + USER_MESSAGE_TEMPLATE（10 维度诊断）
- `backend/.env.example`：内置引擎配置模板
- `backend/requirements.txt`

### API 设计
```
POST /api/analyze
  Form Data:
    image: file (必填)
    provider: "openai" | "anthropic" (可选，默认用 .env)
    model: str (可选)
    api_key: str (可选)
    base_url: str (可选)

  Response:
    {
      "success": true,
      "report": "完整的 Markdown 诊断报告",
      "scores": [{name, score, comment}, ...],
      "meta": {provider, model, image_size_mb, mime_type}
    }
```

### 适配器规范
- OpenAI 适配器：POST {base_url}/chat/completions，Bearer auth，格式 image_url base64
- Anthropic 适配器：POST {base_url}/v1/messages，x-api-key auth，格式 source base64
- 都不依赖官方 SDK，只用 httpx
- 支持任意自定义 base_url（中转站、代理等）

### 内置引擎配置 (.env.example)
```
DEFAULT_PROVIDER=anthropic
DEFAULT_MODEL=claude-sonnet-4-20250514
DEFAULT_API_KEY=your-api-key-here
DEFAULT_BASE_URL=
```

### 其他
- 图片限制 15MB，支持 JPEG/PNG/WebP/HEIC
- CORS 全开（MVP 阶段）
- 从报告 Markdown 解析得分卡表格

## 前端 (Vite + React)

### 技术栈
- Vite + React（不用 Next.js，PWA 用 vite-plugin-pwa）
- 纯 CSS 实现暗色摄影主题（不用 UI 库）
- 移动端优先

### 设计系统
- 底色：#0d0d0d（深黑）
- 卡片底色：#1a1a1a
- 主文字：#f5f0eb（暖白）
- 次要文字：#8a8580
- 强调色：#e8943a（琥珀/暖橙）
- 字体：system-ui, -apple-system, sans-serif
- 圆角：12px（卡片），8px（按钮）
- 最小触控区域：48px

### 页面 1：上传页（首页 `/`）
- 全屏居中布局
- 大尺寸上传区域（虚线边框暗示），支持点击选图 + 拖拽 + 粘贴
- camera input 支持手机拍照
- 底部简洁设置入口（齿轮图标）
- 上传后自动跳转报告页（路由传参或 localStorage）

### 页面 2：诊断报告页（`/report`）
- 得分卡：横向滑动卡片，9 项评分（1-5⭐），每项含名称+评分+一句话
- 核心改进方向：琥珀色高亮卡片，一句话总结
- 10 个诊断维度：折叠面板（accordion），默认全部折叠，点击展开
- 底部：固定按钮"分析下一张"

### 过渡态（分析中）
- 显示照片缩略图
- 优雅加载动画（模拟显影过程）
- 显示"正在分析构图、曝光、色彩..."

### 设置组件
- 提供商选择：OpenAI 兼容 / Anthropic 兼容
- 输入框：API Key、Base URL、Model 名称
- 存储到 localStorage，分析时携带

### PWA 支持
- manifest.json（应用名：Photo Coach，图标预留）
- service worker（基础离线缓存）

## 项目结构
```
photo-coach/
├── backend/
│   ├── main.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── openai_adapter.py
│   │   └── anthropic_adapter.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── diagnosis.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── main.jsx
│   │   ├── pages/
│   │   │   ├── UploadPage.jsx
│   │   │   └── ReportPage.jsx
│   │   ├── components/
│   │   │   ├── ScoreCard.jsx
│   │   │   ├── ReportSection.jsx
│   │   │   └── SettingsModal.jsx
│   │   └── hooks/
│   │       └── useSettings.js
│   ├── public/
│   │   └── manifest.json
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── README.md
```

## 关键约束
- 前端通过 fetch 调用后端 /api/analyze，base_url 用 Vite proxy 或直接配置
- 照片以 FormData 上传（multipart/form-data），包含 image 文件 + 可选引擎参数
- 前端报告页直接渲染 AI 返回的 Markdown 报告（可用简单的 markdown 渲染库如 marked 或手写解析）
- 后端需处理 API 调用错误，返回友好的错误信息
- README.md 说明如何配置 .env 和启动前后端

## 完成后需验证
- 后端能正常启动（uvicorn main:app）
- POST /api/analyze 接口可访问
- 前端能正常构建（npm run build）
- 上传页和报告页路由正常
