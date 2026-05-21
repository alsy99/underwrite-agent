import { Link, Outlet, useLocation } from "react-router-dom";
import {
  FileSearch,
  LayoutDashboard,
  LogOut,
  PlusCircle,
  Shield,
} from "lucide-react";
import { clearAuth, isAuthRequired } from "../lib/auth";
import { SetupBanner } from "./SetupBanner";

const nav = [
  { to: "/", label: "Cases", icon: LayoutDashboard },
  { to: "/new", label: "New investigation", icon: PlusCircle },
];

export function Layout() {
  const { pathname } = useLocation();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 flex-col border-r border-surface-border bg-brand-900 text-white">
        <div className="border-b border-white/10 px-6 py-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <p className="font-display text-lg font-semibold leading-tight">
                Underwrite Agent
              </p>
              <p className="text-xs text-slate-400">Fraud investigation</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {nav.map(({ to, label, icon: Icon }) => {
            const active = pathname === to || (to !== "/" && pathname.startsWith(to));
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  active
                    ? "bg-white/10 text-white"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-white/10 px-6 py-4 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <FileSearch className="h-3.5 w-3.5" />
            Agentic underwriting MVP
          </div>
          {isAuthRequired() && (
            <button
              type="button"
              onClick={() => {
                clearAuth();
                window.location.reload();
              }}
              className="mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-slate-400 transition hover:bg-white/5 hover:text-white"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign out
            </button>
          )}
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <SetupBanner />
        <Outlet />
      </main>
    </div>
  );
}
