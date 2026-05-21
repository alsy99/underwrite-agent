import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Scale,
} from "lucide-react";
import { getAudit, getCase } from "../api";
import { ActionBadge, StatusBadge } from "../components/StatusBadge";
import { formatDate, formatVertical, severityColor } from "../lib/format";
import type { AuditEvent, CaseResponse } from "../types";

export function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const [data, setData] = useState<CaseResponse | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!caseId) return;
    try {
      const [c, a] = await Promise.all([getCase(caseId), getAudit(caseId)]);
      setData(c);
      setAudit(a);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [caseId]);

  useEffect(() => {
    load();
    const t = setInterval(() => {
      if (data?.status !== "completed" && data?.status !== "failed") load();
    }, 4000);
    return () => clearInterval(t);
  }, [load, data?.status]);

  if (!caseId) return null;

  const cf = data?.case_file;
  const processing = data?.status === "queued" || data?.status === "processing";

  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
      <Link
        to="/"
        className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 sm:mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to cases
      </Link>

      <header className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="break-all font-mono text-xs text-slate-500">{caseId}</p>
          <h1 className="mt-1 font-display text-xl font-semibold text-slate-900 sm:text-2xl">
            Investigation case file
          </h1>
          {data && (
            <p className="mt-1 text-sm text-slate-500">
              {formatVertical(data.vertical)} · {formatDate(data.created_at)}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {data && <StatusBadge status={data.status} />}
          {cf && <ActionBadge action={cf.recommended_action} />}
        </div>
      </header>

      {processing && (
        <div className="mb-6 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-5 py-4 text-sm text-blue-900">
          <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
          Investigation in progress — polling every 4s. Ensure worker is running.
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {data?.error && (
        <div className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800">
          {data.error}
        </div>
      )}

      {cf && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <section className="card p-4 sm:p-6">
              <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-slate-900">
                <FileText className="h-5 w-5 text-brand-600" />
                Executive summary
              </h2>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {cleanSummary(cf.executive_summary)}
              </p>
            </section>

            {cf.contradictions.length > 0 && (
              <section className="card p-4 sm:p-6">
                <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-slate-900">
                  <AlertTriangle className="h-5 w-5 text-red-500" />
                  Cross-document contradictions
                </h2>
                <ul className="mt-4 space-y-4">
                  {cf.contradictions.map((c, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-surface-border p-4"
                    >
                      <span
                        className={`badge ${severityColor(c.severity)}`}
                      >
                        {c.severity}
                      </span>
                      <p className="mt-2 text-sm font-medium text-slate-900">
                        {c.claim_a}
                      </p>
                      <p className="text-sm text-slate-500">vs {c.claim_b}</p>
                      <p className="mt-2 text-xs italic text-slate-500">
                        "{c.quoted_evidence}"
                      </p>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {cf.policy_findings.length > 0 && (
              <section className="card p-4 sm:p-6">
                <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-slate-900">
                  <Scale className="h-5 w-5 text-brand-600" />
                  Policy compliance (RAG)
                </h2>
                <ul className="mt-4 space-y-3">
                  {cf.policy_findings.map((p, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-surface-border px-4 py-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs font-semibold text-brand-700">
                          {p.rule_ref}
                        </span>
                        <span className="badge bg-slate-100 text-slate-700">
                          {p.status}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-slate-600">{p.excerpt}</p>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {cf.findings.length > 0 && (
              <section className="card p-4 sm:p-6">
                <h2 className="font-display text-lg font-semibold text-slate-900">
                  Structured findings
                </h2>
                <ul className="mt-4 space-y-3">
                  {cf.findings.map((f) => (
                    <li key={f.id} className="border-l-2 border-brand-200 pl-4">
                      <span className={`text-xs font-semibold uppercase ${severityColor(f.severity).split(" ")[0]}`}>
                        {f.severity}
                      </span>
                      <p className="font-medium text-slate-900">{f.title}</p>
                      <p className="text-sm text-slate-600">{f.description}</p>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>

          <div className="space-y-6">
            {cf.open_questions.length > 0 && (
              <section className="card p-5">
                <h3 className="text-sm font-semibold text-slate-900">
                  Open questions
                </h3>
                <ul className="mt-3 list-disc space-y-2 pl-4 text-sm text-slate-600">
                  {cf.open_questions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              </section>
            )}

            <section className="card p-5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <Clock className="h-4 w-4" />
                Audit trail ({audit.length})
              </h3>
              <ol className="mt-4 max-h-96 space-y-3 overflow-y-auto text-xs">
                {audit.map((e) => (
                  <li key={e.event_id} className="border-l-2 border-slate-200 pl-3">
                    <p className="font-medium text-slate-800">{e.action}</p>
                    <p className="text-slate-500">
                      {e.actor} · {formatDate(e.timestamp)}
                    </p>
                  </li>
                ))}
              </ol>
            </section>

            {data.completed_at && (
              <div className="flex items-center gap-2 text-sm text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                Completed {formatDate(data.completed_at)}
              </div>
            )}
          </div>
        </div>
      )}

      {!cf && !processing && data?.status === "completed" && (
        <p className="text-slate-500">No case file payload returned.</p>
      )}
    </div>
  );
}

function cleanSummary(raw: string): string {
  if (raw.startsWith("{")) {
    try {
      const j = JSON.parse(raw);
      if (typeof j === "object" && j !== null) {
        const text =
          (j as Record<string, unknown>)["Executive Summary"] ||
          (j as Record<string, unknown>)["text"] ||
          (j as Record<string, unknown>)["summary"];
        if (typeof text === "string") return text;
        if (typeof text === "object") return JSON.stringify(text, null, 2);
      }
    } catch {
      /* use raw */
    }
  }
  return raw;
}
