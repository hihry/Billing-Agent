import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import PaymentModeTable from "../components/PaymentModeTable";
import { formatPaise } from "../utils/format";
import "./ReconciliationPage.css";

export default function ReconciliationPage({ reconciliation, clinicId, logDate }) {
  const {
    total_billed_paise,
    total_collected_paise,
    outstanding_paise,
    refunds_paise,
    visit_count,
    refund_visit_count,
    outstanding_visit_count,
    by_payment_mode,
  } = reconciliation;

  const collectedPct =
    total_billed_paise > 0
      ? Math.round((total_collected_paise / total_billed_paise) * 100)
      : null;

  return (
    <div>
      <PageHeader title="EOD Reconciliation" clinicId={clinicId} logDate={logDate} />

      <div className="stat-grid">
        <StatCard
          label="Total Billed"
          value={formatPaise(total_billed_paise)}
          sublabel={`${visit_count} visit${visit_count === 1 ? "" : "s"}`}
        />
        <StatCard
          label="Total Collected"
          value={formatPaise(total_collected_paise)}
          sublabel={collectedPct !== null ? `${collectedPct}% of billed` : "—"}
          tone="success"
        />
        <StatCard
          label="Outstanding"
          value={formatPaise(outstanding_paise)}
          sublabel={`${outstanding_visit_count} pending visit${outstanding_visit_count === 1 ? "" : "s"}`}
          tone="warning"
        />
        <StatCard
          label="Refunds"
          value={formatPaise(refunds_paise)}
          sublabel={`${refund_visit_count} refund${refund_visit_count === 1 ? "" : "s"}`}
          tone="danger"
        />
      </div>

      <PaymentModeTable byPaymentMode={by_payment_mode} />
    </div>
  );
}
