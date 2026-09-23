import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import { SPORT_KEYS, sportIcon } from "../lib/sports.js";
import { agoLabel, useTrendingFeed } from "../lib/trending.js";
import { useSeo } from "../lib/seo.js";

/**
 * 🔥 Viral — what fans are arguing about RIGHT NOW, one tap from a video.
 *
 * The fastest path to a first video for someone who doesn't know how to
 * prompt: every trending story carries five fixed angles (roast, predict,
 * who's better, biggest threat, controversial). Tapping one drops its
 * ready-written take, tone and length into the Studio, where the script
 * still gets approved before anything renders.
 */

const HEAT = {
  viral: { icon: "🔥", label: "VIRAL", color: "#f97316" },
  hot: { icon: "⚡", label: "HOT", color: "var(--app-cyan)" },
  rising: { icon: "📈", label: "RISING", color: "#34e27a" },
};
const SCAN_LINES = [
  "Scanning today's internet…",
  "Reading fan chatter on socials…",
  "Ranking what's blowing up…",
  "Writing angles you can shoot…",
];

function ScanStatus() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % SCAN_LINES.length), 1700);
    return () => clearInterval(t);
  }, []);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9, minHeight: 20 }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--app-cyan)", animation: "pulseGlow 1.2s ease-in-out infinite", flexShrink: 0 }} />
      <span key={i} style={{ fontSize: 12.5, color: "var(--app-muted)", animation: "fadeUp .45s ease both" }}>{SCAN_LINES[i]}</span>
    </div>
  );
}

