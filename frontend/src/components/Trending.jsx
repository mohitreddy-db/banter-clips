import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";

/**
 * Trending on the create page: real topics from today's internet for the
 * selected sport, each expandable into ready-to-shoot takes.
 *
 * The server keeps one shared 20-minute cache per sport; this component adds
 * a session cache on top so switching sports back and forth never refetches
 * or flashes the loading state within that window.
 */

const CLIENT_TTL_MS = 20 * 60 * 1000;
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

const cacheKey = (sport) => `bc-trending-${sport}`;

function readCache(sport) {
  try {
    const raw = sessionStorage.getItem(cacheKey(sport));
    if (!raw) return null;
    const { data, at } = JSON.parse(raw);
    return Date.now() - at < CLIENT_TTL_MS ? data : null;
  } catch {
    return null;
  }
}

function writeCache(sport, data) {
  try {
    sessionStorage.setItem(cacheKey(sport), JSON.stringify({ data, at: Date.now() }));
  } catch { /* storage full/blocked — server cache still saves us */ }
}

function agoLabel(iso) {
  if (!iso) return "";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return mins < 1 ? "updated just now" : `updated ${mins}m ago`;
}

/** Rotating status line while the feed builds — one line, cross-faded. */
function ScanStatus() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % SCAN_LINES.length), 1700);
    return () => clearInterval(t);
  }, []);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9, minHeight: 20 }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--app-cyan)", animation: "pulseGlow 1.2s ease-in-out infinite", flexShrink: 0 }} />
      <span key={i} style={{ fontSize: 12.5, color: "var(--app-muted)", animation: "fadeUp .45s ease both" }}>
        {SCAN_LINES[i]}
      </span>
    </div>
  );
}

export default function Trending({ sport, onUse }) {
  const [feed, setFeed] = useState(() => readCache(sport));
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(-1);
  const seq = useRef(0);

  useEffect(() => {
    setOpen(-1);
    // Bump the sequence on EVERY sport change — including into the cached
    // branch — so an in-flight fetch for the previous sport can never write
    // its results (or its spinner) over the sport now on screen.
    const mySeq = ++seq.current;
    const cached = readCache(sport);
    if (cached) {
      setFeed(cached);
      setFailed(false);
      setLoading(false);
      return;
    }
    setFeed(null);
    setFailed(false);
    setLoading(true);
    api
      .trending(sport)
      .then((data) => {
        writeCache(sport, data); // valid for its own sport even if stale for the UI
        if (seq.current !== mySeq) return; // sport changed mid-flight
        setFeed(data);
      })
      .catch(() => seq.current === mySeq && setFailed(true))
      .finally(() => seq.current === mySeq && setLoading(false));
  }, [sport]);

  const topics = feed?.topics || [];
  // Nothing to show and nothing coming: hide the whole section quietly
  // (research off, or the internet was unreachable). The page works as before.
  if (!loading && !topics.length) return null;
  if (failed && !topics.length) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>
          🔥 TRENDING IN {String(sport).toUpperCase()}
        </span>
        <span style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>
          change sport below to see what's trending there
        </span>
        {!loading && feed?.fetched_at && (
          <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--app-muted2)" }}>
            {agoLabel(feed.fetched_at)}
          </span>
        )}
      </div>

      {loading && (
        <div style={{ display: "grid", gap: 8 }}>
          <ScanStatus />
          {[0, 1, 2].map((i) => (
            <div key={i} className="shimmer"
                 style={{ height: 52, borderRadius: 12, border: "1px solid var(--app-border)", animationDelay: `${i * 0.12}s` }} />
          ))}
        </div>
      )}

      {!loading && topics.length > 0 && (
        <div style={{ display: "grid", gap: 8 }}>
          {topics.map((t, i) => {
            const heat = HEAT[t.heat] || HEAT.hot;
            const expanded = open === i;
            return (
              <div key={i} className="panel"
                   style={{ borderRadius: 12, border: `1px solid ${expanded ? "var(--app-cyan)" : "var(--app-border)"}`, overflow: "hidden", animation: "stepIn .35s cubic-bezier(.2,.8,.2,1) both", animationDelay: `${i * 0.05}s`, transition: "border-color .15s" }}>
                <button
                  type="button"
                  onClick={() => setOpen(expanded ? -1 : i)}
                  style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", padding: "11px 13px", background: "none", border: "none", cursor: "pointer", textAlign: "left" }}
                >
                  <span style={{ fontSize: 9.5, fontWeight: 800, letterSpacing: ".06em", padding: "3px 8px", borderRadius: 999, flexShrink: 0, color: heat.color, border: `1px solid ${heat.color}`, opacity: 0.9 }}>
                    {heat.icon} {heat.label}
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: "block", fontSize: 14, fontWeight: 700, color: "var(--app-text)", lineHeight: 1.3 }}>
                      {t.title}
                    </span>
                    {t.why_now && (
                      <span style={{ display: "block", fontSize: 11.5, color: "var(--app-muted2)", marginTop: 2 }}>
                        {t.why_now}
                      </span>
                    )}
                  </span>
                  <span style={{ color: "var(--app-muted2)", fontSize: 12, flexShrink: 0, transform: expanded ? "rotate(180deg)" : "none", transition: "transform .2s" }}>
                    ▾
                  </span>
                </button>

                {expanded && (
                  <div style={{ padding: "0 13px 12px", display: "grid", gap: 8, animation: "fadeUp .25s ease both" }}>
                    {t.summary && (
                      <div style={{ fontSize: 12.5, color: "var(--app-muted)", lineHeight: 1.5 }}>{t.summary}</div>
                    )}
                    {(t.prompts || []).map((p, j) => (
                      <button
                        key={j}
                        type="button"
                        onClick={() => onUse(p)}
                        style={{ display: "flex", flexDirection: "column", gap: 5, padding: "11px 13px", borderRadius: 10, cursor: "pointer", textAlign: "left", background: "rgba(34,211,238,.05)", border: "1px solid var(--app-border)", animation: "fadeUp .3s ease both", animationDelay: `${j * 0.06}s` }}
                      >
                        <span style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                          <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.6, textTransform: "uppercase", color: "var(--app-cyan)" }}>
                            ✨ {p.angle || "Take this angle"}
                          </span>
                          <span style={{ fontSize: 10.5, color: "var(--app-muted2)" }}>
                            {p.tone} · {p.seconds}s
                          </span>
                          <span style={{ marginLeft: "auto", fontSize: 11.5, fontWeight: 700, color: "var(--app-cyan)" }}>
                            Use →
                          </span>
                        </span>
                        <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--app-text)", lineHeight: 1.45 }}>
                          “{p.take}”
                        </span>
                      </button>
                    ))}
                    {!(t.prompts || []).length && (
                      <div style={{ fontSize: 12, color: "var(--app-muted2)", fontStyle: "italic" }}>
                        Write your own take on this one — it's hot right now.
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
