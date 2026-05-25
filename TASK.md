# Photo Coach Phase 2 — 可视化诊断 + 每日挑战 + 参数实验室

## 1. AI 摄影教练：可视化诊断（核心升级）

### 目标
不只给分数，给可视化的修改方案。AI 在诊断报告中标注问题区域，前端在照片上叠加标注。

### 后端改动
- **prompts/diagnosis.py**：新增输出格式要求。10个维度诊断后，追加一个 `## 标注区域` section，每个标注包含：
  - `type`: crop / overexposed / underexposed / blur / composition
  - `label`: 简短中文说明
  - `description`: 具体问题和改进建议
- **main.py**：新增 `parse_annotations()` 函数，从报告中提取标注数据返回给前端。格式：`[{type, label, description, position}]`

### 前端改动
- **新增 AnnotationOverlay 组件**：在报告页显示上传的照片，叠加半透明标注层（Canvas/SVG）
  - 裁剪参考线（九宫格线 + 推荐的裁剪框）
  - 高光溢出区域（红色半透明蒙版）
  - 欠曝区域（蓝色半透明蒙版）
  - 模糊/对焦问题区域（虚线框标注）
- **ReportPage**：报告页新增"可视化诊断"tab/区域，展示带标注的图片
- 标注位置策略：AI 描述区域类型（如"左侧面部高光过曝"），前端根据通用人体比例推算大致位置并画标记（不需要 AI 返回像素坐标，太不可靠）

---

## 2. 每日摄影挑战

### 目标
每天推送一个具体拍摄任务，用户上传完成 → AI 评判是否达标。

### 后端改动
- **新增 backend/challenges.py**：每日挑战任务库
  - 预置 15-30 个挑战任务（覆盖构图、光线、色彩、人像等方向）
  - 每个任务：id, 标题, 详细说明, 评分标准, 难度(1-3)
  - `get_daily_challenge()`: 根据日期返回当天挑战（轮换）
  - `get_challenge_by_id()`: 按ID获取挑战详情
- **新增 POST /api/challenge/judge**：接收照片 + challenge_id → AI 评判是否达标 + 改进建议
  - 新增 `prompts/challenge_judge.py`：评判 prompt 模板
- **GET /api/challenge/today**：返回今日挑战（无需认证）

### 前端改动
- **新增 DailyChallenge 页面**：
  - 顶部：今日挑战卡片（标题 + 详细说明 + 难度标签）
  - 中间：上传区域（复用 UploadPage 的上传逻辑）
  - 结果：AI 评判——达标/未达标 + 具体反馈 + 改进建议
  - 底部：查看之前的挑战结果（localStorage 存储）
- **路由**：新增 `/challenge` 路由
- **首页入口**：UploadPage 增加"每日挑战"入口按钮

---

## 3. 参数实验室

### 目标
解析照片 EXIF 数据，展示参数规律，帮用户建立参数直觉。

### 后端改动
- **新增 backend/exif_analyzer.py**：
  - `parse_exif(image_bytes)`: 用 Pillow 读取 EXIF（光圈、快门、ISO、焦距、相机型号、镜头、拍摄时间）
  - `analyze_params(photos_data)`: 分析多张照片的参数规律
- **扩展 POST /api/analyze**：返回数据中增加 `exif` 字段
  - 新增要求到 requirements.txt（Pillow 已有）
- **新增 POST /api/params/analyze**：根据用户的多张照片数据，AI 生成参数关联分析

### 前端改动
- **新增 ParamsLab 页面**：
  - 顶部：上传多张照片（2-10张）用于参数分析
  - 中间：每张照片的参数卡片（光圈/快门/ISO/焦距，小字展示）
  - 底部：AI 生成的参数关联分析（如"你的最佳照片光圈在 f/4-f/5.6"）
  - 历史照片的参数集合自动累积（localStorage）
- **ReportPage**：报告页 meta 区域增加 EXIF 参数展示
- **路由**：新增 `/params` 路由

---

## 技术约束
- 标记位置用 AI 描述 + 前端推算，不依赖模型返回像素坐标
- EXIF 用 Pillow 读取（已在 requirements.txt）
- 前端保持纯 CSS 暗色摄影主题，不加 UI 框架
- 新增页面使用 React Router，保持 SPA 结构
- 所有新增功能需在无登录状态下可用（MVP 阶段）
