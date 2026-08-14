import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api, downloadClip } from "../lib/api.js";
import { resolutionLabel } from "../lib/format.js";
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
// Free renders at 720p; 1080p is a Creator feature (server-enforced too).
const RESOLUTIONS = [
  { key: "720p", sub: "HD" },
  { key: "1080p", sub: "Full HD" },
];
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

/** One selectable wording — the user's own, or a suggested variation. */
function TakeOption({ selected, onClick, label, text, hint, badge }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex", flexDirection: "column", gap: 6, width: "100%",
        padding: "13px 16px", borderRadius: 14, cursor: "pointer", textAlign: "left",
        background: selected ? "rgba(34,211,238,.10)" : "transparent",
        border: `1px solid ${selected ? "var(--app-cyan)" : "var(--app-border)"}`,
        animation: "stepIn .35s cubic-bezier(.2,.8,.2,1) both",
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            width: 14, height: 14, borderRadius: "50%", flexShrink: 0,
            border: `2px solid ${selected ? "var(--app-cyan)" : "var(--app-border)"}`,
            background: selected
              ? "radial-gradient(circle, var(--app-cyan) 0 42%, transparent 43%)"
              : "transparent",
          }}
        />
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.7, textTransform: "uppercase", color: selected ? "var(--app-cyan)" : "var(--app-muted)" }}>
          {badge ? `${badge} ` : ""}{label}
        </span>
      </span>
      <span style={{ fontSize: 15, fontWeight: selected ? 600 : 500, lineHeight: 1.45, color: selected ? "var(--app-text)" : "var(--app-muted)" }}>
        “{text}”
      </span>
      {hint && (
        <span style={{ fontSize: 11.5, color: "var(--app-muted2)", lineHeight: 1.4 }}>{hint}</span>
      )}
    </button>
  );
}

