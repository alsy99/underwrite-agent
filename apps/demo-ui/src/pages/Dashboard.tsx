import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowRight, RefreshCw } from "lucide-react";
import { listCases } from "../api";
import { ActionBadge, StatusBadge } from "../components/StatusBadge";
import { formatDate, formatVertical, truncateId } from "../lib/format";
import type { CaseListItem } from "../types";

export function Dashboard() {
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCases(await listCases());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  const completed = cases.filter((c) => c.status === "completed").length;
  const review = cases.filter((c) => c.recommended_action === "review").length;

  return (
    <div className="p-8">
      <header className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-slate-900">
            Investigation cases
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            AI-powered document cross-check, policy RAG, and agentic case files
          </p>
        </div>
        <button type="button" onClick={load} className="btn-secondary" disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </header>

      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <div className="card p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Total cases
          </p>
          <p className="mt-2 font-display text-3xl font-semibold text-slate-900">
            {cases.length}
          </p>
        </div>
        <div className="card p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Completed
          </p>
          <p className="mt-2 font-display text-3xl font-semibold text-emerald-600">
            {completed}
          </p>
        </div>
        <div className="card p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Needs review
          </p>
          <p className="mt-2 font-display text-3xl font-semibold text-amber-600">
            {review}
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">Cannot reach API</p>
            <p className="mt-1 text-red-700">{error}</p>
            <p className="mt-2 text-xs">
              Start API: <code className="rounded bg-red-100 px-1">./scripts/start-api.sh</code>
            </p>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-surface-border bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3 font-medium">Case</th>
              <th className="px-5 py-3 font-medium">Vertical</th>
              <th className="px-5 py-3 font-medium">Status</th>
              <th className="px-5 py-3 font-medium">Decision</th>
              <th className="px-5 py-3 font-medium">Signals</th>
              <th className="px-5 py-3 font-medium">Created</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border">
            {loading && cases.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-slate-500">
                  Loading cases…
                </td>
              </tr>
            ) : cases.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-slate-500">
                  No cases yet.{" "}
                  <Link to="/new" className="font-medium text-brand-600 hover:underline">
                    Start an investigation
                  </Link>
                </td>
              </tr>
            ) : (
              cases.map((c) => (
                <tr key={c.case_id} className="hover:bg-slate-50/80">
                  <td className="px-5 py-4 font-mono text-xs text-slate-600">
                    {truncateId(c.case_id)}
                  </td>
                  <td className="px-5 py-4">{formatVertical(c.vertical)}</td>
                  <td className="px-5 py-4">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-5 py-4">
                    <ActionBadge action={c.recommended_action} />
                  </td>
                  <td className="px-5 py-4 text-slate-600">
                    {c.contradictions_count > 0 && (
                      <span className="mr-2 text-red-600">
                        {c.contradictions_count} contradictions
                      </span>
                    )}
                    {c.findings_count} findings
                  </td>
                  <td className="px-5 py-4 text-slate-500">{formatDate(c.created_at)}</td>
                  <td className="px-5 py-4 text-right">
                    <Link
                      to={`/cases/${c.case_id}`}
                      className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700"
                    >
                      View
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
