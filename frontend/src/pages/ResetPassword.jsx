import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { supabase, supabaseEnabled } from "../lib/supabase.js";

import { useSeo } from "../lib/seo.js";
const label = { fontSize: 11, fontWeight: 600, letterSpacing: 1, color: "var(--app-muted)" };
// 16px minimum — anything smaller makes iOS Safari zoom the page on focus.
const inputStyle = { padding: "14px 16px", fontSize: 16, color: "var(--app-text)", background: "var(--app-panel)", width: "100%", boxSizing: "border-box" };

export default function ResetPassword() {
  useSeo({
    title: "Reset your password — BanterClips",
    description: "Choose a new password for your BanterClips account.",
    // Explicit path: this route arrives carrying a recovery token in the URL,
    // which must never end up in a canonical tag.
    path: "/reset-password",
    noindex: true,
  });

  const nav = useNavigate();
  const { updatePassword, signedIn } = useApp();
  const [phase, setPhase] = useState("checking"); // checking | form | done | invalid
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // The email link opens this page with a recovery session in the URL;
  // supabase-js picks it up. Without any session, the link is invalid/expired.
  useEffect(() => {
    if (!supabaseEnabled) {
      setPhase("invalid");
      return;
    }
    let alive = true;
    const check = async () => {
      const { data } = await supabase.auth.getSession();
      if (alive && data.session) setPhase("form");
    };
    check();
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      if (alive && session && (event === "PASSWORD_RECOVERY" || event === "SIGNED_IN")) setPhase("form");
    });
    const timer = setTimeout(() => {
      if (alive) setPhase((p) => (p === "checking" ? "invalid" : p));
    }, 4000);
    return () => {
      alive = false;
      sub.subscription.unsubscribe();
      clearTimeout(timer);
    };
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (password !== confirm) return setError("Passwords don't match.");
    setBusy(true);
    setError("");
    try {
      await updatePassword(password);
      setPhase("done");
    } catch (err) {
      setError(err.message || "Could not update the password. Try again.");
    }
    setBusy(false);
  };

  return (
    <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "grid", placeItems: "center", padding: "clamp(14px, 4vw, 24px)" }}>
      <div className="card auth-card" style={{ width: "100%", maxWidth: 430, padding: "40px 36px", display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <svg width="32" height="32" viewBox="0 0 34 34">
            <defs>
              <linearGradient id="rplg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#22d3ee" />
                <stop offset="1" stopColor="#34e27a" />
              </linearGradient>
            </defs>
            <rect width="34" height="34" rx="9" fill="url(#rplg)" />
            <path d="M13 10.5 L25 17 L13 23.5 Z" fill="#06121A" />
          </svg>
          <span style={{ fontWeight: 700, fontSize: 20, color: "var(--app-text)" }}>BanterClips</span>
        </div>

        {phase === "checking" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, padding: "18px 0" }}>
            <span style={{ width: 28, height: 28, borderRadius: "50%", border: "3px solid #12303d", borderTopColor: "#22d3ee", animation: "spin 1s linear infinite" }} />
            <span style={{ fontSize: 14, color: "var(--app-muted)" }}>Checking your reset link…</span>
          </div>
        )}

        {phase === "invalid" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ fontWeight: 700, fontSize: 22, color: "var(--app-text)" }}>Link expired or invalid</div>
            <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.55 }}>
              Password reset links work once and expire quickly. Request a fresh one from the sign-in page.
            </div>
            <button className="grad-btn" style={{ padding: 13, fontSize: 15 }} onClick={() => nav("/signin")}>
              Back to sign in
            </button>
          </div>
        )}

        {phase === "form" && (
          <>
            <div>
              <div style={{ fontWeight: 700, fontSize: 24, color: "var(--app-text)", marginBottom: 8 }}>Choose a new password</div>
              <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.5 }}>
                From now on you can sign in with this password (Google sign-in keeps working too).
              </div>
            </div>
            <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <label style={label}>NEW PASSWORD</label>
                <div style={{ position: "relative" }}>
                  <input
                    autoFocus
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    className="panel"
                    style={{ ...inputStyle, paddingRight: 48 }}
                  />
                  <button
                    type="button"
                    aria-label={showPw ? "Hide password" : "Show password"}
                    onClick={() => setShowPw((v) => !v)}
                    style={{ position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", padding: 8, color: "var(--app-muted)" }}
                  >
                    {showPw ? "🙈" : "👁"}
                  </button>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <label style={label}>CONFIRM PASSWORD</label>
                <input
                  type={showPw ? "text" : "password"}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Same password again"
                  className="panel"
                  style={inputStyle}
                />
              </div>
              {error && (
                <div style={{ fontSize: 13, color: "var(--app-error)", background: "rgba(240,84,108,.1)", borderRadius: 10, padding: "10px 14px" }}>
                  {error}
                </div>
              )}
              <button type="submit" className="grad-btn" style={{ padding: 14, fontSize: 16, opacity: busy ? 0.7 : 1 }} disabled={busy}>
                {busy ? "Saving…" : "Set new password"}
              </button>
            </form>
          </>
        )}

        {phase === "done" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, textAlign: "center", padding: "8px 0" }}>
            <div style={{ width: 60, height: 60, borderRadius: 18, background: "rgba(52,226,122,.14)", display: "grid", placeItems: "center" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#34e27a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="m8 12.5 2.6 2.6L16 9.5" />
              </svg>
            </div>
            <div style={{ fontWeight: 700, fontSize: 22, color: "var(--app-text)" }}>Password updated</div>
            <div style={{ fontSize: 14, color: "var(--app-muted)" }}>You're signed in and ready to go.</div>
            <button className="grad-btn" style={{ padding: "13px 26px", fontSize: 15 }} onClick={() => nav(signedIn ? "/studio" : "/signin")}>
              {signedIn ? "Enter studio →" : "Back to sign in"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
