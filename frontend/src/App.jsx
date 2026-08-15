import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import UploadModal from "./components/UploadModal";
import ReconciliationPage from "./pages/ReconciliationPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import NarrativePage from "./pages/NarrativePage";
import { api } from "./api/client";
import "./App.css";

export default function App() {
  const [logs, setLogs] = useState([]);
  const [selectedLogId, setSelectedLogId] = useState(null);
  const [activeView, setActiveView] = useState("reconciliation");
  const [showUploadModal, setShowUploadModal] = useState(false);

  const [reconciliation, setReconciliation] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [narrative, setNarrative] = useState(null);

  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);

  async function refreshLogs() {
    try {
      const data = await api.listLogs();
      setLogs(data);
      if (!selectedLogId && data.length > 0) {
        setSelectedLogId(data[0].log_id);
      }
    } catch (err) {
      setLoadError(err.message);
    }
  }

  useEffect(() => {
    refreshLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedLogId) return;

    let cancelled = false;
    setIsLoading(true);
    setLoadError(null);
    setNarrative(null); // narrative is per-log; don't show stale content while switching

    Promise.all([
      api.getReconciliation(selectedLogId),
      api.getAnalytics(selectedLogId),
      api.getNarrative(selectedLogId).catch((err) => (err.status === 404 ? null : Promise.reject(err))),
    ])
      .then(([recon, an, narr]) => {
        if (cancelled) return;
        setReconciliation(recon);
        setAnalytics(an);
        setNarrative(narr);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedLogId]);

  const selectedLog = logs.find((l) => l.log_id === selectedLogId);

  return (
    <div className="app-shell">
      <Sidebar
        logs={logs}
        selectedLogId={selectedLogId}
        onSelectLog={setSelectedLogId}
        activeView={activeView}
        onSelectView={setActiveView}
        onUploadClick={() => setShowUploadModal(true)}
      />

      <main className="app-main">
        {!selectedLogId && (
          <div className="app-empty-state">
            <p>Upload a billing log to get started.</p>
            <button className="btn-primary" onClick={() => setShowUploadModal(true)}>
              Upload Billing Log
            </button>
          </div>
        )}

        {selectedLogId && isLoading && <p className="app-loading">Loading…</p>}

        {selectedLogId && loadError && <p className="app-error">{loadError}</p>}

        {selectedLogId && !isLoading && !loadError && reconciliation && analytics && (
          <>
            {activeView === "reconciliation" && (
              <ReconciliationPage
                reconciliation={reconciliation}
                clinicId={selectedLog?.clinic_id}
                logDate={selectedLog?.log_date}
              />
            )}
            {activeView === "analytics" && (
              <AnalyticsPage
                analytics={analytics}
                clinicId={selectedLog?.clinic_id}
                logDate={selectedLog?.log_date}
              />
            )}
            {activeView === "narrative" && (
              <NarrativePage
                logId={selectedLogId}
                narrative={narrative}
                clinicId={selectedLog?.clinic_id}
                logDate={selectedLog?.log_date}
                onNarrativeGenerated={setNarrative}
              />
            )}
          </>
        )}
      </main>

      {showUploadModal && (
        <UploadModal
          onClose={() => setShowUploadModal(false)}
          onIngested={refreshLogs}
        />
      )}
    </div>
  );
}
