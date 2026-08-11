import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api, downloadClip } from "../lib/api.js";
import { UpgradeModal, PublishModal } from "../components/Modals.jsx";

const SPORTS = ["NBA", "NFL", "Soccer", "MLB"];
const TONES = [
  { key: "Funny", icon: "😄", sub: "Playful roast" },
  { key: "Savage", icon: "🔪", sub: "No mercy" },
  { key: "Hype", icon: "📣", sub: "Full energy" },
  { key: "Bold", icon: "💪", sub: "Fearless claim" },
];
// Free tops out at 15s; longer runs are a Creator feature (server-enforced too).
const DURATIONS = [10, 15, 30];
const FREE_MAX_DURATION = 15;
const STAGE_LABELS = {
  queued: "Queued",
  planning_story: "Planning story",
  creating_voice: "Creating voice",
  designing_characters: "Designing characters",
  generating_scenes: "Generating scene images",
  animating_scenes: "Animating scenes",
  assembling_video: "Assembling video",
  validating: "Validating",
};
const STAGES = Object.values(STAGE_LABELS).slice(1); // the 7 real stages

const EXAMPLES_BY_SPORT = {
  NBA: ["Messi is still the GOAT.", "Lakers won't make the playoffs.", "Knicks are contenders."],
  NFL: ["Chiefs dynasty is over.", "Defense wins championships — still.", "Your QB is a system QB."],
  Soccer: ["Messi is still the GOAT.", "VAR ruined the derby.", "The Prem is overrated."],
  MLB: ["Yankees are cooked this season.", "Small ball is dead.", "The shift ban changed nothing."],
};

