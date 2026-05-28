import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSettings } from "../hooks/useSettings";
import "./ParamsLab.css";

const HISTORY_KEY = "pc-params-history";

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(entry) {
  const history = loadHistory();
  history.unshift(entry);
  if (history.length > 20) history.length = 20;
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

export default function ParamsLab() {
  const navigate = useNavigate();
  const [settings] = useSettings();
  const fileInputRef = useRef(null);

  const [photos, setPhotos] = useState([]);
  const [loadingExif, setLoadingExif] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState(loadHistory);

  // 一次性提取所有照片的 EXIF
  const handleFiles = useCallback(async (files) => {
    const validFiles = Array.from(files).filter(
      (f) => f && f.type.startsWith("image/")
    );
    if (validFiles.length === 0) {
      setError("请选择至少一张图片");
      return;
    }
    if (validFiles.length < 2) {
      setError("至少需要 2 张照片才能进行参数分析");
    }

    setError(null);
    setAnalysis(null);
    setLoadingExif(true);

    const newPhotos = [];
    for (const f of validFiles) {
      const previewUrl = URL.createObjectURL(f);
      // 提取 EXIF
      let exif = {};
      try {
        const formData = new FormData();
        formData.append("image", f);
        const resp = await fetch("/api/extract-exif", {
          method: "POST",
          body: formData,
        });
        if (resp.ok) {
          const data = await resp.json();
          exif = data.exif || {};
        }
      } catch {
        // EXIF 提取失败，留空
      }
      newPhotos.push({ file: f, previewUrl, exif, filename: f.name });
    }

    setPhotos(newPhotos);
    setLoadingExif(false);
  }, []);

  // 调用 /api/params/analyze 进行 AI 分析
  const handleAnalyze = async () => {
    const exifPhotos = photos
      .filter((p) => p.exif && Object.keys(p.exif).length > 0)
      .map((p) => ({ filename: p.filename, exif: p.exif }));

    if (exifPhotos.length < 2) {
      setError("至少需要 2 张包含 EXIF 数据的照片才能进行分析");
      return;
    }

    setAnalyzing(true);
    setError(null);

    const formData = new FormData();
    formData.append("photos_data", JSON.stringify(exifPhotos));
    if (settings.provider) formData.append("provider", settings.provider);
    if (settings.model) formData.append("model", settings.model);
    if (settings.apiKey) formData.append("api_key", settings.apiKey);
    if (settings.baseUrl) formData.append("base_url", settings.baseUrl);

    try {
      const resp = await fetch("/api/params/analyze", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `请求失败 (${resp.status})`);
      }
      const data = await resp.json();
      setAnalysis(data.analysis);

      // 保存历史
      const paramsSummary = exifPhotos
        .slice(0, 3)
        .map((p) => {
          const e = p.exif;
          const parts = [];
          if (e.aperture) parts.push(e.aperture);
          if (e.shutter_speed) parts.push(e.shutter_speed);
          if (e.iso) parts.push(`ISO${e.iso}`);
          return `${p.filename}: ${parts.join(" ")}`;
        })
        .join("; ");
      saveHistory({
        date: new Date().toISOString(),
        photoCount: photos.length,
        paramsSummary,
      });
      setHistory(loadHistory());
    } catch (err) {
      setError(err.message || "分析失败，请重试");
    } finally {
      setAnalyzing(false);
    }
  };

  // 重置
  const handleReset = () => {
    photos.forEach((p) => URL.revokeObjectURL(p.previewUrl));
    setPhotos([]);
    setAnalysis(null);
    setError(null);
  };

  // 组件卸载清理
  useEffect(() => {
    return () => {
      photos.forEach((p) => URL.revokeObjectURL(p.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="params-page">
      <div className="params-container">
        {/* 顶栏 */}
        <div className="params-header">
          <button className="btn-back" onClick={() => navigate("/")}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 4l-6 6 6 6" />
            </svg>
            返回
          </button>
          <h2>参数实验室</h2>
        </div>

        <p className="params-intro">
          上传多张照片，提取 EXIF 拍摄参数，AI 分析你的参数使用规律并给出优化建议
        </p>

        {/* 上传区域 */}
        {!loadingExif && photos.length === 0 && (
          <div
            className="params-upload"
            onClick={() => fileInputRef.current?.click()}
          >
            <p>点击选择多张照片</p>
            <span className="upload-hint">支持 JPEG / PNG / WebP / HEIC，至少 2 张</span>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
          multiple
          style={{ display: "none" }}
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />

        {/* 加载中 */}
        {loadingExif && (
          <div className="analyzing-container" style={{ marginTop: "2rem" }}>
            <div className="develop-ring" />
            <p className="analyzing-text">正在提取 EXIF 参数…</p>
          </div>
        )}

        {/* 参数卡片网格 */}
        {photos.length > 0 && (
          <>
            <div className="params-grid">
              {photos.map((p, i) => (
                <div key={i} className="param-card">
                  <img
                    className="param-thumb"
                    src={p.previewUrl}
                    alt={p.filename}
                  />
                  <div className="param-info">
                    <span className="param-filename">{p.filename}</span>
                    {p.exif && Object.keys(p.exif).length > 0 ? (
                      <div className="param-rows">
                        {p.exif.aperture && <span>{p.exif.aperture}</span>}
                        {p.exif.shutter_speed && (
                          <span>{p.exif.shutter_speed}</span>
                        )}
                        {p.exif.iso && <span>ISO {p.exif.iso}</span>}
                        {p.exif.focal_length && (
                          <span className="param-lens">
                            {p.exif.focal_length}
                          </span>
                        )}
                        {p.exif.camera && (
                          <span className="param-lens">{p.exif.camera}</span>
                        )}
                      </div>
                    ) : (
                      <span className="param-na">无 EXIF 数据</span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* 操作按钮 */}
            {!analyzing && !analysis && (
              <div style={{ marginTop: "1.25rem", textAlign: "center" }}>
                <button
                  className="btn-analyze"
                  style={{ maxWidth: 320 }}
                  onClick={handleAnalyze}
                >
                  AI 分析参数规律
                </button>
                <button
                  className="btn-retry"
                  style={{ maxWidth: 320, marginTop: "0.5rem" }}
                  onClick={handleReset}
                >
                  重新选择
                </button>
              </div>
            )}

            {/* 分析中 */}
            {analyzing && (
              <div
                className="analyzing-container"
                style={{ marginTop: "1.5rem" }}
              >
                <div className="develop-ring" />
                <p className="analyzing-text">AI 正在分析参数规律…</p>
              </div>
            )}

            {/* 分析结果 */}
            {analysis && (
              <div className="params-analysis">
                <h4>参数分析报告</h4>
                <div className="analysis-content">{analysis}</div>
                <button
                  className="btn-retry"
                  style={{ marginTop: "1rem" }}
                  onClick={handleReset}
                >
                  重新分析
                </button>
              </div>
            )}
          </>
        )}

        {error && !analyzing && <div className="error-msg">{error}</div>}

        {/* 历史记录 */}
        {history.length > 0 && (
          <div className="params-history">
            <h4>历史分析</h4>
            {history.map((h, i) => (
              <div key={i} className="history-param-item">
                <span className="hp-date">
                  {new Date(h.date).toLocaleDateString("zh-CN")}
                </span>
                <span className="hp-name">
                  {h.photoCount} 张照片
                </span>
                <span className="hp-params">{h.paramsSummary}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
