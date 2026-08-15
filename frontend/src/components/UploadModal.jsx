import { useState } from "react";
import { X } from "lucide-react";
import { api } from "../api/client";
import "./UploadModal.css";

export default function UploadModal({ onClose, onIngested }) {
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleFile(file) {
    setError(null);
    setResult(null);
    setIsUploading(true);
    try {
      const text = await file.text();
      const rows = JSON.parse(text);
      if (!Array.isArray(rows)) {
        throw new Error("File must contain a JSON array of billing rows.");
      }
      const response = await api.ingestLog(rows);
      setResult(response);
      onIngested();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Upload Billing Log</h2>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <p className="modal-description">
          Select a JSON file containing one clinic-day's billing rows, matching the SwasthiQ schema.
        </p>

        <label className="modal-file-input">
          <input
            type="file"
            accept="application/json"
            disabled={isUploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
          {isUploading ? "Uploading…" : "Choose a file"}
        </label>

        {error && <p className="modal-error">{error}</p>}

        {result && (
          <div className="modal-result">
            <p>
              <strong>{result.valid_count}</strong> valid row{result.valid_count === 1 ? "" : "s"} ingested
              {result.rejected_count > 0 && (
                <> · <strong>{result.rejected_count}</strong> rejected</>
              )}
            </p>
            {result.errors?.length > 0 && (
              <ul className="modal-error-list">
                {result.errors.map((e) => (
                  <li key={e.row_index}>
                    Row {e.row_index}: {e.issues.map((i) => `${i.field} — ${i.reason}`).join("; ")}
                  </li>
                ))}
              </ul>
            )}
            <button className="btn-primary" onClick={onClose}>Done</button>
          </div>
        )}
      </div>
    </div>
  );
}
