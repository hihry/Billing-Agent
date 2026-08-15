import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { formatHour, formatHourRange, formatPaise } from "../utils/format";
import "./RevenueByHourChart.css";

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { hour, revenue_paise } = payload[0].payload;
  return (
    <div className="rbh-tooltip">
      <strong>{formatHour(hour)}</strong>
      <span>{formatPaise(revenue_paise)}</span>
    </div>
  );
}

export default function RevenueByHourChart({ revenueByHour, peakHour, peakHourRevenuePaise }) {
  const data = revenueByHour.map((d) => ({ ...d, hourLabel: formatHour(d.hour) }));

  return (
    <div className="card">
      <div className="rbh-header">
        <h2 className="card-title" style={{ margin: 0 }}>Revenue by Hour of Day</h2>
        {peakHour !== null && peakHour !== undefined && (
          <span className="rbh-peak-label">
            Peak: {formatHourRange(peakHour)} — {formatPaise(peakHourRevenuePaise)}
          </span>
        )}
      </div>

      {data.length === 0 ? (
        <p className="empty-note">No sales activity recorded for this day.</p>
      ) : (
        <div className="rbh-chart-wrap">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={data} barCategoryGap="28%">
              <XAxis
                dataKey="hourLabel"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 11, fill: "var(--color-text-muted)", fontFamily: "var(--font-ui)" }}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(22,58,95,0.04)" }} />
              <Bar dataKey="revenue_paise" radius={[4, 4, 0, 0]} maxBarSize={36}>
                {data.map((entry) => (
                  <Cell
                    key={entry.hour}
                    fill={entry.hour === peakHour ? "var(--color-navy)" : "#C9D9E8"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
