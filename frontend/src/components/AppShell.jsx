import { Outlet, NavLink, Navigate, useNavigate, useLocation } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";

const TITLES = { "/studio": "Create Studio", "/clips": "My Clips", "/account": "Account", "/pricing": "Plans & Pricing" };

function Icon({ d, size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {d}
    </svg>
  );
}

const icons = {
  create: <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />,
  catalog: (
    <>
      <circle cx="9" cy="7" r="3" />
      <path d="M3 19c0-3 2.5-5 6-5s6 2 6 5" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M15.5 14.2c3-.4 5.5 1.3 5.5 4.3" />
    </>
  ),
  clips: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M7 5v14M17 5v14M3 9h4M3 15h4M17 9h4M17 15h4" />
    </>
  ),
  account: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
    </>
  ),
  pricing: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v10M15 9.5c0-1.4-1.3-2.5-3-2.5s-3 1-3 2.2c0 3.2 6 1.6 6 4.6 0 1.2-1.3 2.2-3 2.2s-3-1.1-3-2.5" />
    </>
  ),
  remix: (
    <>
      <path d="M12 2 2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </>
  ),
  analytics: (
    <>
      <path d="M3 3v18h18" />
      <path d="M8 17V9M13 17V5M18 17v-7" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </>
  ),
};

