import "./TracedFiguresPanel.css";

export default function TracedFiguresPanel({ citedFigures }) {
  return (
    <div className="card traced-figures-panel">
      <h2 className="card-title">Traced Figures</h2>
      <p className="tfp-intro">
        Every number above maps to the deterministic report field it came from — this is what gets auto-checked.
      </p>
      {citedFigures.length === 0 ? (
        <p className="empty-note">No figures cited.</p>
      ) : (
        <ul className="tfp-list">
          {citedFigures.map((fig, i) => (
            <li key={`${fig.source_field}-${i}`} className="tfp-item">
              <span className="tfp-value">{fig.value}</span>
              <span className="tfp-field">{fig.source_field}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
