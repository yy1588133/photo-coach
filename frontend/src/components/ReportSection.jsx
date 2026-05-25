import { useState } from "react";

export default function ReportSection({ title, score, content }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`report-section${open ? " open" : ""}`}>
      <button className="section-header" onClick={() => setOpen(!open)}>
        <span className="dim-title">{title}</span>
        {score > 0 && <span className="dim-score">{score}分</span>}
        <svg
          className="chevron"
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path d="M5 8l5 5 5-5" />
        </svg>
      </button>
      <div className="section-body">
        <div
          className="section-content"
          dangerouslySetInnerHTML={{ __html: content }}
        />
      </div>
    </div>
  );
}
