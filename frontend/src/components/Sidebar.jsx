import { BarChart3, FileText, MessageSquareText, Plus } from "lucide-react";
import { formatLogDate } from "../utils/format";
import "./Sidebar.css";

const VIEWS = [
  { id: "reconciliation", label: "Reconciliation", icon: FileText },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "narrative", label: "AI Narrative", icon: MessageSquareText },
];

export default function Sidebar({
  logs,
  selectedLogId,
  onSelectLog,
  activeView,
  onSelectView,
  onUploadClick,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">
          <span className="sidebar-brand-plus">+</span>
        </div>
        <span className="sidebar-brand-name">SwasthiQ</span>
      </div>

      <nav className="sidebar-nav" aria-label="Report views">
        {VIEWS.map((v) => {
          const Icon = v.icon;
          const isActive = v.id === activeView;
          return (
            <button
              key={v.id}
              className={`sidebar-nav-item${isActive ? " is-active" : ""}`}
              onClick={() => onSelectView(v.id)}
              disabled={!selectedLogId}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon size={18} strokeWidth={2} />
              <span>{v.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-section-header">
        <span>Billing Logs</span>
        <button className="sidebar-upload-btn" onClick={onUploadClick} aria-label="Upload a billing log">
          <Plus size={14} strokeWidth={2.5} />
        </button>
      </div>

      <ul className="sidebar-log-list">
        {logs.length === 0 && (
          <li className="sidebar-log-empty">No logs uploaded yet.</li>
        )}
        {logs.map((log) => {
          const isSelected = log.log_id === selectedLogId;
          return (
            <li key={log.log_id}>
              <button
                className={`sidebar-log-item${isSelected ? " is-selected" : ""}`}
                onClick={() => onSelectLog(log.log_id)}
              >
                <span className={`sidebar-log-dot${isSelected ? " is-filled" : ""}`} />
                <div className="sidebar-log-item-text">
                  <span className="sidebar-log-date">{formatLogDate(log.log_date)}</span>
                  <span className="sidebar-log-meta">
                    {log.visit_count} visit{log.visit_count === 1 ? "" : "s"}
                    {log.rejected_count > 0 ? ` · ${log.rejected_count} rejected` : ""}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