export default function Studio() {
  const nav = useNavigate();
  const { search } = useLocation();
  const { profile, left, limit, plan, refreshClips, refreshUsage, clips, canDownload, watermarked } = useApp();
  // input → generating → result | failed. Enhancement happens on the input
  // page, before anything is generated.
  const [phase, setPhase] = useState("input");
  const [busy, setBusy] = useState(false);
  // Enhancement. `take` stays exactly as the user typed it — a variation is
  // only ever *selected*, never written back over their words.
  const [variations, setVariations] = useState([]);
  const [chosen, setChosen] = useState(-1); // -1 = the original
  const [enhancing, setEnhancing] = useState(false);
  const [round, setRound] = useState(0);
  const [take, setTake] = useState("");
  const [sport, setSport] = useState(SPORTS.includes(profile.sports?.[0]) ? profile.sports[0] : "NBA");
  const [tone, setTone] = useState("Funny");
  const [duration, setDuration] = useState(15);
  const [resolution, setResolution] = useState("720p");
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

  // Opened from My Clips as /studio?clip=<id>: jump straight to that clip's
  // state — live status while it renders, the player when it is done.
  useEffect(() => {
    const id = new URLSearchParams(search).get("clip");
    if (!id) return;
    let cancelled = false;
    (async () => {
      try {
        const c = await api.getClip(id);
        if (cancelled) return;
        setClip(c);
        if (c.status === "ready") setPhase("result");
        else if (c.status === "failed") setPhase("failed");
        // Elapsed counts from when the job actually started, not from when
        // this page happened to open — reopening a running clip mid-render
        // used to restart the clock at 0:00.
        else watchClip(c.id, new Date(c.created_at).getTime());
      } catch {
        setError("That clip could not be opened.");
      }
    })();
    return () => {
      cancelled = true;
    };
    // watchClip is stable; re-running on it would restart the poll needlessly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const valid = take.trim().length >= 10 && take.length <= 280;

  const watchClip = useCallback(
    (id, startedAtMs) => {
      setPhase("generating");
      // Wall-clock arithmetic rather than a +1 counter: it survives the page
      // being reopened mid-render and background-tab interval throttling.
      const startedAt = startedAtMs || Date.now();
      const sync = () => setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
      sync();
      clearInterval(tickRef.current);
      tickRef.current = setInterval(sync, 1000);
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

  // Whatever wording will actually be generated: their words unless they
  // picked one of ours.
  const activeTake = chosen >= 0 && variations[chosen] ? variations[chosen].take : take.trim();

  // Ask for two fresh variations. Repeatable — each press widens the search,
  // so a second press gives new ideas rather than rephrasings of the first.
  const enhance = async () => {
    if (!valid || enhancing) return;
    setError("");
    setEnhancing(true);
    try {
      const res = await api.enhanceTakeVariations(take.trim(), sport, tone, round);
      if (res.variations?.length) {
        setVariations(res.variations);
        setChosen(-1); // never auto-select: the user's own take stays chosen
        setRound((r) => r + 1);
      } else {
        setError("Couldn't come up with a better angle — your take is good as is.");
      }
    } catch (e) {
      setError(`Enhance is unavailable right now (${e.message}). Your take still works.`);
    } finally {
      setEnhancing(false);
    }
  };

  const generate = async () => {
    if (!valid) return;
    setError("");
    setBusy(true);
    try {
      const c = await api.createClip(activeTake, sport, tone, duration, resolution);
      setClip(c);
      refreshClips(); // the new in-flight clip shows up in My Clips immediately
      watchClip(c.id, new Date(c.created_at).getTime());
    } catch (e) {
      if (e.code === "limit_reached" || e.code === "upgrade_required") setUpgradeOpen(true);
      else setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    try {
      const c = await api.retryClip(clip.id);
      setClip(c);
      // A retry starts now; created_at is the original creation, so counting
      // from it would open the timer minutes or days in.
      watchClip(c.id, Date.now());
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
    setVariations([]);
    setChosen(-1);
    setRound(0);
    setError("");
  };

  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const stageIdx = clip ? clip.stage_index : 0;
  const latestStep = clip?.current_step || null;

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

          {/* Enhance: offered, never imposed. The typed take above is
              untouched; a variation is only ever selected. */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <button
              type="button"
              onClick={enhance}
              disabled={!valid || enhancing}
              style={{
                alignSelf: "flex-start", display: "inline-flex", alignItems: "center", gap: 9,
                padding: "10px 18px", borderRadius: 999, fontSize: 14, fontWeight: 700,
                cursor: valid && !enhancing ? "pointer" : "not-allowed",
                color: valid ? "var(--app-cyan)" : "var(--app-muted2)",
                background: "rgba(34,211,238,.08)",
                border: `1px solid ${valid ? "rgba(34,211,238,.45)" : "var(--app-border)"}`,
                opacity: valid ? 1 : 0.6,
              }}
            >
              <span style={{ display: "inline-block", animation: enhancing ? "pulseGlow 1.1s ease-in-out infinite" : "none" }}>
                ✨
              </span>
              {enhancing
                ? "Finding sharper angles…"
                : variations.length
                  ? "Enhance again"
                  : "Enhance take"}
            </button>

            {enhancing && (
              <div style={{ display: "grid", gap: 10 }}>
                {[0, 1].map((i) => (
                  <div
                    key={i}
                    className="shimmer"
                    style={{ height: 74, borderRadius: 14, border: "1px solid var(--app-border)" }}
                  />
                ))}
              </div>
            )}

            {!enhancing && variations.length > 0 && (
              <div style={{ display: "grid", gap: 10 }}>
                <TakeOption
                  selected={chosen === -1}
                  onClick={() => setChosen(-1)}
                  label="Your take"
                  text={take.trim()}
                />
                {variations.map((v, i) => (
                  <TakeOption
                    key={`${round}-${i}`}
                    selected={chosen === i}
                    onClick={() => setChosen(i)}
                    label={v.angle || "Sharper"}
                    badge="✨"
                    text={v.take}
                    hint={v.why}
                  />
                ))}
              </div>
            )}
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

          {/* quality — 720p for everyone, 1080p on Creator */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>QUALITY</span>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {RESOLUTIONS.map((r) => {
                const locked = r.key === "1080p" && plan !== "creator";
                const on = resolution === r.key;
                return (
                  <button
                    key={r.key}
                    className={`chip${on ? " on" : ""}`}
                    style={locked ? { color: "var(--app-muted2)", borderStyle: "dashed", display: "inline-flex", alignItems: "center", gap: 6 } : undefined}
                    title={locked ? "1080p video is a Creator feature — Free renders at 720p" : `${r.sub} · ${resolutionLabel(r.key)}`}
                    onClick={() => (locked ? setUpgradeOpen(true) : setResolution(r.key))}
                  >
                    {r.key} · {r.sub}
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
          <button className="grad-btn" style={{ padding: 18, fontSize: 17, borderRadius: 16 }} disabled={!valid || busy} onClick={generate}>
            {busy ? "Starting…" : "🪄 Generate BanterClip"}
          </button>
          <div style={{ fontSize: 12.5, color: "var(--app-muted2)", textAlign: "center", marginTop: -8 }}>
            Hot Take format · cinematic scenes · {duration}s vertical MP4 · {resolution} · AI-parody labeled
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
                  <div key={c.id} className="card" style={{ display: "flex", alignItems: "center", gap: 10, padding: 10, borderRadius: 12, cursor: "pointer" }} onClick={() => nav(`/studio?clip=${c.id}`)}>
                    {/* A real frame from the clip. The gradient stays as the
                        fallback for clips made before posters were stored. */}
                    <div
                      style={{
                        width: 34, height: 58, borderRadius: 7, flexShrink: 0, overflow: "hidden",
                        background: c.thumb_gradient || "linear-gradient(160deg,#22d3ee,#3d2c8d)",
                      }}
                    >
                      {c.poster_url && (
                        <img
                          src={c.poster_url}
                          alt=""
                          loading="lazy"
                          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                        />
                      )}
                    </div>
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
          {/* The take in full — this is the view My Clips links to, so it
              must not truncate the way a card does. */}
          <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 10, padding: "16px 20px", borderRadius: 14, marginTop: 12 }}>
            <span style={{ fontSize: 15.5, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.5 }}>
              “{clip.take}”
            </span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", fontSize: 12.5, color: "var(--app-muted)" }}>
              {[
                clip.sport,
                clip.tone,
                `${clip.duration_target || 15}s`,
                clip.resolution || null,
                clip.is_simulated ? "demo run" : null,
                clip.watermarked ? "watermarked" : null,
              ]
                .filter(Boolean)
                .map((tag) => (
                  <span key={tag} style={{ padding: "3px 9px", borderRadius: 999, border: "1px solid var(--app-border)" }}>
                    {tag}
                  </span>
                ))}
              <span style={{ marginLeft: "auto" }}>
                {new Date(clip.created_at).toLocaleString(undefined, {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </span>
            </div>
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

              {/* One line, always the current one. The stage rows above move
                  every minute or two; this moves every few seconds, which is
                  what makes a four-minute wait feel alive. */}
              {latestStep && (
                <div
                  style={{
                    display: "flex", alignItems: "center", gap: 12, minHeight: 26,
                    padding: "16px 20px", borderRadius: 14,
                    background: "rgba(34,211,238,.06)",
                    border: "1px solid rgba(34,211,238,.18)",
                    overflow: "hidden",
                  }}
                >
                  <span
                    style={{
                      width: 16, height: 16, flexShrink: 0, borderRadius: "50%",
                      border: "2px solid rgba(34,211,238,.25)", borderTopColor: "var(--app-cyan)",
                      animation: "spin 1s linear infinite",
                    }}
                  />
                  {/* keyed on the text so React remounts and replays the slide */}
                  <span
                    key={latestStep}
                    style={{
                      fontSize: 14.5, fontWeight: 600, color: "var(--app-text)",
                      animation: "stepIn .45s cubic-bezier(.2,.8,.2,1)",
                    }}
                  >
                    {latestStep}
                  </span>
                </div>
              )}

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
            <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--app-muted)" }}>{clip.sport} · {clip.tone}</span>
          </div>
          {/* Full take, untruncated — opened from My Clips this is the only
              place the whole thing is readable. */}
          <div className="panel" style={{ padding: "14px 18px", borderRadius: 12, fontSize: 14.5, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.5 }}>
            “{clip.take}”
          </div>
          <div className="result-grid" style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 28, alignItems: "start" }}>
            <div className="card" style={{ padding: 20, display: "grid", placeItems: "center" }}>
              <div style={{ position: "relative", width: "100%", aspectRatio: "9/16", borderRadius: 16, overflow: "hidden", background: "#000" }}>
                {clip.video_url ? (
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
                ) : (
                  // Ready but the URL hasn't landed (storage hiccup): honest
                  // waiting state instead of a dead black player.
                  <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center", color: "var(--app-muted)", padding: 16 }}>
                    <div>
                      <div style={{ fontSize: 28, marginBottom: 10 }}>🎬</div>
                      <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--app-text)" }}>Your video is being prepared</div>
                      <div style={{ fontSize: 12, marginTop: 6 }}>It's finished rendering — check back in a minute.</div>
                    </div>
                  </div>
                )}
                {clip.watermarked && (
                  <div style={{ position: "absolute", right: 10, bottom: 44, background: "rgba(0,0,0,.55)", backdropFilter: "blur(4px)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "4px 8px", borderRadius: 6, pointerEvents: "none" }}>
                    ▶ BanterClips
                  </div>
                )}
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
                  ["Resolution", resolutionLabel(clip.resolution)],
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
