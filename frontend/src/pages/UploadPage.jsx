import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSettings } from "../hooks/useSettings";
import SettingsModal from "../components/SettingsModal";
import "./UploadPage.css";

const ANALYZE_STAGES = [
  "正在分析构图与画面平衡…",
  "正在检查曝光与光线质量…",
  "正在评估色彩与白平衡…",
  "正在审阅对焦与景深…",
  "正在解读面部表情与眼神…",
  "正在观察肢体语言与姿态…",
  "正在生成诊断报告…",
];

export default function UploadPage() {
  const navigate = useNavigate();
  const [settings, updateSettings] = useSettings();
  const fileInputRef = useRef(null);
  const dropRef = useRef(null);

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);

  // 轮播分析阶段文字
  useEffect(() => {
    if (!analyzing) return;
    const timer = setInterval(() => {
      setStageIndex((prev) => (prev + 1) % ANALYZE_STAGES.length);
    }, 2000);
    return () => clearInterval(timer);
  }, [analyzing]);

  // 处理文件
  const handleFile = useCallback(
    (f) => {
      if (!f || !f.type.startsWith("image/")) {
        setError("请选择一张图片文件");
        return;
      }
      setError(null);
      setFile(f);
      const url = URL.createObjectURL(f);
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return url;
      });
    },
    [],
  );

  // 拖拽事件
  const onDragEnter = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);
  const onDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);
  const onDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
  }, []);
  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  // 粘贴事件
  useEffect(() => {
    const onPaste = (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          handleFile(item.getAsFile());
          break;
        }
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [handleFile]);

  // 调用分析API
  const handleAnalyze = async () => {
    if (!file) return;
    setAnalyzing(true);
    setError(null);
    setStageIndex(0);

    const formData = new FormData();
    formData.append("image", file);
    if (settings.provider) formData.append("provider", settings.provider);
    if (settings.model) formData.append("model", settings.model);
    if (settings.apiKey) formData.append("api_key", settings.apiKey);
    if (settings.baseUrl) formData.append("base_url", settings.baseUrl);

    try {
      const resp = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `请求失败 (${resp.status})`);
      }
      const data = await resp.json();

      // 存到 localStorage 传给报告页
      localStorage.setItem("photo-coach-report", JSON.stringify(data));

      navigate("/report");
    } catch (err) {
      setError(err.message || "分析失败，请重试");
      setAnalyzing(false);
    }
  };

  // 组件卸载清理
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  return (
    <div className="upload-page">
      <div className="upload-header">
        <h1>Photo Coach</h1>
        <p>AI 摄影教练 — 拍摄 / 上传，即刻诊断</p>
      </div>

      {/* 上传区域 */}
      <div
        ref={dropRef}
        className={`upload-zone${dragOver ? " drag-over" : ""}${file ? " has-file" : ""}`}
        onClick={() => !analyzing && fileInputRef.current?.click()}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {file ? (
          <>
            <svg
              className="upload-icon"
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <path d="M20 6L9 17l-5-5" />
            </svg>
            <p>已选择图片</p>
            <span className="upload-hint">点击更换 / 拖拽新图片</span>
          </>
        ) : (
          <>
            <svg
              className="upload-icon"
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="M21 15l-5-5L5 21" />
            </svg>
            <p>点击上传 / 拖拽图片到此处</p>
            <span className="upload-hint">也支持 Ctrl+V 粘贴</span>
          </>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
        capture="environment"
        style={{ display: "none" }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
          // 重置 input，允许重复选择同一文件
          e.target.value = "";
        }}
      />

      {/* 预览 & 操作 */}
      {file && !analyzing && (
        <div className="preview-container">
          {previewUrl && (
            <img
              className="preview-image"
              src={previewUrl}
              alt="预览"
            />
          )}
          <button className="btn-analyze" onClick={handleAnalyze}>
            开始分析
          </button>
        </div>
      )}

      {/* 分析中 */}
      {analyzing && (
        <div className="analyzing-container">
          {previewUrl && (
            <img className="analyzing-thumb" src={previewUrl} alt="" />
          )}
          <div className="develop-animation">
            <div className="develop-ring" />
            <div className="develop-dot" />
          </div>
          <p className="analyzing-text">
            {ANALYZE_STAGES[stageIndex]}
          </p>
        </div>
      )}

      {/* 错误信息 */}
      {error && !analyzing && (
        <div className="error-msg">{error}</div>
      )}

      {/* 支持格式 */}
      <p className="format-list">支持 JPEG / PNG / WebP / HEIC，超大图片将自动压缩</p>

      {/* 设置按钮 */}
      <button
        className="settings-trigger"
        onClick={() => setShowSettings(true)}
        aria-label="设置"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
        </svg>
      </button>

      {/* 设置弹窗 */}
      {showSettings && (
        <SettingsModal
          settings={settings}
          onSave={updateSettings}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}
