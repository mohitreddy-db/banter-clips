import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";

export default function SignIn() {
  const nav = useNavigate();
  const { signIn } = useApp();
  const [email, setEmail] = useState("");
  const [state, setState] = useState("form"); // form | sending | error
  const [error, setError] = useState("");

  const send = async (e) => {
    e.preventDefault();
    if (!email.includes("@")) return;
    setState("sending");
    setError("");
    try {
      // Small pause so the "check your inbox" moment reads naturally.
      const [user] = await Promise.all([
        signIn(email.trim()),
        new Promise((r) => setTimeout(r, 1200)),
      ]);
      nav(user?.preferences?.onboarding_completed ? "/studio" : "/onboarding");
    } catch (err) {
      setError(err.message || "Sign-in failed. Try again.");
      setState("error");
    }
  };

  return (
    <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "grid", placeItems: "center", padding: 24 }}>
      <div className="card" style={{ width: "100%", maxWidth: 420, padding: "40px 36px", display: "flex", flexDirection: "column", gap: 20 }}>
        {state !== "sending" ? (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <svg width="32" height="32" viewBox="0 0 34 34">
                <defs>
                  <linearGradient id="silg" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stopColor="#22d3ee" />
                    <stop offset="1" stopColor="#34e27a" />
                  </linearGradient>
                </defs>
                <rect width="34" height="34" rx="9" fill="url(#silg)" />
                <path d="M13 10.5 L25 17 L13 23.5 Z" fill="#06121A" />
              </svg>
              <span style={{ fontWeight: 700, fontSize: 20, color: "var(--app-text)" }}>BanterClips</span>
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 24, color: "var(--app-text)", marginBottom: 8 }}>Sign in to BanterClips</div>
              <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.5 }}>
                We’ll email you a one-time magic link. No passwords to remember.
              </div>
            </div>
            <form onSubmit={send} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <label style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1, color: "var(--app-muted)" }}>EMAIL</label>
                <input
                  autoFocus
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@team.com"
                  className="panel"
                  style={{ padding: "14px 16px", fontSize: 15, color: "var(--app-text)", background: "var(--app-panel)" }}
                />
              </div>
              {error && (
                <div style={{ fontSize: 13, color: "var(--app-error)", background: "rgba(240,84,108,.1)", borderRadius: 10, padding: "10px 14px" }}>
                  {error}
                </div>
              )}
              <button type="submit" className="grad-btn" style={{ padding: "14px", fontSize: 16 }}>
                Send magic link
              </button>
            </form>
            <div style={{ fontSize: 12, color: "var(--app-muted)", textAlign: "center", lineHeight: 1.5 }}>
              By continuing you agree to the beta Terms and AI-content policy.
            </div>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, textAlign: "center", padding: "12px 0" }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "rgba(52,226,122,.14)", display: "grid", placeItems: "center" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#34e27a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <path d="m3 7 9 6 9-6" />
              </svg>
            </div>
            <div style={{ fontWeight: 700, fontSize: 24, color: "var(--app-text)" }}>Check your inbox</div>
            <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.5 }}>
              We sent a sign-in link to <b style={{ color: "var(--app-text)" }}>{email}</b>.<br />
              Signing you in… <span style={{ fontSize: 12 }}>(beta: the link opens automatically)</span>
            </div>
            <div style={{ width: 28, height: 28, borderRadius: "50%", border: "3px solid #12303d", borderTopColor: "#22d3ee", animation: "spin 1s linear infinite" }} />
          </div>
        )}
      </div>
    </div>
  );
}
