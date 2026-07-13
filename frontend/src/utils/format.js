export function formatDuration(seconds) {
  if (seconds == null) return "—";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${total}s`;
}

export function secondsToHHMM(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function hhmmToSeconds(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 3600 + m * 60;
}

export function formatDate(dateStr) {
  if (!dateStr) return "No date";
  // dateStr is "YYYY-MM-DD" — parse as local, not UTC, to avoid off-by-one.
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function formatDateTime(isoStr) {
  if (!isoStr) return "—";
  // Full ISO timestamp (e.g. a JobStop's created_at) — unlike formatDate,
  // this always includes a time component and a real timezone offset, so
  // native Date parsing is correct here (no local-vs-UTC ambiguity).
  const d = new Date(isoStr);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function statusBadgeClass(status) {
  switch (status) {
    case "published":
      return "badge badge-success";
    case "options_ready":
    case "active":
      return "badge badge-primary";
    case "pending":
    case "draft":
      return "badge badge-gray";
    case "stale":
    case "superseded":
      return "badge badge-warning";
    case "failed":
      return "badge badge-danger";
    default:
      return "badge badge-gray";
  }
}
