import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSettings } from "../hooks/useSettings";
import "./DailyChallenge.css";

const DIFFICULTY_LABELS = { 1: "入门", 2: "进阶", 3: "挑战" };

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem("pc-challenge-history") || "[]");
  } catch {
    return [];
  }
}

function saveHistory(entry) {
  const history = loadHistory();
  history.unshift(entry);
  if (history.length > 30) history.length = 30;
  localStorage.setItem("pc-challenge-history", JSON.stringify(history));
}

export default function DailyChallenge() {
  const navigate = useNavigate();
  const [settings] = useSettings();
  const fileInputRef = useRef(null);

  const [challenge, setChallenge] = useState(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [judging, setJudging] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState(loadHistory);

  // 加载今日挑战
  useEffect(() => {
    fetch("/api/challenge/today")
      .then((r) => r.json())
      .then((d) => setChallenge(d.challenge))
      .catch(() => setError("加载今日挑战失败"));
  }, []);

  const handleFile = useCallback((f) => {
    if (!f || !f.type.startsWith("image/")) {
      setError("请选择一张图片文件");
      return;
    }
    setError(null);
    setResult(null);
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return url;
    });
  }, []);

  const handleJudge = async () => {
    if (!file || !challenge) return;
    setJudging(true);
    setError(null);

    const formData = new FormData();
    formData.append("image", file);
    formData.append("challenge_id", challenge.id);
    if (settings.provider) formData.append("provider", settings.provider);
    if (settings.model) formData.append("model", settings.model);
    if (settings.apiKey) formData.append("api_key", settings.apiKey);
    if (settings.baseUrl) formData.append("base_url", settings.baseUrl);

    try {
      const resp = await fetch("/api/challenge/judge", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `请求失败 (${resp.status})`);
      }
      const data = await resp.json();
      setResult(data.judgment);
      saveHistory({
        date: new Date().toISOString(),
        challengeId: challenge.id,
        title: challenge.title,
        passed: data.judgment.passed,
        comment: data.judgment.comment,
      });
      setHistory(loadHistory());
    } catch (err) {
      setError(err.message || "评判失败，请重试");
    } finally {
      setJudging(false);
    }
  };

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  if (!challenge) {
    return (
      <div className="challenge-page">
        <div className="challenge-container">
          {error ? (
            <div className="error-msg">{error}</div>
          ) : (
            <div className="analyzing-container">
              <div className="develop-ring" />
              <p className="analyzing-text">加载今日挑战…</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="challenge-page">
      <div className="challenge-container">
        {/* 顶栏 */}
        <div className="challenge-header">
          <button className="btn-back" onClick={() => navigate("/")}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 4l-6 6 6 6"/></svg>
            返回
          </button>
          <h2>每日挑战</h2>
        </div>

        {/* 今日挑战卡片 */}
        <div className="challenge-card">
          <div className="challenge-badge difficulty-{challenge.difficulty}">
            {DIFFICULTY_LABELS[challenge.difficulty] || "未知"}
          </div>
          <h3>{challenge.title}</h3>
          <p className="challenge-desc">{challenge.description}</p>
          <div className="challenge-criteria">
            <strong>评分标准：</strong>{challenge.criteria}
          </div>
        </div>

        {/* 上传区域 */}
        <div
          className={`challenge-upload${file ? " has-file" : ""}`}
          onClick={() => !judging && fileInputRef.current?.click()}
        >
          {file ? (
            <p>已选择图片，点击更换</p>
          ) : (
            <p>点击上传照片完成挑战</p>
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
            e.target.value = "";
          }}
        />

        {/* 预览与提交 */}
        {file && !judging && !result && (
          <div className="preview-container">
            {previewUrl && (
              <img className="preview-image" src={previewUrl} alt="预览" />
            )}
            <button className="btn-analyze" onClick={handleJudge}>
              提交评判
            </button>
          </div>
        )}

        {/* 评判中 */}
        {judging && (
          <div className="analyzing-container">
            <div className="develop-ring" />
            <p className="analyzing-text">AI 正在评判…</p>
          </div>
        )}

        {/* 评判结果 */}
        {result && (
          <div className={`judge-result${result.passed ? " passed" : " failed"}`}>
            <div className="result-verdict">
              {result.passed ? "达标" : "未达标"}
            </div>
            <p className="result-comment">{result.comment}</p>
            {result.highlights && result.highlights.length > 0 && (
              <div className="result-list">
                <strong>亮点</strong>
                {result.highlights.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </div>
            )}
            {result.suggestions && result.suggestions.length > 0 && (
              <div className="result-list suggestions">
                <strong>改进建议</strong>
                {result.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </div>
            )}
            <button className="btn-retry" onClick={() => { setResult(null); setFile(null); }}>
              再试一次
            </button>
          </div>
        )}

        {error && !judging && <div className="error-msg">{error}</div>}

        {/* 历史记录 */}
        {history.length > 0 && (
          <div className="challenge-history">
            <h4>挑战记录</h4>
            {history.slice(0, 10).map((h, i) => (
              <div key={i} className={`history-item${h.passed ? " passed" : " failed"}`}>
                <span className="history-date">
                  {new Date(h.date).toLocaleDateString("zh-CN")}
                </span>
                <span className="history-title">{h.title}</span>
                <span className="history-badge">
                  {h.passed ? "达标" : "未达标"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
