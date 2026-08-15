import { useState } from "react";
import PageHeader from "../components/PageHeader";
import NarrativeCard from "../components/NarrativeCard";
import TracedFiguresPanel from "../components/TracedFiguresPanel";
import { api } from "../api/client";
import "./NarrativePage.css";

export default function NarrativePage({ logId, narrative, clinicId, logDate, onNarrativeGenerated }) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);

  async function handleGenerate() {
    setIsGenerating(true);
    setError(null);
    try {
      const result = await api.generateNarrative(logId);
      onNarrativeGenerated(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div>
      <PageHeader title="AI Narrative Summary" clinicId={clinicId} logDate={logDate} />

      {!narrative ? (
        <div className="card narrative-empty-state">
          <p>No summary generated yet for this day.</p>
          <button className="btn-primary" onClick={handleGenerate} disabled={isGenerating}>
            {isGenerating ? "Generating…" : "Generate Summary"}
          </button>
          {error && <p className="narrative-error">{error}</p>}
        </div>
      ) : (
        <>
          <div className="narrative-layout">
            <NarrativeCard
              narrative={narrative.narrative}
              clinicId={clinicId}
              groundingStatus={narrative.grounding_status}
            />
            <TracedFiguresPanel citedFigures={narrative.cited_figures} />
          </div>
          <button className="btn-secondary regen-btn" onClick={handleGenerate} disabled={isGenerating}>
            {isGenerating ? "Regenerating…" : "Regenerate"}
          </button>
          {error && <p className="narrative-error">{error}</p>}
        </>
      )}
    </div>
  );
}
