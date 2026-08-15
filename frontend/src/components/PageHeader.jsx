import { formatLogDate } from "../utils/format";
import "./PageHeader.css";

export default function PageHeader({ title, clinicId, logDate }) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-header-title">{title}</h1>
        <p className="page-header-subtitle">{clinicId}</p>
      </div>
      {logDate && (
        <div className="page-header-date">
          <span>{formatLogDate(logDate)}</span>
        </div>
      )}
    </div>
  );
}