export default function Viral() {
  useSeo({
    title: "Viral — BanterClips",
    description: "What sports fans are arguing about right now, one tap from a video.",
    path: "/viral",
    noindex: true,
  });
  const nav = useNavigate();
  const { profile } = useApp();
  const followed = useMemo(() => (profile?.sports || []).filter((s) => SPORT_KEYS.includes(s)), [profile?.sports]);
  // The user's own sports lead the row; everything else follows.
  const order = useMemo(() => [...followed, ...SPORT_KEYS.filter((s) => !followed.includes(s))], [followed]);
  const [sport, setSport] = useState(() => followed[0] || "Soccer");
  const { feed, loading, refreshing, failed, refresh } = useTrendingFeed(sport);
  const topics = feed?.topics || [];
  // The server rebuilds on demand at most once every few minutes per sport;
  // until then the button shows the wait instead of pretending to refresh.
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const waitSecs = (() => {
    if (!feed?.fetched_at || !feed?.refresh_after) return 0;
    const elapsed = (now - new Date(feed.fetched_at).getTime()) / 1000;
    return Math.max(0, Math.ceil(feed.refresh_after - elapsed));
  })();

  useEffect(() => {
    api.track("viral_viewed", { sport });
  }, [sport]);

  // One tap → the take, tone and length land in the Studio, prefilled.
  const use = (topic, p, kind) => {
    api.track("viral_preset_used", { sport, kind, tone: p.tone, seconds: p.seconds });
    const q = new URLSearchParams({ prompt: p.take, tone: p.tone, seconds: String(p.seconds), sport });
    nav(`/studio?${q.toString()}`);
  };

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>
      <div>
        <h1 style={{ fontSize: "clamp(22px, 6vw, 28px)", fontWeight: 800, color: "var(--app-text)", margin: "0 0 6px" }}>🔥 What's viral right now</h1>
        <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.5 }}>
          Real stories from the last 48 hours. Tap an angle — the take is written for you, you approve the script, we make the video.
        </div>
      </div>

      {/* sport row — horizontally scrollable on phones, never wraps into a wall */}
      <div className="viral-sports">
        {order.map((s) => {
          const on = s === sport;
          return (
            <button key={s} type="button" className={`chip${on ? " on" : ""}`} onClick={() => setSport(s)} style={{ padding: "9px 14px", fontSize: 13.5 }}>
              {sportIcon(s)} {s}
            </button>
          );
        })}
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>🔥 TRENDING NOW · {String(sport).toUpperCase()}</span>
        <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 10 }}>
          {!loading && feed?.fetched_at && <span style={{ fontSize: 11, color: "var(--app-muted2)" }}>{agoLabel(feed.fetched_at)}</span>}
          <button
            type="button"
            onClick={() => { api.track("viral_refreshed", { sport }); refresh(); }}
            disabled={loading || refreshing || waitSecs > 0}
            title={waitSecs > 0 ? `Fresh — try again in ${waitSecs}s` : "Rebuild this sport's feed from today's internet"}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "7px 12px", minHeight: 34, borderRadius: 999, fontSize: 12.5, fontWeight: 700, cursor: waitSecs > 0 || refreshing ? "default" : "pointer", color: waitSecs > 0 ? "var(--app-muted2)" : "var(--app-cyan)", background: "var(--app-surface)", border: `1px solid ${waitSecs > 0 ? "var(--app-border)" : "rgba(34,211,238,.45)"}` }}
          >
            <span style={{ display: "inline-block", animation: refreshing ? "spin 1s linear infinite" : "none" }}>↻</span>
            {refreshing ? "Refreshing…" : waitSecs > 0 ? `Fresh · ${waitSecs}s` : "Refresh"}
          </button>
        </span>
      </div>

      {loading && (
        <div style={{ display: "grid", gap: 10 }}>
          <ScanStatus />
          {[0, 1, 2].map((i) => (
            <div key={i} className="shimmer" style={{ height: 150, borderRadius: 16, border: "1px solid var(--app-border)", animationDelay: `${i * 0.12}s` }} />
          ))}
        </div>
      )}

      {!loading && !topics.length && (
        <div className="card" style={{ padding: "28px 22px", textAlign: "center", display: "flex", flexDirection: "column", gap: 10, alignItems: "center" }}>
          <div style={{ fontSize: 30 }}>📡</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--app-text)" }}>
            {failed ? "Couldn't reach the internet just now" : `Nothing viral in ${sport} yet`}
          </div>
          <div style={{ fontSize: 13, color: "var(--app-muted)", maxWidth: 380, lineHeight: 1.5 }}>
            Try another sport above, or write your own take — the Studio still writes the script for you.
          </div>
          <button className="ghost-btn" style={{ padding: "10px 16px", fontSize: 13.5 }} onClick={() => nav("/studio")}>Write my own take →</button>
        </div>
      )}

      {!loading && topics.map((t, i) => {
        const heat = HEAT[t.heat] || HEAT.hot;
        const presets = t.presets || [];
        const ready = t.prompts || [];
        return (
          <div key={i} className="card" style={{ padding: "clamp(14px, 3.5vw, 20px)", display: "flex", flexDirection: "column", gap: 12, animation: "stepIn .35s cubic-bezier(.2,.8,.2,1) both", animationDelay: `${i * 0.05}s` }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
              <span style={{ fontSize: 9.5, fontWeight: 800, letterSpacing: ".06em", padding: "4px 8px", borderRadius: 999, flexShrink: 0, color: heat.color, border: `1px solid ${heat.color}`, marginTop: 2 }}>
                {heat.icon} {heat.label}
              </span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: "clamp(16px, 4.5vw, 19px)", fontWeight: 800, color: "var(--app-text)", lineHeight: 1.25 }}>{t.title}</div>
                {t.why_now && <div style={{ fontSize: 12.5, color: "var(--app-muted)", marginTop: 4, lineHeight: 1.45 }}>{t.why_now}</div>}
                {t.summary && <div style={{ fontSize: 12.5, color: "var(--app-muted2)", marginTop: 4, lineHeight: 1.45 }}>{t.summary}</div>}
              </div>
            </div>

            {presets.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "var(--app-muted2)" }}>CREATE · ONE TAP</div>
                <div className="viral-presets">
                  {presets.map((p) => (
                    <button
                      key={p.key}
                      type="button"
                      onClick={() => use(t, p, p.key)}
                      title={p.take}
                      style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4, padding: "12px 13px", minHeight: 56, borderRadius: 12, cursor: "pointer", textAlign: "left", background: "rgba(34,211,238,.06)", border: "1px solid var(--app-border)", color: "var(--app-text)" }}
                    >
                      <span style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.25 }}>{p.icon} {p.label}</span>
                      <span style={{ fontSize: 11, color: "var(--app-muted2)" }}>{p.tone} · {p.seconds}s</span>
                    </button>
                  ))}
                </div>
              </>
            )}

            {ready.length > 0 && (
              <details>
                <summary style={{ cursor: "pointer", fontSize: 12.5, fontWeight: 700, color: "var(--app-cyan)", listStyle: "none" }}>✨ Or use a ready-written take ▾</summary>
                <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                  {ready.map((p, j) => (
                    <button key={j} type="button" onClick={() => use(t, p, "ready")} style={{ display: "flex", flexDirection: "column", gap: 5, padding: "11px 13px", borderRadius: 10, cursor: "pointer", textAlign: "left", background: "var(--app-surface)", border: "1px solid var(--app-border)" }}>
                      <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.6, textTransform: "uppercase", color: "var(--app-cyan)" }}>{p.angle || "Take this angle"} · <span style={{ color: "var(--app-muted2)", textTransform: "none", letterSpacing: 0 }}>{p.tone} · {p.seconds}s</span></span>
                      <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--app-text)", lineHeight: 1.45 }}>“{p.take}”</span>
                    </button>
                  ))}
                </div>
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}
