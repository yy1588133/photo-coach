import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ScoreCard from "../components/ScoreCard";
import ReportSection from "../components/ReportSection";
import "./ReportPage.css";

/**
 * 简易 Markdown → HTML（覆盖报告所需的基础语法）
 */
function mdToHtml(md) {
  if (!md) return "";
  let html = md
    // 转义 HTML 实体（先处理，保留 & 兼容）
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // 粗体
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // 行内代码
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    // 标题
    .replace(/^#### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    // 列表项
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    // 表格行（保留管道符，用简单的表格渲染）
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      const cells = row.split("|").map((c) => c.trim());
      const isHeader =
        cells.length > 1 && cells.every((c) => /^:?-{3,}:?$/.test(c));
      if (isHeader) return ""; // 跳过分隔行
      const tag = html.includes("<th>") ? "td" : "th";
      return (
        "<tr>" +
        cells.map((c) => `<${tag}>${c}</${tag}>`).join("") +
        "</tr>"
      );
    })
    // 段落（空行分隔）
    .split(/\n\n+/)
    .map((block) => {
      const trimmed = block.trim();
      if (!trimmed) return "";
      if (
        trimmed.startsWith("<h") ||
        trimmed.startsWith("<tr") ||
        trimmed.startsWith("<li") ||
        trimmed.startsWith("<table")
      )
        return trimmed;
      return `<p>${trimmed.replace(/\n/g, "<br/>")}</p>`;
    })
    .join("\n");

  // 包裹表格
  html = html.replace(
    /(<tr>(?:<th>.+?<\/th>.*?)?<\/tr>\s*)+/g,
    "<table>$&</table>",
  );

  return html;
}

/**
 * 解析 Markdown 报告为 sections 数组，供 ReportSection 渲染
 */
function parseSections(report) {
  if (!report) return [];
  const sections = [];
  // 按 ## 标题分割（保留标题）
  const parts = report.split(/(?=^## )/m);
  for (const part of parts) {
    const lines = part.trim().split("\n");
    const titleLine = lines[0].replace(/^## /, "").trim();
    // 提取评分（⭐）
    const starsMatch = titleLine.match(/^(⭐+)\s*/);
    const stars = starsMatch ? starsMatch[1] : null;
    const title = stars ? titleLine.slice(stars.length).trim() : titleLine;
    const body = lines.slice(1).join("\n").trim();
    if (body) {
      sections.push({
        title,
        stars,
        html: mdToHtml(body),
      });
    }
  }
  return sections;
}

/**
 * 提取"一句话核心改进方向"
 */
function extractCoreDirection(report) {
  if (!report) return null;
  const m = report.match(
    /## 💡\s*一句话核心改进方向\s*\n+(.+?)(?:\n##|\n*$)/s,
  );
  return m ? m[1].trim() : null;
}

export default function ReportPage() {
  const navigate = useNavigate();
  const [reportData, setReportData] = useState(null);
  const [sections, setSections] = useState([]);
  const [coreDirection, setCoreDirection] = useState(null);

  useEffect(() => {
    const stored = localStorage.getItem("photo-coach-report");
    if (!stored) return;
    try {
      const data = JSON.parse(stored);
      setReportData(data);
      setSections(parseSections(data.report));
      setCoreDirection(extractCoreDirection(data.report));
    } catch {
      // ignore
    }
  }, []);

  const handleNewAnalysis = () => {
    localStorage.removeItem("photo-coach-report");
    navigate("/");
  };

  // 空状态
  if (!reportData) {
    return (
      <div className="report-page">
        <div className="report-empty">
          <p>暂无诊断报告</p>
          <button className="btn-retry" onClick={() => navigate("/")}>
            返回上传照片
          </button>
        </div>
      </div>
    );
  }

  const { scores, meta } = reportData;

  // 过滤"基本信息"section，单独展示
  const infoSection = sections.find(
    (s) => s.title.includes("基本信息") || s.title.includes("基本"),
  );
  const diagnosisSections = sections.filter(
    (s) =>
      !s.title.includes("基本信息") &&
      !s.title.includes("基本") &&
      !s.title.includes("一句话核心改进") &&
      !s.title.includes("得分卡"),
  );

  return (
    <div className="report-page">
      {/* 顶栏 */}
      <div className="report-header">
        <div>
          <h2>诊断报告</h2>
          {meta && (
            <p className="report-meta">
              {meta.model} · {meta.image_size_mb}MB
            </p>
          )}
        </div>
        <button className="btn-new" onClick={handleNewAnalysis}>
          新分析
        </button>
      </div>

      {/* 得分卡 */}
      {scores && scores.length > 0 && (
        <div className="score-section">
          <h3>得分总览</h3>
          <div className="score-scroll">
            {scores.map((s, i) => (
              <ScoreCard
                key={i}
                name={s.name}
                score={s.score}
                stars={s.stars}
                comment={s.comment}
              />
            ))}
          </div>
        </div>
      )}

      {/* 一句话核心改进方向 */}
      {coreDirection && (
        <div className="core-direction">
          <div className="label">💡 核心改进方向</div>
          <p>{coreDirection}</p>
        </div>
      )}

      {/* 基本信息摘要 */}
      {infoSection && (
        <div className="report-summary">
          <div
            dangerouslySetInnerHTML={{ __html: infoSection.html }}
          />
        </div>
      )}

      {/* 诊断详情（折叠面板） */}
      {diagnosisSections.length > 0 && (
        <div className="diagnosis-section">
          <h3>详细诊断</h3>
          {diagnosisSections.map((sec, i) => (
            <ReportSection
              key={i}
              title={sec.title}
              stars={sec.stars}
              content={sec.html}
            />
          ))}
        </div>
      )}

      {/* 底部操作 */}
      <div className="bottom-action">
        <button className="btn-next" onClick={handleNewAnalysis}>
          📤 分析下一张
        </button>
      </div>
    </div>
  );
}
