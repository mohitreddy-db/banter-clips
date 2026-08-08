import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";

function Logo() {
  return (
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
  );
}

const label = { fontSize: 11, fontWeight: 600, letterSpacing: 1, color: "var(--app-muted)" };
const input = { padding: "14px 16px", fontSize: 15, color: "var(--app-text)", background: "var(--app-panel)" };

export default function SignIn() {
  const nav = useNavigate();
  const { supabaseEnabled, signUp, signInPassword, sendMagicLink, devSignIn } = useApp();
  const [mode, setMode] = useState("signin"); // signin | signup
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(null); // { title, body }

  const after = (user) => nav(user?.preferences?.onboarding_completed ? "/studio" : "/onboarding");

  const submit = async (e) => {
    e.preventDefault();
    if (!email.includes("@")) return setError("Enter a valid email address.");
    setBusy(true);
    setError("");
    try {
      if (!supabaseEnabled) {
        // Local dev without Supabase keys — instant dev magic link.
        after(await devSignIn(email.trim()));
      } else if (mode === "signup") {
        if (password.length < 8) throw new Error("Password must be at least 8 characters.");
        const res = await signUp(email.trim(), password, name.trim());
        if (res.needsConfirmation) {
          setNotice({
            title: "Confirm your email",
            body: `We sent a confirmation link to ${email.trim()}. Click it, then come back and sign in.`,
          });
        } else {
          after(res.user);
        }
      } else {
        after(await signInPassword(email.trim(), password));
      }
    } catch (err) {
      setError(err.message || "Something went wrong. Try again.");
    }
    setBusy(false);
  };

  const magic = async () => {
    if (!email.includes("@")) return setError("Enter your email first, then use the magic link.");
    setBusy(true);
    setError("");
    try {
      await sendMagicLink(email.trim());
      setNotice({
        title: "Check your inbox",
        body: `We emailed a one-time sign-in link to ${email.trim()}. Open it on this device.`,
      });
    } catch (err) {
      setError(err.message || "Could not send the link. Try again.");
    }
    setBusy(false);
  };

  return (
    <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "grid", placeItems: "center", padding: 24 }}>
      <div className="card" style={{ width: "100%", maxWidth: 430, padding: "40px 36px", display: "flex", flexDirection: "column", gap: 20 }}>
        {notice ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, textAlign: "center", padding: "12px 0" }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "rgba(52,226,122,.14)", display: "grid", placeItems: "center" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#34e27a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <path d="m3 7 9 6 9-6" />
              </svg>
            </div>
            <div style={{ fontWeight: 700, fontSize: 24, color: "var(--app-text)" }}>{notice.title}</div>
            <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.55 }}>{notice.body}</div>
            <button className="ghost-btn" style={{ padding: "11px 20px", fontSize: 14 }} onClick={() => { setNotice(null); setMode("signin"); }}>
              ← Back to sign in
            </button>
          </div>
        ) : (
          <>
            <Logo />
            <div>
              <div style={{ fontWeight: 700, fontSize: 24, color: "var(--app-text)", marginBottom: 8 }}>
                {mode === "signup" ? "Create your account" : "Sign in to BanterClips"}
              </div>
              <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.5 }}>
                {supabaseEnabled
                  ? mode === "signup"
                    ? "Free to start — publish your first clip in minutes."
                    : "Welcome back. Your takes missed you."
                  : "Dev mode — instant sign-in with any email."}
              </div>
            </div>

            {/* mode switch */}
            {supabaseEnabled && (
              <div style={{ display: "flex", background: "var(--app-panel)", borderRadius: 12, padding: 4 }}>
                {[["signin", "Sign in"], ["signup", "Create account"]].map(([m, t]) => (
                  <button
                    key={m}
                    onClick={() => { setMode(m); setError(""); }}
                    style={{
                      flex: 1, padding: "10px 0", borderRadius: 9, border: "none", cursor: "pointer",
                      fontSize: 14, fontWeight: 600, transition: "all .15s",
                      background: mode === m ? "var(--app-surface)" : "transparent",
                      color: mode === m ? "var(--app-text)" : "var(--app-muted)",
                      boxShadow: mode === m ? "0 1px 6px rgba(0,0,0,.35)" : "none",
                    }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            )}

            <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {supabaseEnabled && mode === "signup" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <label style={label}>NAME</label>
                  <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Jordan Hoops" className="panel" style={input} />
                </div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <label style={label}>EMAIL</label>
                <input autoFocus type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@team.com" className="panel" style={input} />
              </div>
              {supabaseEnabled && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <label style={label}>PASSWORD</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
                    className="panel"
                    style={input}
                  />
                </div>
              )}
              {error && (
                <div style={{ fontSize: 13, color: "var(--app-error)", background: "rgba(240,84,108,.1)", borderRadius: 10, padding: "10px 14px" }}>
                  {error}
                </div>
              )}
              <button type="submit" className="grad-btn" style={{ padding: "14px", fontSize: 16, opacity: busy ? 0.7 : 1 }} disabled={busy}>
                {busy ? "One sec…" : !supabaseEnabled ? "Continue" : mode === "signup" ? "Create account" : "Sign in"}
              </button>
            </form>

            {supabaseEnabled && mode === "signin" && (
              <button onClick={magic} disabled={busy} style={{ background: "none", border: "none", color: "var(--app-cyan)", fontSize: 13.5, fontWeight: 600, cursor: "pointer" }}>
                Email me a magic link instead
              </button>
            )}

            <div style={{ fontSize: 12, color: "var(--app-muted)", textAlign: "center", lineHeight: 1.5 }}>
              By continuing you agree to the beta Terms and AI-content policy.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
