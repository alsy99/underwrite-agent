import { actionColor, statusColor } from "../lib/format";
import type { CaseStatus, RecommendedAction } from "../types";

export function StatusBadge({ status }: { status: CaseStatus }) {
  return <span className={`badge ${statusColor(status)}`}>{status}</span>;
}

export function ActionBadge({ action }: { action: RecommendedAction | null }) {
  if (!action) return <span className="badge bg-slate-100 text-slate-500">pending</span>;
  return (
    <span className={`badge border ${actionColor(action)}`}>{action}</span>
  );
}