export default function Studio() {
  const nav = useNavigate();
  const { profile, left, limit, plan, refreshClips, refreshUsage, clips, canDownload, watermarked } = useApp();
  const [phase, setPhase] = useState("input"); // input | generating | result | failed
  const [take, setTake] = useState("");
  const [sport, setSport] = useState(SPORTS.includes(profile.sports?.[0]) ? profile.sports[0] : "NBA");
  const [tone, setTone] = useState("Funny");
  const [duration, setDuration] = useState(15);
  const [clip, setClip] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const pollRef = useRef(null);
  const tickRef = useRef(null);

  const stopTimers = useCallback(() => {
    clearInterval(pollRef.current);
    clearInterval(tickRef.current);
  }, []);
  useEffect(() => stopTimers, [stopTimers]);

  const valid = take.trim().length >= 10 && take.length <= 280;

  const watchClip = useCallback(
    (id) => {
      setPhase("generating");
      setElapsed(0);
      clearInterval(tickRef.current);
      tickRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
      clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const c = await api.getClip(id);
          setClip(c);
          if (c.status === "ready") {
            stopTimers();
            setPhase("result");
            refreshClips();
            refreshUsage();
          } else if (c.status === "failed") {
            stopTimers();
            setPhase("failed");
            refreshClips();
          }
        } catch {
          /* transient poll error — keep trying */
        }
      }, 900);
    },
    [refreshClips, refreshUsage, stopTimers]
  );

  const generate = async () => {
    if (!valid) return;
    setError("");
    try {
      const c = await api.createClip(take.trim(), sport, tone, duration);
      setClip(c);
      refreshClips(); // the new in-flight clip shows up in My Clips immediately
      watchClip(c.id);
    } catch (e) {
      if (e.code === "limit_reached" || e.code === "upgrade_required") setUpgradeOpen(true);
      else setError(e.message);
    }
  };

  const retry = async () => {
    try {
      const c = await api.retryClip(clip.id);
      setClip(c);
      watchClip(c.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const download = async () => {
    try {
      await downloadClip(clip);
    } catch (e) {
      if (e.code === "upgrade_required" || e.status === 403) setUpgradeOpen(true);
      else setError(e.message);
    }
  };

  const reset = () => {
    stopTimers();
    setPhase("input");
    setTake("");
    setClip(null);
    setError("");
  };

  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const stageIdx = clip ? clip.stage_index : 0;
  const examples = EXAMPLES_BY_SPORT[sport] || EXAMPLES_BY_SPORT.NBA;

  return (
    <div style={{ maxWidth: 780, margin: "0 auto", display: "flex", flexDirection: "column", gap: 22 }}>
      {phase === "input" && (
        <>
          {/* hero */}
          <div style={{ textAlign: "center", paddingTop: 18 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "7px 16px", borderRadius: 999, background: "rgba(34,211,238,.1)", border: "1px solid rgba(34,211,238,.35)", color: "var(--app-cyan)", fontSize: 12, fontWeight: 700, letterSpacing: ".08em" }}>
              ⚡ NEW CLIP
            </span>
            <h1 style={{ fontSize: 42, fontWeight: 800, color: "var(--app-text)", margin: "18px 0 10px" }}>What’s your sports take?</h1>
            <div style={{ fontSize: 16, color: "var(--app-muted)" }}>One sentence. We’ll do the hook, voice, captions and video.</div>
          </div>

          {/* take input */}
          <div style={{ position: "relative" }}>
            <textarea
              value={take}
              onChange={(e) => setTake(e.target.value)}
              placeholder="Messi is still the GOAT."
              rows={4}
              className="panel"
              style={{ width: "100%", padding: "22px 24px", fontSize: 19, fontWeight: 500, color: "var(--app-text)", resize: "vertical", background: "var(--app-surface)", border: "1.5px solid var(--app-border)", borderRadius: 20, lineHeight: 1.45, boxSizing: "border-box" }}
            />
            <span style={{ position: "absolute", right: 16, bottom: 14, fontSize: 12, color: take.length > 280 ? "var(--app-error)" : "var(--app-muted2)" }}>
              {take.length} / 280
            </span>
          </div>

          {/* examples */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontSize: 13, color: "var(--app-muted)" }}>Try:</span>
            {examples.map((ex) => (
              <button key={ex} className="chip" style={{ fontSize: 13 }} onClick={() => setTake(ex)}>
                {ex}
              </button>
            ))}
          </div>

          {/* sport */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>SPORT</span>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {SPORTS.map((s) => (
                <button key={s} className={`chip${sport === s ? " on" : ""}`} onClick={() => setSport(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* tone cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>TONE</span>
            <div className="tone-cards" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 14 }}>
              {TONES.map((t) => {
                const on = tone === t.key;
                return (
                  <button
                    key={t.key}
                    onClick={() => setTone(t.key)}
                    style={{
                      display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                      padding: "20px 10px 16px", borderRadius: 16, cursor: "pointer",
                      background: on ? "rgba(34,211,238,.08)" : "var(--app-surface)",
                      border: `1.5px solid ${on ? "var(--app-cyan)" : "var(--app-border)"}`,
                      transition: "all .15s",
                    }}
                  >
                    <span style={{ fontSize: 26 }}>{t.icon}</span>
                    <span style={{ fontWeight: 700, fontSize: 15, color: on ? "var(--app-cyan)" : "var(--app-text)" }}>{t.key}</span>
                    <span style={{ fontSize: 11.5, color: "var(--app-muted)" }}>{t.sub}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* duration */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>LENGTH</span>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {DURATIONS.map((d) => {
                const locked = d > FREE_MAX_DURATION && plan !== "creator";
                const on = duration === d;
                return (
                  <button
                    key={d}
                    className={`chip${on ? " on" : ""}`}
                    style={locked ? { color: "var(--app-muted2)", borderStyle: "dashed", display: "inline-flex", alignItems: "center", gap: 6 } : undefined}
                    title={locked ? "Videos longer than 15 seconds are a Creator feature" : undefined}
                    onClick={() => (locked ? setUpgradeOpen(true) : setDuration(d))}
                  >
                    {d}s
                    {locked && (
                      <span style={{ fontSize: 8, fontWeight: 800, letterSpacing: ".05em", padding: "2px 6px", borderRadius: 999, background: "rgba(34,211,238,.12)", color: "var(--app-cyan)" }}>
                        CREATOR
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* credits bar */}
          <div className="panel" style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 18px", borderRadius: 14 }}>
            <span style={{ color: "var(--app-cyan)" }}>⚡</span>
            <span style={{ fontSize: 13.5, color: "var(--app-muted)" }}>
              <b style={{ color: "var(--app-text)" }}>{left}</b> of <b style={{ color: "var(--app-text)" }}>{limit}</b> monthly videos left · each clip uses 1 · failures are free
            </span>
            <div style={{ flex: 1 }} />
            {plan !== "creator" && (
              <button onClick={() => nav("/pricing")} style={{ background: "none", border: "none", color: "var(--app-cyan)", fontWeight: 700, fontSize: 13.5, cursor: "pointer" }}>
                + Get more with Creator
              </button>
            )}
          </div>

          {error && (
            <div style={{ fontSize: 13.5, color: "var(--app-error)", background: "rgba(240,84,108,.1)", borderRadius: 12, padding: "12px 16px" }}>
              {error}
            </div>
          )}

          {/* generate */}
          <button className="grad-btn" style={{ padding: 18, fontSize: 17, borderRadius: 16 }} disabled={!valid} onClick={generate}>
            🪄 Generate BanterClip
          </button>
          <div style={{ fontSize: 12.5, color: "var(--app-muted2)", textAlign: "center", marginTop: -8 }}>
            Hot Take format · three cinematic scenes · 12–15s vertical MP4 · 1080 × 1920 · AI-parody labeled
          </div>

          {/* recent clips strip */}
          {clips.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingTop: 10 }}>
              <div style={{ display: "flex", alignItems: "center" }}>
                <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>RECENT CLIPS</span>
                <button onClick={() => nav("/clips")} style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--app-cyan)", fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}>
                  View all →
                </button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(170px,1fr))", gap: 12 }}>
                {clips.slice(0, 4).map((c) => (
                  <div key={c.id} className="card" style={{ display: "flex", alignItems: "center", gap: 10, padding: 10, borderRadius: 12, cursor: "pointer" }} onClick={() => nav("/clips")}>
                    <div style={{ width: 34, height: 58, borderRadius: 7, background: c.thumb_gradient || "linear-gradient(160deg,#22d3ee,#3d2c8d)", flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, fontWeight: 500, color: "var(--app-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.take}</div>
                      <div style={{ fontSize: 10.5, color: c.status === "failed" ? "var(--app-error)" : "var(--app-muted)", marginTop: 3 }}>
                        {c.sport} · {c.tone}{c.status === "ready" && c.publishes?.some((p) => p.status === "published") ? " · published" : c.status !== "ready" ? ` · ${c.status}` : ""}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {(phase === "generating" || phase === "failed") && clip && (
        <>
          <div className="panel" style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderRadius: 14, marginTop: 12 }}>
            <span style={{ fontSize: 15, fontWeight: 600, color: "var(--app-text)" }}>“{clip.take}”</span>
            <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--app-muted)", flexShrink: 0 }}>{clip.sport} · {clip.tone} · Hot Take</span>
          </div>

          {phase === "generating" && (
            <>
              <div className="card" style={{ padding: "26px 28px" }}>
                <div style={{ display: "flex", alignItems: "center", paddingBottom: 18 }}>
                  <span style={{ fontSize: 20, fontWeight: 600, color: "var(--app-text)" }}>Generating your video…</span>
                  <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--app-muted)" }}>{fmt(elapsed)} elapsed</span>
                </div>
                {STAGES.map((s, i) => {
                  const state =
                    clip.status === "queued" ? "pending" : i < stageIdx ? "done" : i === stageIdx ? "active" : "pending";
                  return (
                    <div key={s} style={{ display: "flex", alignItems: "center", gap: 14, padding: "9px 0" }}>
                      {state === "done" ? (
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                          <circle cx="12" cy="12" r="10" fill="#12351f" stroke="#34e27a" strokeWidth="1.5" />
                          <path d="m8 12.5 2.6 2.6L16 9.5" stroke="#34e27a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      ) : state === "active" ? (
                        <span style={{ width: 22, height: 22, borderRadius: "50%", border: "2.5px solid #12303d", borderTopColor: "#22d3ee", animation: "spin 1s linear infinite" }} />
                      ) : (
                        <span style={{ width: 22, height: 22, borderRadius: "50%", border: "2px solid var(--app-border)" }} />
                      )}
                      <span style={{ fontSize: 15, fontWeight: state === "active" ? 600 : 500, color: state === "done" ? "var(--app-text)" : state === "active" ? "var(--app-cyan)" : "var(--app-muted2)" }}>{s}</span>
                      <span style={{ marginLeft: "auto", fontSize: 12, color: state === "done" ? "var(--app-green)" : state === "active" ? "var(--app-cyan)" : "var(--app-muted2)" }}>
                        {state === "done" ? "done" : state === "active" ? "in progress" : "queued"}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderRadius: 12, background: "rgba(34,211,238,.07)", fontSize: 13, color: "var(--app-muted)" }}>
                ℹ️ You can leave this page — your video keeps rendering and will be waiting in My Clips.
              </div>
            </>
          )}

          {phase === "failed" && (
            <div className="card" style={{ padding: "30px 28px", display: "flex", flexDirection: "column", gap: 16, alignItems: "flex-start" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 44, height: 44, borderRadius: 13, background: "rgba(240,84,108,.14)", display: "grid", placeItems: "center", fontSize: 20 }}>⚠️</div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 19, color: "var(--app-text)" }}>Generation failed</div>
                  <div style={{ fontSize: 13, color: "var(--app-muted)" }}>Your allowance was not used.</div>
                </div>
              </div>
              <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.55 }}>{clip.error}</div>
              <div style={{ display: "flex", gap: 12 }}>
                <button className="grad-btn" style={{ padding: "13px 24px", fontSize: 15 }} onClick={retry}>
                  ↻ Retry for free
                </button>
                <button className="ghost-btn" style={{ padding: "13px 24px", fontSize: 15 }} onClick={reset}>
                  Start over
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {phase === "result" && clip && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", borderRadius: 12, background: "rgba(52,226,122,.1)", border: "1px solid rgba(52,226,122,.35)", marginTop: 12 }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#34e27a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="m8 12.5 2.6 2.6L16 9.5" />
            </svg>
            <span style={{ fontSize: 15, fontWeight: 600, color: "var(--app-green)" }}>Video ready · 0:{String(Math.round(clip.duration_seconds || 14)).padStart(2, "0")}</span>
            <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--app-muted)" }}>“{clip.take}” · {clip.sport} · {clip.tone}</span>
          </div>
          <div className="result-grid" style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 28, alignItems: "start" }}>
            <div className="card" style={{ padding: 20, display: "grid", placeItems: "center" }}>
              <div style={{ position: "relative", width: "100%", aspectRatio: "9/16", borderRadius: 16, overflow: "hidden", background: "#000" }}>
                <video
                  src={clip.video_url}
                  controls
                  playsInline
                  controlsList="nodownload noremoteplayback"
                  disablePictureInPicture
                  onContextMenu={(e) => e.preventDefault()}
                  onPlay={() => api.track("preview_played")}
                  style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
                />
                {clip.watermarked && (
                  <div style={{ position: "absolute", right: 10, bottom: 44, background: "rgba(0,0,0,.55)", backdropFilter: "blur(4px)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "4px 8px", borderRadius: 6, pointerEvents: "none" }}>
                    ▶ BanterClips
                  </div>
                )}
                <div style={{ position: "absolute", top: 10, left: 10, background: "rgba(0,0,0,.55)", color: "#fff", fontSize: 9, fontWeight: 700, padding: "3px 7px", borderRadius: 6, letterSpacing: ".04em", pointerEvents: "none" }}>
                  AI-GENERATED PARODY
                </div>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <button className="grad-btn" style={{ padding: 15, fontSize: 16 }} onClick={() => setPublishOpen(true)}>
                Publish to Instagram{watermarked ? " · free" : ""}
              </button>
              {canDownload ? (
                <button className="ghost-btn" style={{ padding: 14, fontSize: 15, color: "var(--app-text)" }} onClick={download}>
                  ⬇ Download MP4 · no watermark
                </button>
              ) : (
                <button className="ghost-btn" style={{ padding: 14, fontSize: 15, color: "var(--app-muted)" }} onClick={() => setUpgradeOpen(true)}>
                  🔒 Download HD — Creator feature
                </button>
              )}
              <button className="ghost-btn" style={{ padding: 14, fontSize: 15 }} onClick={reset}>
                ↻ Generate another
              </button>
              <div className="panel" style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
                {[
                  ["Resolution", "1080 × 1920 · 9:16"],
                  ["Duration", `${clip.duration_seconds || 14}s`],
                  ["Format", "MP4 · H.264/AAC"],
                  ["Watermark", clip.watermarked ? "BanterClips (Free plan)" : "None (Creator)"],
                  ["Labeling", "AI-parody disclosure"],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: "flex", fontSize: 13 }}>
                    <span style={{ color: "var(--app-muted)" }}>{k}</span>
                    <span style={{ marginLeft: "auto", fontWeight: 600, color: "var(--app-text)" }}>{v}</span>
                  </div>
                ))}
              </div>
              {watermarked && (
                <div style={{ fontSize: 12.5, color: "var(--app-muted)", lineHeight: 1.5 }}>
                  Free plan publishes with the BanterClips watermark — every post you share promotes your clip <i>and</i> brings creators back to you.{" "}
                  <span onClick={() => nav("/pricing")} style={{ color: "var(--app-cyan)", fontWeight: 600, cursor: "pointer" }}>Compare plans →</span>
                </div>
              )}
              {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}
            </div>
          </div>
        </>
      )}

      {upgradeOpen && <UpgradeModal reason={left <= 0 ? "limit" : "download"} onClose={() => setUpgradeOpen(false)} />}
      {publishOpen && clip && <PublishModal clip={clip} onClose={() => setPublishOpen(false)} />}
    </div>
  );
}
