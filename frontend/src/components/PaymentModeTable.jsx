import { formatPaise } from "../utils/format";
import "./PaymentModeTable.css";

const MODE_LABELS = { cash: "Cash", card: "Card", upi: "UPI" };

export default function PaymentModeTable({ byPaymentMode }) {
  const modes = Object.keys(byPaymentMode);

  return (
    <div className="card">
      <h2 className="card-title">Payment Mode Breakdown</h2>
      {modes.length === 0 ? (
        <p className="empty-note">No transactions recorded.</p>
      ) : (
        <table className="pm-table">
          <thead>
            <tr>
              <th>Mode</th>
              <th>Billed</th>
              <th>Collected</th>
              <th>Outstanding</th>
            </tr>
          </thead>
          <tbody>
            {modes.map((mode) => {
              const row = byPaymentMode[mode];
              return (
                <tr key={mode}>
                  <td className="pm-mode-cell">{MODE_LABELS[mode] || mode}</td>
                  <td>{formatPaise(row.billed_paise)}</td>
                  <td>{formatPaise(row.collected_paise)}</td>
                  <td>{formatPaise(row.outstanding_paise)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
