import PageHeader from "../components/PageHeader";
import RevenueByHourChart from "../components/RevenueByHourChart";
import MedicineRankList from "../components/MedicineRankList";
import "./AnalyticsPage.css";

export default function AnalyticsPage({ analytics, clinicId, logDate }) {
  const {
    revenue_by_hour,
    peak_hour,
    peak_hour_revenue_paise,
    top_medicines_by_qty,
    top_medicines_by_revenue,
  } = analytics;

  return (
    <div>
      <PageHeader title="Analytics" clinicId={clinicId} logDate={logDate} />

      <div className="analytics-chart-row">
        <RevenueByHourChart
          revenueByHour={revenue_by_hour}
          peakHour={peak_hour}
          peakHourRevenuePaise={peak_hour_revenue_paise}
        />
      </div>

      <div className="analytics-rank-row">
        <MedicineRankList title="Top Medicines — by Quantity" items={top_medicines_by_qty} valueKey="qty" />
        <MedicineRankList title="Top Medicines — by Revenue" items={top_medicines_by_revenue} valueKey="revenue_paise" />
      </div>
    </div>
  );
}
