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
  { to: "/", label: "Cases", icon: LayoutDashboard, shortLabel: "Cases" },
  { to: "/new", label: "New investigation", icon: PlusCircle, shortLabel: "New" },
];

function NavLink({
  to,
  label,
  icon: Icon,
  active,
  compact,
}: {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  active: boolean;
  compact?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`flex items-center gap-3 rounded-lg font-medium transition ${
        compact ? "flex-1 flex-col gap-1 px-2 py-2 text-[11px]" : "px-3 py-2.5 text-sm"
      } ${
        active
          ? compact
            ? "text-brand-600"
            : "bg-white/10 text-white"
          : compact
            ? "text-slate-500"
            : "text-slate-300 hover:bg-white/5 hover:text-white"
      }`}
    >
      <Icon className={compact ? "h-5 w-5" : "h-4 w-4"} />
      <span className={compact ? "text-center leading-tight" : ""}>{label}</span>
    </Link>
  );
}

export function Layout() {
  const { pathname } = useLocation();

  const isActive = (to: string) =>
    pathname === to || (to !== "/" && pathname.startsWith(to));

  return (
    <div className="flex min-h-screen min-h-[100dvh] flex-col lg:flex-row">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-surface-border bg-brand-900 text-white lg:flex">
        <div className="border-b border-white/10 px-6 py-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-500">
              <Shield className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="font-display text-lg font-semibold leading-tight">
                Underwrite Agent
              </p>
              <p className="text-xs text-slate-400">Fraud investigation</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {nav.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              label={label}
              icon={icon}
              active={isActive(to)}
            />
          ))}
        </nav>
        <SidebarFooter />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex shrink-0 items-center gap-3 border-b border-brand-800 bg-brand-900 px-4 py-3 text-white lg:hidden">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500">
          <Shield className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-base font-semibold leading-tight">
            Underwrite Agent
          </p>
          <p className="truncate text-xs text-slate-400">Fraud investigation</p>
        </div>
      </header>

      <main className="min-w-0 flex-1 overflow-x-hidden pb-[calc(4.5rem+env(safe-area-inset-bottom,0px))] lg:pb-0">
        <SetupBanner />
        <Outlet />
      </main>

      {/* Mobile bottom navigation */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-30 flex border-t border-surface-border bg-white px-2 pt-1 shadow-[0_-4px_20px_rgba(15,23,42,0.08)] lg:hidden"
        style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
        aria-label="Main navigation"
      >
        {nav.map(({ to, shortLabel, icon }) => (
          <NavLink
            key={to}
            to={to}
            label={shortLabel}
            icon={icon}
            active={isActive(to)}
            compact
          />
        ))}
      </nav>
    </div>
  );
}

function SidebarFooter() {
  return (
    <div className="border-t border-white/10 px-6 py-4 text-xs text-slate-400">
      <div className="flex items-center gap-2">
        <FileSearch className="h-3.5 w-3.5 shrink-0" />
        <span>Agentic underwriting MVP</span>
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
  );
}
