import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import AppShell from "../components/AppShell.jsx";
import { useSeo } from "../lib/seo.js";

/**
 * Public feedback — no sign-in needed. Signed-in visitors get the same form
 * inside the app chrome (AppShell children mode, like Pricing); signed-out
 * and still-booting visitors get a plain public layout immediately.
 */

const CATEGORIES = [
  { key: "bug", icon: "🐛", label: "Something's broken" },
  { key: "idea", icon: "💡", label: "An idea" },
  { key: "praise", icon: "🎉", label: "Loved something" },
  { key: "other", icon: "💬", label: "Other" },
];

function Logo({ size = 26 }) {
  return (
    <div style={{ width: size, height: size, borderRadius: size * 0.3, background: "linear-gradient(135deg,#22d3ee,#34e27a)", display: "grid", placeItems: "center", flexShrink: 0 }}>
      <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24" fill="#04121a"><path d="M8 5v14l11-7z" /></svg>
    </div>
  );
}

function FeedbackForm({ signedIn, userEmail }) {
  const { search } = useLocation();
  const [category, setCategory] = useState("idea");
  const [message, setMessage] = useState("");
  const [rating, setRating] = useState(0);
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState(""); // honeypot — stays empty for humans
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const from = new URLSearchParams(search).get("from") || "";
  const valid = message.trim().length >= 5 && message.length <= 2000;

  const send = async () => {
    setBusy(true);
    setError("");
    try {
      await api.sendFeedback({
        message: message.trim(), category, rating: rating || null,
        email: signedIn ? null : email.trim() || null,
        page: from || (typeof window !== "undefined" ? window.location.pathname : ""),
        website,
      });
      setDone(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="card" style={{ padding: "34px 28px", textAlign: "center", display: "flex", flexDirection: "column", gap: 10, alignItems: "center" }}>
        <div style={{ fontSize: 34 }}>🙌</div>
        <div style={{ fontSize: 19, fontWeight: 800, color: "var(--app-text)" }}>Thanks — we read every one.</div>
        <div style={{ fontSize: 14, color: "var(--app-muted)", maxWidth: 420, lineHeight: 1.55 }}>
          Your note went straight to the team. {signedIn ? "If it needs a reply, we'll use your account email." : email ? "We'll reply to the email you left if it needs one." : ""}
        </div>
        <button className="ghost-btn" style={{ padding: "11px 18px", fontSize: 14, marginTop: 8 }} onClick={() => { setDone(false); setMessage(""); setRating(0); }}>
          Leave another note
        </button>
      </div>
    );
  }

  const input = { width: "100%", boxSizing: "border-box", padding: "12px 14px", fontSize: 14.5, color: "var(--app-text)", background: "var(--app-surface)", border: "1.5px solid var(--app-border)", borderRadius: 12 };

  return (
    <div className="card" style={{ padding: "clamp(18px, 4vw, 26px)", display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>WHAT IS THIS ABOUT?</span>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
          {CATEGORIES.map((c) => {
            const on = category === c.key;
            return (
              <button
                key={c.key}
                type="button"
                onClick={() => setCategory(c.key)}
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 12px", borderRadius: 12, cursor: "pointer", textAlign: "left", background: on ? "rgba(34,211,238,.08)" : "var(--app-surface)", border: `1.5px solid ${on ? "var(--app-cyan)" : "var(--app-border)"}`, color: on ? "var(--app-cyan)" : "var(--app-text)", fontWeight: 700, fontSize: 13.5 }}
              >
                <span style={{ fontSize: 18 }}>{c.icon}</span> {c.label}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>TELL US MORE</span>
        <div style={{ position: "relative" }}>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value.slice(0, 2000))}
            rows={5}
            placeholder={category === "bug" ? "What happened, and what did you expect? The page you were on helps." : "Be as specific as you like — we read every word."}
            style={{ ...input, resize: "vertical", lineHeight: 1.5 }}
          />
          <span style={{ position: "absolute", right: 12, bottom: 10, fontSize: 11.5, color: "var(--app-muted2)" }}>{message.length} / 2000</span>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>HOW'S BANTERCLIPS SO FAR? <span style={{ fontWeight: 500, letterSpacing: 0, textTransform: "none" }}>optional</span></span>
        <div style={{ display: "flex", gap: 6 }}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button key={n} type="button" onClick={() => setRating(n === rating ? 0 : n)} aria-label={`${n} star`} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 26, padding: 2, filter: n <= rating ? "none" : "grayscale(1) opacity(.45)", transition: "filter .15s" }}>
              ⭐
            </button>
          ))}
        </div>
      </div>

      {!signedIn && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>EMAIL <span style={{ fontWeight: 500, letterSpacing: 0 }}>optional · only if you want a reply</span></span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" style={input} inputMode="email" />
        </div>
      )}
      {signedIn && (
        <div style={{ fontSize: 12.5, color: "var(--app-muted2)" }}>Sent from your account ({userEmail}) — we'll reply there if needed.</div>
      )}

      {/* Honeypot: hidden from people, irresistible to bots. */}
      <input value={website} onChange={(e) => setWebsite(e.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true" style={{ position: "absolute", left: -9999, width: 1, height: 1, opacity: 0 }} placeholder="website" />

      {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}
      <button className="grad-btn" style={{ padding: 15, fontSize: 16, borderRadius: 14 }} disabled={!valid || busy} onClick={send}>
        {busy ? "Sending…" : "Send feedback"}
      </button>
    </div>
  );
}

export default function Feedback() {
  useSeo({
    title: "Feedback — BanterClips",
    description: "Tell the BanterClips team what's working, what's broken, and what you want next.",
    path: "/feedback",
  });
  const { booted, signedIn, user } = useApp();
  const nav = useNavigate();

  useEffect(() => {
    api.track("feedback_viewed");
  }, []);

  const heading = (
    <div style={{ textAlign: "center" }}>
      <h1 style={{ fontSize: "clamp(24px, 6vw, 30px)", fontWeight: 800, color: "var(--app-text)", margin: "0 0 8px" }}>Tell us what you think</h1>
      <div style={{ fontSize: 15, color: "var(--app-muted)", maxWidth: 520, margin: "0 auto", lineHeight: 1.55 }}>
        Bugs, ideas, a video that came out wrong, a feature you wish existed — every note lands in front of the team.
      </div>
    </div>
  );

  if (booted && signedIn) {
    return (
      <AppShell>
        <div style={{ maxWidth: 680, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24, paddingTop: 8 }}>
          {heading}
          <FeedbackForm signedIn userEmail={user?.email} />
        </div>
      </AppShell>
    );
  }

  return (
    <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "flex", flexDirection: "column" }}>
      <div style={{ borderBottom: "1px solid var(--app-border)", padding: "14px clamp(18px, 4vw, 28px)", display: "flex", alignItems: "center", gap: 12 }}>
        <div onClick={() => nav("/")} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
          <Logo />
          <span style={{ fontWeight: 700, fontSize: 17, color: "var(--app-text)" }}>BanterClips</span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
          <span onClick={() => nav("/signin")} style={{ cursor: "pointer", fontSize: 14, fontWeight: 600, color: "var(--app-muted)" }}>Sign in</span>
          <button className="grad-btn" style={{ padding: "10px 18px", fontSize: 13.5 }} onClick={() => nav("/signin")}>
            Start Creating Free
          </button>
        </div>
      </div>
      <div style={{ maxWidth: 680, width: "100%", margin: "0 auto", display: "flex", flexDirection: "column", gap: 24, padding: "clamp(28px, 6vw, 48px) clamp(18px, 4vw, 28px) 64px", boxSizing: "border-box" }}>
        {heading}
        <FeedbackForm signedIn={false} />
      </div>
    </div>
  );
}
