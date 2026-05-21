import { useState, type FormEvent } from "react";
import { Lock, Shield } from "lucide-react";
import { isAuthRequired, isAuthenticated, login } from "../lib/auth";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState(isAuthenticated);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isAuthRequired() || authed) {
    return <>{children}</>;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const ok = await login(password);
      if (ok) {
        setAuthed(true);
      } else {
        setError("Incorrect password");
        setPassword("");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-900 via-brand-800 to-slate-900 px-4">
      <div className="card w-full max-w-md p-8 shadow-xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Shield className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-display text-xl font-semibold text-slate-900">
              Underwrite Agent
            </h1>
            <p className="text-sm text-slate-500">Private demo — sign in to continue</p>
          </div>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
              Password
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-surface-border py-2.5 pl-10 pr-3 text-sm outline-none ring-brand-500 focus:ring-2"
                placeholder="Enter demo password"
                required
              />
            </div>
          </div>
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Checking…" : "Continue"}
          </button>
        </form>
        <p className="mt-6 text-center text-xs text-slate-400">
          API access is also protected with a separate key on the server.
        </p>
      </div>
    </div>
  );
}