// Usually a layout route (renders <Outlet />). Pages that live OUTSIDE the
// gated route group but still want the app chrome when a session exists —
// today just /pricing, which must stay public for SEO — pass content as
// `children` instead.
export default function AppShell({ children }) {
  const nav = useNavigate();
  const loc = useLocation();
  const { plan, left, limit, booted, signedIn, apiDown, user } = useApp();

  // App pages require a session (BR-02). Wait for boot, then gate.
  if (!booted) {
    return (
      <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "grid", placeItems: "center" }}>
        <span style={{ width: 30, height: 30, borderRadius: "50%", border: "3px solid #12303d", borderTopColor: "#22d3ee", animation: "spin 1s linear infinite" }} />
      </div>
    );
  }
  if (!signedIn) return <Navigate to={apiDown ? "/" : "/signin"} replace />;

  const navItem = ({ isActive }) => ({
    display: "flex", alignItems: "center", gap: 12, padding: "11px 12px", borderRadius: 10,
    fontSize: 15, fontWeight: isActive ? 600 : 500, cursor: "pointer",
    color: isActive ? "var(--app-cyan)" : "var(--app-muted)",
    background: isActive ? "var(--app-surface)" : "transparent",
    textDecoration: "none", transition: "all .15s",
  });

  return (
    <div className="app-font app-shell" style={{ display: "grid", gridTemplateColumns: "240px 1fr", minHeight: "100vh", background: "var(--app-bg)" }}>
      {/* sidebar */}
      <aside className="app-sidebar" style={{ background: "var(--app-sidebar)", borderRight: "1px solid var(--app-border)", padding: "24px 16px", display: "flex", flexDirection: "column", gap: 6, position: "sticky", top: 0, height: "100vh" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 8px 16px", cursor: "pointer" }} onClick={() => nav("/")}>
          <svg width="28" height="28" viewBox="0 0 34 34">
            <defs>
              <linearGradient id="sblg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#22d3ee" />
                <stop offset="1" stopColor="#34e27a" />
              </linearGradient>
            </defs>
            <rect width="34" height="34" rx="9" fill="url(#sblg)" />
            <path d="M13 10.5 L25 17 L13 23.5 Z" fill="#06121A" />
          </svg>
          <span style={{ fontWeight: 700, fontSize: 18, color: "var(--app-text)" }}>BanterClips</span>
        </div>

        <button className="grad-btn" style={{ padding: "13px", fontSize: 15, marginBottom: 12 }} onClick={() => nav("/studio")}>
          + New Video
        </button>

        <NavLink to="/studio" style={navItem}>
          <Icon d={icons.create} /> Create
        </NavLink>
        <NavLink to="/clips" style={navItem}>
          <Icon d={icons.clips} /> My Clips
        </NavLink>
        <NavLink to="/pricing" style={navItem}>
          <Icon d={icons.pricing} /> Pricing
        </NavLink>
        <NavLink to="/account" style={navItem}>
          <Icon d={icons.account} /> Account
        </NavLink>
        {user?.is_admin && (
          <NavLink to="/admin" style={navItem}>
            <Icon d={icons.catalog} /> Admin
          </NavLink>
        )}

        <div style={{ borderTop: "1px solid var(--app-border)", margin: "14px 0 10px" }} />
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1.2, color: "var(--app-muted2)", padding: "0 12px 4px" }}>COMING SOON</div>
        {[
          ["Remix Library", icons.remix],
          ["Analytics", icons.analytics],
        ].map(([label, ic]) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 12px", fontSize: 15, fontWeight: 500, color: "var(--app-muted2)" }}>
            <Icon d={ic} /> {label}
            <span style={{ marginLeft: "auto" }}>
              <Icon d={icons.lock} size={14} />
            </span>
          </div>
        ))}

        <div style={{ marginTop: "auto", padding: "12px", borderRadius: 12, background: "var(--app-panel)", border: "1px solid var(--app-border)" }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--app-muted)", marginBottom: 6 }}>
            {plan === "creator" ? "CREATOR PLAN" : "FREE PLAN"}
          </div>
          <div style={{ height: 6, borderRadius: 99, background: "#0b0f1c", overflow: "hidden", marginBottom: 6 }}>
            <div style={{ height: "100%", width: `${((limit - left) / limit) * 100}%`, background: "var(--app-grad)" }} />
          </div>
          <div style={{ fontSize: 11.5, color: "var(--app-muted)" }}>{left} of {limit} videos left</div>
        </div>
      </aside>

      {/* main */}
      <div className="app-main" style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header className="app-topbar" style={{ display: "flex", alignItems: "center", gap: 16, padding: "16px 32px", position: "sticky", top: 0, zIndex: 30, background: "rgba(11,15,28,.8)", backdropFilter: "blur(12px)" }}>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--app-text)", margin: 0 }}>{TITLES[loc.pathname] || "BanterClips"}</h1>
          <div style={{ flex: 1 }} />
          {plan !== "creator" && (
            <button className="grad-btn" style={{ padding: "8px 16px", borderRadius: 999, fontSize: 13 }} onClick={() => nav("/pricing")}>
              Upgrade
            </button>
          )}
          <div className="usage-pill" style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 16px", borderRadius: 999, background: "var(--app-surface)", border: "1px solid var(--app-border)", flexShrink: 0 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: left > 0 ? "var(--app-green)" : "var(--app-error)" }} />
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--app-text)", whiteSpace: "nowrap" }}>
              <span className="usage-long">{left} of {limit} videos left</span>
              <span className="usage-short">{left}/{limit}</span>
            </span>
          </div>
          <div style={{ width: 36, height: 36, borderRadius: "50%", background: "linear-gradient(140deg,#7b2ff7,#f0546c)", cursor: "pointer", flexShrink: 0 }} onClick={() => nav("/account")} />
        </header>
        <main className="app-content" style={{ padding: "16px 32px 40px", flex: 1, minWidth: 0 }}>
          {children ?? <Outlet />}
        </main>
      </div>

      {/* mobile bottom tab bar — the sidebar is hidden under 860px, and
          navigation must not disappear with it */}
      <nav className="app-bottomnav app-font">
        {[
          ["/studio", "Create", icons.create],
          ["/clips", "My Clips", icons.clips],
          ["/pricing", "Pricing", icons.pricing],
          ["/account", "Account", icons.account],
        ].map(([to, label, ic]) => (
          <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : undefined)}>
            <Icon d={ic} size={20} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
