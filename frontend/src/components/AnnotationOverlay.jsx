import { useRef, useEffect } from "react";

/**
 * 将 AI 标注数据渲染为 Canvas 半透明叠加层。
 *
 * attributes 格式: [{type, label, position, description}]
 * position 位置映射策略：自然语言描述 → Canvas 相对坐标
 */
function resolvePosition(position, imgW, imgH) {
  const pos = position.toLowerCase();
  const w = imgW;
  const h = imgH;

  // 人脸/身体区域映射
  if (pos.includes("面部") || pos.includes("脸") || pos.includes("眼睛") || pos.includes("眼神")) {
    return { x: w * 0.3, y: h * 0.08, rw: w * 0.4, rh: h * 0.22 };
  }
  if (pos.includes("身体") || pos.includes("肢体") || pos.includes("姿态")) {
    return { x: w * 0.25, y: h * 0.3, rw: w * 0.5, rh: h * 0.55 };
  }

  // 通用方位映射
  let x = 0, y = 0, rw = w * 0.3, rh = h * 0.25;
  if (pos.includes("左")) x = 0;
  else if (pos.includes("右")) x = w * 0.7;
  else x = w * 0.35;
  if (pos.includes("上") || pos.includes("顶") || pos.includes("天空")) y = 0;
  else if (pos.includes("下") || pos.includes("底") || pos.includes("地面")) y = h * 0.75;
  else y = h * 0.35;

  if (pos.includes("中") || pos.includes("中央") || pos.includes("主体")) {
    x = w * 0.3;
    y = h * 0.25;
    rw = w * 0.4;
    rh = h * 0.5;
  }

  return { x, y, rw, rh };
}

export default function AnnotationOverlay({ imageUrl, annotations }) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  useEffect(() => {
    if (!imageUrl || !annotations || annotations.length === 0) return;

    const img = new Image();
    imgRef.current = img;
    img.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      // 限制最大渲染尺寸
      const MAX = 1200;
      let drawW = img.naturalWidth;
      let drawH = img.naturalHeight;
      if (drawW > MAX || drawH > MAX) {
        const ratio = Math.min(MAX / drawW, MAX / drawH);
        drawW = Math.round(drawW * ratio);
        drawH = Math.round(drawH * ratio);
      }

      canvas.width = drawW;
      canvas.height = drawH;
      const ctx = canvas.getContext("2d");

      // 绘制原图
      ctx.drawImage(img, 0, 0, drawW, drawH);

      // 九宫格辅助线
      ctx.strokeStyle = "rgba(255,255,255,0.15)";
      ctx.lineWidth = 1;
      ctx.setLineDash([8, 12]);
      const tx = drawW / 3;
      const ty = drawH / 3;
      for (let i = 1; i < 3; i++) {
        ctx.beginPath();
        ctx.moveTo(tx * i, 0);
        ctx.lineTo(tx * i, drawH);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, ty * i);
        ctx.lineTo(drawW, ty * i);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // 绘制标注区域
      for (const anno of annotations) {
        const { x, y, rw, rh } = resolvePosition(anno.position, drawW, drawH);

        if (anno.type === "overexposed") {
          // 红色半透明蒙版
          ctx.fillStyle = "rgba(255, 60, 60, 0.25)";
          ctx.fillRect(x, y, rw, rh);
          ctx.strokeStyle = "rgba(255, 100, 100, 0.8)";
          ctx.lineWidth = 2;
          ctx.setLineDash([]);
          ctx.strokeRect(x, y, rw, rh);
        } else if (anno.type === "underexposed") {
          // 蓝色半透明蒙版
          ctx.fillStyle = "rgba(60, 100, 255, 0.25)";
          ctx.fillRect(x, y, rw, rh);
          ctx.strokeStyle = "rgba(100, 140, 255, 0.8)";
          ctx.lineWidth = 2;
          ctx.setLineDash([]);
          ctx.strokeRect(x, y, rw, rh);
        } else if (anno.type === "blur") {
          // 虚线框
          ctx.strokeStyle = "rgba(255, 255, 255, 0.8)";
          ctx.lineWidth = 2;
          ctx.setLineDash([6, 4]);
          ctx.strokeRect(x, y, rw, rh);
          ctx.setLineDash([]);
        } else if (anno.type === "composition") {
          // 琥珀色裁剪指示
          ctx.strokeStyle = "rgba(232, 148, 58, 0.8)";
          ctx.lineWidth = 2.5;
          ctx.setLineDash([10, 6]);
          ctx.strokeRect(x, y, rw, rh);
          ctx.setLineDash([]);
        }

        // 标签文字
        const labelY = y - 6 > 16 ? y - 6 : y + rh + 16;
        ctx.font = "12px system-ui, sans-serif";
        const textW = ctx.measureText(anno.label).width + 10;
        ctx.fillStyle = "rgba(0,0,0,0.75)";
        ctx.fillRect(x + 2, labelY - 13, textW, 18);
        ctx.fillStyle = "#fff";
        ctx.fillText(anno.label, x + 7, labelY);
      }
    };
    img.src = imageUrl;

    return () => {
      img.onload = null;
    };
  }, [imageUrl, annotations]);

  if (!annotations || annotations.length === 0) {
    return (
      <div className="annotation-empty">
        <p>暂无标注数据</p>
        <span>AI 未检测到需要标注的问题区域</span>
      </div>
    );
  }

  return (
    <div className="annotation-overlay">
      <canvas ref={canvasRef} className="annotation-canvas" />
      <div className="annotation-legend">
        {annotations.map((a, i) => (
          <div key={i} className={`legend-item legend-${a.type}`}>
            <span className="legend-dot" />
            <span className="legend-label">{a.label}</span>
            <span className="legend-desc">{a.description}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
