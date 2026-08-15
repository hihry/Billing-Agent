const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail;
    try {
      detail = await res.json();
    } catch {
      detail = { detail: res.statusText };
    }
    const err = new Error(detail.detail || detail.error || `Request failed: ${res.status}`);
    err.status = res.status;
    err.body = detail;
    throw err;
  }
  return res.json();
}

export const api = {
  listLogs: () => request("/api/logs"),
  getReconciliation: (logId) => request(`/api/logs/${logId}/reconciliation`),
  getAnalytics: (logId) => request(`/api/logs/${logId}/analytics`),
  getNarrative: (logId) => request(`/api/logs/${logId}/narrative`),
  generateNarrative: (logId) =>
    request(`/api/logs/${logId}/narrative`, { method: "POST" }),
  ingestLog: (rows) =>
    request("/api/logs", { method: "POST", body: JSON.stringify(rows) }),
};
