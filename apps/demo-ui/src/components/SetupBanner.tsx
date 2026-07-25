import { AlertCircle } from "lucide-react";

const apiUrl = import.meta.env.VITE_API_URL?.trim() || "";
const apiKey = import.meta.env.VITE_API_KEY?.trim() || "";

/** Local Vite uses empty VITE_API_URL + /api proxy. Static Pages needs absolute URL. */
export function isBackendConfigured(): boolean {
  if (import.meta.env.DEV) return true;
  return Boolean(apiUrl && apiKey);
}

export function SetupBanner() {
  if (isBackendConfigured()) return null;

  return (
    <div className="mx-4 mt-4 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:mx-6 lg:mx-8">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="font-medium">Backend not connected</p>
        <p className="mt-1 text-amber-800">
          Add GitHub Actions secrets <code className="rounded bg-amber-100 px-1">VITE_API_URL</code>{" "}
          (ngrok URL) and <code className="rounded bg-amber-100 px-1">VITE_API_KEY</code>, then
          re-run the deploy workflow. See{" "}
          <a
            href="https://github.com/alsy99/underwrite-agent/blob/main/docs/INTERNET_DEPLOY.md"
            className="underline"
            target="_blank"
            rel="noreferrer"
          >
            INTERNET_DEPLOY.md
          </a>
          .
        </p>
      </div>
    </div>
  );
}
