# 超大图片自动压缩

## 目标
图片超过 15MB 时不拒绝，自动压缩后再分析。

## 改动

### 1. backend/requirements.txt
添加 `Pillow>=10.0.0`

### 2. backend/main.py
- 添加图片压缩函数 `compress_image(image_bytes, max_mb=15)`：
  - 用 Pillow 打开图片
  - 如果原图 ≤ max_mb，直接返回原图
  - 超过则逐步降低质量和/或缩放尺寸，直到 ≤ max_mb
  - 最低质量 30%，最小长边 1024px
  - 返回压缩后的 bytes
- 在 `/api/analyze` 中，将 `if len(image_bytes) > MAX_IMAGE_SIZE_BYTES` 的 413 拒绝改为调用 `compress_image()` 自动压缩
- 压缩后在 meta 中标注 `compressed: true` 和原始大小

### 3. frontend UploadPage.jsx
- 去掉或大幅提高前端 15MB 硬限制（因为后端会自动处理）
- 可以保留一个提示但不再拒绝上传

## 约束
- 压缩保持 JPEG 格式输出
- 压缩后的图片质量不能太差（保证 AI 仍能分析）
