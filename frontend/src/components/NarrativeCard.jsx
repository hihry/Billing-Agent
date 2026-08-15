import "./NarrativeCard.css";

const STATUS_LABELS = {
  llm_grounded: { text: "AI-generated · grounded", tone: "success" },
  llm_retry_grounded: { text: "AI-generated · grounded on retry", tone: "success" },
  fallback_no_llm_configured: { text: "Template (no AI configured)", tone: "neutral" },
  fallback_malformed_response: { text: "Template (AI response was invalid)", tone: "warning" },
  fallback_ungrounded_after_retry: { text: "Template (AI figures couldn't be verified)", tone: "warning" },
};

export default function NarrativeCard({ narrative, clinicId, groundingStatus }) {
  const status = STATUS_LABELS[groundingStatus] || { text: groundingStatus, tone: "neutral" };

  return (
    <div className="card narrative-card">
      <div className="narrative-card-header">
        <span>Sent to {clinicId} · WhatsApp</span>
      </div>
      <div className="narrative-bubble">
        <p>{narrative}</p>
      </div>
      <span className={`narrative-status-badge tone-${status.tone}`}>{status.text}</span>
    </div>
  );
}
