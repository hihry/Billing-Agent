/** Format integer paise as a rupee string, e.g. 4285000 -> "₹42,850". */
export function formatPaise(paise) {
  const rupees = Math.abs(paise) / 100;
  const sign = paise < 0 ? "-" : "";
  const formatted = rupees % 1 === 0
    ? rupees.toLocaleString("en-IN", { maximumFractionDigits: 0 })
    : rupees.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${sign}₹${formatted}`;
}

/** 13 -> "1pm", 0 -> "12am", 12 -> "12pm" */
export function formatHour(hour24) {
  const period = hour24 < 12 ? "am" : "pm";
  const h12 = hour24 % 12 === 0 ? 12 : hour24 % 12;
  return `${h12}${period}`;
}

/** 13 -> "1pm-2pm" (a one-hour bucket starting at hour24) */
export function formatHourRange(hour24) {
  return `${formatHour(hour24)}-${formatHour((hour24 + 1) % 24)}`;
}

/** "2026-07-27" -> "27 Jul 2026" */
export function formatLogDate(isoDate) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
}
