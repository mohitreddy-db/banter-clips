import { useEffect, useState } from "react";
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
  const { supabaseEnabled, signedIn, user: sessionUser, signUp, signInPassword, signInWithGoogle, sendMagicLink, resetPassword, devSignIn } = useApp();
  const [mode, setMode] = useState("signin"); // signin | signup
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(null); // { title, body }

  const after = (user) => nav(user?.preferences?.onboarding_completed ? "/studio" : "/onboarding");

  // Covers redirect logins (Google OAuth / magic-link return): the session is
  // exchanged by AppContext, we just move on once it lands.
  useEffect(() => {
    if (signedIn) after(sessionUser);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signedIn]);

  const google = async () => {
    setBusy(true);
    setError("");
    try {
      await signInWithGoogle(); // full-page redirect — nothing runs after this on success
    } catch (err) {
      setError(err.message || "Google sign-in failed.");
      setBusy(false);
    }
  };

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
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <label style={label}>PASSWORD</label>
                    {mode === "signin" && (
                      <button
                        type="button"
                        onClick={async () => {
                          if (!email.includes("@")) return setError("Enter your email above first, then tap Forgot password.");
                          setBusy(true);
                          setError("");
                          try {
                            await resetPassword(email.trim());
                            setNotice({
                              title: "Reset link sent",
                              body: `Check ${email.trim()} for a link to set a new password. It also works for accounts created with Google.`,
                            });
                          } catch (err) {
                            setError(err.message || "Could not send the reset email.");
                          }
                          setBusy(false);
                        }}
                        style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--app-cyan)", fontSize: 12, fontWeight: 600, cursor: "pointer", padding: 0 }}
                      >
                        Forgot password?
                      </button>
                    )}
                  </div>
                  <div style={{ position: "relative" }}>
                    <input
                      type={showPw ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
                      className="panel"
                      style={{ ...input, width: "100%", boxSizing: "border-box", paddingRight: 48 }}
                    />
                    <button
                      type="button"
                      aria-label={showPw ? "Hide password" : "Show password"}
                      onClick={() => setShowPw((v) => !v)}
                      style={{ position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", padding: 8, color: "var(--app-muted)", display: "grid", placeItems: "center" }}
                    >
                      {showPw ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.5 10.5 0 0 1 12 20c-7 0-10-8-10-8a17.9 17.9 0 0 1 4.06-5.17" />
                          <path d="M9.9 4.24A9.7 9.7 0 0 1 12 4c7 0 10 8 10 8a18 18 0 0 1-2.24 3.35" />
                          <path d="M14.12 14.12A3 3 0 1 1 9.88 9.88" />
                          <path d="m2 2 20 20" />
                        </svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M2 12s3-8 10-8 10 8 10 8-3 8-10 8-10-8-10-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      )}
                    </button>
                  </div>
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

            {supabaseEnabled && (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "-4px 0" }}>
                  <div style={{ flex: 1, height: 1, background: "var(--app-border)" }} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: "var(--app-muted2)", letterSpacing: ".08em" }}>OR</span>
                  <div style={{ flex: 1, height: 1, background: "var(--app-border)" }} />
                </div>
                <button
                  type="button"
                  onClick={google}
                  disabled={busy}
                  className="ghost-btn"
                  style={{ padding: "13px", fontSize: 15, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, color: "var(--app-text)" }}
                >
                  <svg width="18" height="18" viewBox="0 0 48 48">
                    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
                    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
                    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
                    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
                  </svg>
                  Continue with Google
                </button>
              </>
            )}

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
