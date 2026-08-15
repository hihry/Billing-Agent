import "./StatCard.css";

/** tone controls the sublabel color: "neutral" | "success" | "warning" | "danger" */
export default function StatCard({ label, value, sublabel, tone = "neutral" }) {
  return (
    <div className="stat-card">
      <span className="stat-card-label">{label}</span>
      <span className="stat-card-value">{value}</span>
      {sublabel && <span className={`stat-card-sublabel tone-${tone}`}>{sublabel}</span>}
    </div>
  );
}
