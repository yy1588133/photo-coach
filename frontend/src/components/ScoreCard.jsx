export default function ScoreCard({ name, score, comment }) {
  const isNA = comment === "非人像，不适用" || comment === "无法解析";

  return (
    <div className={`score-card${isNA ? " na" : ""}`}>
      <div className="dim-name">{name}</div>
      <div className="score-display">
        {isNA ? (
          <span className="na-text">N/A</span>
        ) : (
          <>
            <span className="score-number">{score}</span>
            <span className="score-unit">分</span>
          </>
        )}
      </div>
      <div className="score-bar-track">
        <div
          className={`score-bar-fill${isNA ? " na-bar" : ""}`}
          style={{ width: isNA ? "0%" : `${score}%` }}
        />
      </div>
      <div className="comment">{comment}</div>
    </div>
  );
}
