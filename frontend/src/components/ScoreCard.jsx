export default function ScoreCard({ name, score, stars, comment }) {
  const isNA = stars === "N/A" || score === 0;

  return (
    <div className={`score-card${isNA ? " na" : ""}`}>
      <div className="dim-name">{name}</div>
      <div className={`stars${isNA ? " na-text" : ""}`}>
        {isNA ? "N/A" : stars || "⭐".repeat(score)}
      </div>
      <div className="comment">{comment}</div>
    </div>
  );
}
