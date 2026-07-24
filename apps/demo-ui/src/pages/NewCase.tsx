import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileUp, Loader2, Sparkles } from "lucide-react";
import { createCase, uploadPolicySba } from "../api";
import { formatVertical } from "../lib/format";
import type { LoanVertical } from "../types";

const PRESETS: Record<
  string,
  { label: string; vertical: LoanVertical; metadata: Record<string, string>; hint: string }
> = {
  fraud: {
    label: "SBA — Fraudulent (demo)",
    vertical: "sba_7a",
    metadata: {
      business_name: "Acme Consulting LLC",
      employer: "Acme Consulting LLC",
      address: "1200 Market Street Suite 400 Wilmington DE",
      stated_employer: "Acme Consulting LLC",
    },
    hint: "Upload files from data/fixtures/sba/fraudulent/",
  },
  clean: {
    label: "SBA — Clean (happy path)",
    vertical: "sba_7a",
    metadata: {
      business_name: "Sunrise Bakery LLC",
      employer: "Sunrise Bakery LLC",
      address: "88 Main Street Portland OR",
      stated_employer: "Sunrise Bakery LLC",
    },
    hint: "Upload files from data/fixtures/sba/clean/",
  },
  cre: {
    label: "CRE — Fraudulent (demo)",
    vertical: "cre_acquisition",
    metadata: {
      business_name: "Oak Plaza Holdings LLC",
      address: "200 Oak Street Dallas TX",
    },
    hint: "Upload files from data/fixtures/cre/fraudulent/",
  },
  bank_stmt: {
    label: "Bank Statement — Fraudulent (demo)",
    vertical: "specialty_mortgage_bank_statement",
    metadata: {
      business_name: "Apex Design Studio LLC",
      employer: "Apex Design Studio LLC",
      stated_employer: "Apex Design Studio LLC",
      address: "410 Commerce Blvd Suite 12 Austin TX",
    },
    hint: "Upload files from data/fixtures/specialty_mortgage/fraudulent/",
  },
};

export function NewCase() {
  const navigate = useNavigate();
  const [preset, setPreset] = useState("fraud");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seedPolicy, setSeedPolicy] = useState(true);

  const p = PRESETS[preset];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) {
      setError("Select at least one document");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (seedPolicy) {
        try {
          await uploadPolicySba();
        } catch {
          /* policy may already exist */
        }
      }
      const res = await createCase(p.vertical, p.metadata, files);
      navigate(`/cases/${res.case_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create case");
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-6 sm:px-6 sm:py-8">
      <header className="mb-6 sm:mb-8">
        <h1 className="font-display text-xl font-semibold text-slate-900 sm:text-2xl">
          New investigation
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload loan documents — Sherlock agent builds an auditable case file
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card p-4 sm:p-6">
          <label className="text-sm font-medium text-slate-700">Demo package</label>
          <div className="mt-3 grid gap-2">
            {Object.entries(PRESETS).map(([key, val]) => (
              <label
                key={key}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-3 transition sm:items-center sm:px-4 ${
                  preset === key
                    ? "border-brand-500 bg-brand-50"
                    : "border-surface-border hover:border-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="preset"
                  checked={preset === key}
                  onChange={() => setPreset(key)}
                  className="text-brand-600"
                />
                <div>
                  <p className="text-sm font-medium text-slate-900">{val.label}</p>
                  <p className="text-xs text-slate-500">{formatVertical(val.vertical)}</p>
                </div>
              </label>
            ))}
          </div>
          <p className="mt-3 flex items-center gap-2 text-xs text-slate-500">
            <Sparkles className="h-3.5 w-3.5" />
            {p.hint}
          </p>
        </div>

        <div className="card p-4 sm:p-6">
          <label className="text-sm font-medium text-slate-700">Documents</label>
          <div className="mt-3 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 px-4 py-8 sm:px-6 sm:py-10">
            <FileUp className="h-8 w-8 text-slate-400" />
            <p className="mt-2 text-sm text-slate-600">PDF or text files</p>
            <input
              type="file"
              multiple
              accept=".pdf,.txt,.md"
              className="mt-4 w-full max-w-full text-sm file:mr-2 file:rounded file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-brand-700"
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
            />
            {files.length > 0 && (
              <ul className="mt-3 w-full text-left text-xs text-slate-600">
                {files.map((f) => (
                  <li key={f.name} className="truncate">
                    {f.name}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={seedPolicy}
            onChange={(e) => setSeedPolicy(e.target.checked)}
            className="rounded border-slate-300"
          />
          Seed SBA policy document (for policy RAG)
        </label>

        {error && (
          <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>
        )}

        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Starting investigation…
            </>
          ) : (
            "Run investigation"
          )}
        </button>
      </form>
    </div>
  );
}
