import type { CaseStatus, LoanVertical, RecommendedAction } from "../types";

export function formatVertical(v: LoanVertical): string {
  const map: Record<LoanVertical, string> = {
    sba_7a: "SBA 7(a)",
    cre_acquisition: "CRE Acquisition",
    specialty_mortgage_bank_statement: "Bank Statement Mortgage",
  };
  return map[v] || v;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function statusColor(status: CaseStatus): string {
  switch (status) {
    case "completed":
      return "bg-emerald-100 text-emerald-800";
    case "processing":
      return "bg-blue-100 text-blue-800";
    case "queued":
      return "bg-amber-100 text-amber-800";
    case "failed":
      return "bg-red-100 text-red-800";
  }
}

export function actionColor(action: RecommendedAction | null): string {
  switch (action) {
    case "approve":
      return "bg-emerald-100 text-emerald-800 border-emerald-200";
    case "decline":
      return "bg-red-100 text-red-800 border-red-200";
    case "review":
      return "bg-amber-100 text-amber-800 border-amber-200";
    default:
      return "bg-slate-100 text-slate-600 border-slate-200";
  }
}

export function severityColor(severity: string): string {
  const s = severity.toLowerCase();
  if (s === "high") return "text-red-600 bg-red-50";
  if (s === "medium") return "text-amber-700 bg-amber-50";
  return "text-slate-600 bg-slate-100";
}

export function truncateId(id: string): string {
  return id.slice(0, 8) + "…";
}
