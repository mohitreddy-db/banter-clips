import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { T } from "./ui.jsx";

/**
 * Admin console shell — grouped sidebar per ADMIN.md §2 / Figma frames 15–23.
 * Own layout (not AppShell): the console has its own IA, and mixing the two
 * sidebars would be noise. Server-side every /admin API 404s for non-admins;
 * this guard is just the polite client-side mirror of that.
 */

const GROUPS = [
  { label: "OVERVIEW", items: [{ to: "/admin", end: true, label: "Dashboard" }] },
  { label: "GROWTH", items: [{ to: "/admin/users", label: "Users" }] },
  { label: "CONTENT", items: [{ to: "/admin/videos", label: "All Videos" }] },
  {
    label: "AI ENGINE",
    items: [
      { to: "/admin/jobs", label: "Generation Jobs" },
      { to: "/admin/costs", label: "AI Costs & Quality" },
    ],
  },
  {
    label: "MONETIZATION",
    items: [
      { to: "/admin/revenue", label: "Revenue" },
      { to: "/admin/credits", label: "Credits" },
    ],
  },
  { label: "SOCIAL", items: [{ to: "/admin/publishing", label: "Publishing" }] },
  {
    label: "SYSTEM",
    items: [
      { to: "/admin/catalog", label: "Catalog" },
      { to: "/admin/admins", label: "Admins" },
      { to: "/admin/audit", label: "Audit Log" },
    ],
  },
];

const navStyle = ({ isActive }) => ({
  display: "block", padding: "7px 12px", borderRadius: 8, fontSize: 13.5,
  fontWeight: isActive ? 600 : 500, textDecoration: "none",
  color: isActive ? T.cyan : T.muted,
  background: isActive ? "var(--app-surface)" : "transparent",
});

export default function AdminShell() {
  const { booted, user, signedIn, apiDown } = useApp();
  const location = useLocation();

  if (!booted) return null;
  if (!signedIn) return <Navigate to={apiDown ? "/" : "/signin"} replace />;
  if (!user?.is_admin) return <Navigate to="/studio" replace />;

  return (
    <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "flex" }}>
      <aside
        className="admin-console-sidebar"
        style={{
          width: 232, flexShrink: 0, position: "sticky", top: 0, height: "100vh",
          overflowY: "auto", background: "var(--app-sidebar)",
          borderRight: `1px solid ${T.border}`, padding: 16, boxSizing: "border-box",
        }}
      >
        <NavLink to="/studio" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none", marginBottom: 4 }}>
          {/* Same mark as the app sidebar (AppShell) — play glyph on the gradient. */}
          <svg width="28" height="28" viewBox="0 0 34 34" style={{ flexShrink: 0 }}>
            <defs>
              <linearGradient id="adminlg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#22d3ee" />
                <stop offset="1" stopColor="#34e27a" />
              </linearGradient>
            </defs>
            <rect width="34" height="34" rx="9" fill="url(#adminlg)" />
            <path d="M13 10.5 L25 17 L13 23.5 Z" fill="#06121A" />
          </svg>
          <span>
            <span style={{ display: "block", fontSize: 16, fontWeight: 700, color: T.text, lineHeight: 1.1 }}>BanterClips</span>
            <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: ".12em", color: T.cyan }}>ADMIN CONSOLE</span>
          </span>
        </NavLink>

        {GROUPS.map((g) => (
          <div key={g.label} style={{ marginTop: 18 }}>
            <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".1em", color: T.muted2, padding: "0 12px", marginBottom: 6 }}>
              {g.label}
            </div>
            {g.items.map((it) => (
              <NavLink key={it.to} to={it.to} end={it.end} style={navStyle}>
                {it.label}
              </NavLink>
            ))}
          </div>
        ))}

        <div style={{ marginTop: 28, paddingTop: 14, borderTop: `1px solid ${T.border}`, display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ width: 28, height: 28, borderRadius: "50%", background: T.purple, display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700, color: "#fff" }}>
            {(user.email || "?")[0].toUpperCase()}
          </span>
          <span style={{ minWidth: 0 }}>
            <span style={{ display: "block", fontSize: 12, fontWeight: 600, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 140 }}>
              {user.email}
            </span>
            <span style={{ fontSize: 10, color: T.muted2 }}>Operator</span>
          </span>
        </div>
      </aside>

      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <header
          style={{
            position: "sticky", top: 0, zIndex: 40, display: "flex", alignItems: "center", gap: 12,
            padding: "14px 24px", background: "rgba(11,15,28,.9)", backdropFilter: "blur(8px)",
            borderBottom: `1px solid ${T.border}`,
          }}
        >
          {/* Mobile nav — visibility is CSS-only (index.css): hidden ≥860px,
              a scrollable strip below. No inline display so the media query
              always wins. */}
          <nav className="admin-console-mobilenav" style={{ gap: 6, overflowX: "auto", flex: 1, minWidth: 0, WebkitOverflowScrolling: "touch" }}>
            {GROUPS.flatMap((g) => g.items).map((it) => (
              <NavLink key={it.to} to={it.to} end={it.end} style={(s) => ({ ...navStyle(s), whiteSpace: "nowrap", flexShrink: 0 })}>
                {it.label}
              </NavLink>
            ))}
          </nav>
          <span className="admin-console-live" style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: T.muted, border: `1px solid ${T.border}`, borderRadius: 999, padding: "6px 14px", background: "var(--app-surface)" }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: T.green }} />
            live · 60s cache
          </span>
          <NavLink to="/studio" className="ghost-btn admin-console-backlink" style={{ padding: "7px 14px", fontSize: 12, textDecoration: "none", whiteSpace: "nowrap", flexShrink: 0 }}>
            ← Back to app
          </NavLink>
        </header>
        <main key={location.pathname} style={{ padding: "clamp(16px, 3vw, 28px)", display: "flex", flexDirection: "column", gap: 20, maxWidth: 1280, width: "100%", margin: "0 auto", boxSizing: "border-box" }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
