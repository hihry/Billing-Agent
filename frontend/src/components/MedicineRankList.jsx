import { formatPaise } from "../utils/format";
import "./MedicineRankList.css";

/**
 * items: array of { drug_name, qty } OR { drug_name, revenue_paise }
 * valueKey: "qty" | "revenue_paise"
 */
export default function MedicineRankList({ title, items, valueKey }) {
  return (
    <div className="card">
      <h2 className="card-title">{title}</h2>
      {items.length === 0 ? (
        <p className="empty-note">No medicines sold today.</p>
      ) : (
        <ol className="mrl-list">
          {items.map((item, i) => (
            <li key={item.drug_name} className="mrl-item">
              <span className="mrl-rank">{i + 1}</span>
              <span className="mrl-name">{item.drug_name}</span>
              <span className="mrl-value">
                {valueKey === "qty" ? `${item.qty} units` : formatPaise(item.revenue_paise)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
