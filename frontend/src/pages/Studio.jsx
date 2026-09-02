import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import { resolutionLabel } from "../lib/format.js";
import { UpgradeModal, PublishModal, TopUpModal } from "../components/Modals.jsx";
import ScriptView, { ScriptDialog } from "../components/ScriptView.jsx";
import Trending from "../components/Trending.jsx";
import { SPORT_KEYS, sportIcon, suggestionsFor } from "../lib/sports.js";
import DownloadButton from "../components/DownloadButton.jsx";
import { PublishedTo } from "../components/SocialIcon.jsx";

import { useSeo } from "../lib/seo.js";
const TONES = [
  { key: "Funny", icon: "😄", sub: "Playful roast" },
  { key: "Savage", icon: "🔪", sub: "No mercy" },
  { key: "Roast", icon: "🔥", sub: "Friendly burn" },
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
  designing_characters: "Designing characters",
  generating_scenes: "Generating scene images",
  animating_scenes: "Animating scenes",
  assembling_video: "Assembling video",
  validating: "Validating",
};
const STAGES = Object.values(STAGE_LABELS).slice(1); // the real stages, in order

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
  useSeo({
    title: "Studio — BanterClips",
    description: "Write a sports take and generate a video.",
    path: "/studio",
    noindex: true,
  });

  const nav = useNavigate();
  const { search } = useLocation();
  const { profile, credits, videoPrice, prices, plan, refreshClips, refreshUsage, clips, canDownload, watermarked } = useApp();
  // Prompt length is a plan capability: 280 characters on Free, 500 on Creator.
  const takeLimit = plan === "creator" ? 500 : 280;
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
  // Sport is a multi-select HINT now, not a required single choice: empty is
  // the normal case, and the server infers it from the take.
  const [sports, setSports] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [subjectInput, setSubjectInput] = useState("");
  const [direction, setDirection] = useState("");
  const [reference, setReference] = useState(null);
  const [tone, setTone] = useState("Funny");
  const [duration, setDuration] = useState(15);
  const [resolution, setResolution] = useState("720p");
  const [clip, setClip] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [topupOpen, setTopupOpen] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [scriptOpen, setScriptOpen] = useState(false);      // "Show script" dialog
  const [scriptFeedback, setScriptFeedback] = useState(""); // regenerate note
  const [scriptBusy, setScriptBusy] = useState("");
  // "Rewrite with different options": tone/length/quality editable at the
  // approval gate, seeded from the clip whenever a script arrives.
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [optTone, setOptTone] = useState("Funny");
  const [optDuration, setOptDuration] = useState(15);
  const [optResolution, setOptResolution] = useState("720p");
  // Editable working copy of the script: the user can rewrite any dialogue
  // line or action before approving; diffs are saved on approve.
  const [draft, setDraft] = useState(null);
  // Scene editor on a finished video: a working copy of the scenes, which
  // ones to re-render, and the request in flight.
  const [sceneEditOpen, setSceneEditOpen] = useState(false);
  const [sceneDraft, setSceneDraft] = useState([]);
  const [sceneSel, setSceneSel] = useState([]);
  const [sceneBusy, setSceneBusy] = useState(false);

  useEffect(() => {
    if (clip?.status === "script_ready" && clip.script) {
      setDraft(JSON.parse(JSON.stringify(clip.script)));
      setOptTone(clip.tone);
      setOptDuration(clip.duration_target);
      setOptResolution(clip.resolution);
      setOptionsOpen(false);
    }
  }, [clip?.status, clip?.script]);

  const editDraft = (sceneIndex, field, value) =>
    setDraft((d) => {
      if (!d) return d;
      const next = { ...d, scenes: d.scenes.map((s, i) => (i === sceneIndex ? { ...s, [field]: value } : s)) };
      return next;
    });

  const draftEdits = () => {
    if (!draft || !clip?.script) return [];
    return draft.scenes
      .map((s, i) => {
        const orig = clip.script.scenes[i] || {};
        const edit = { index: i };
        if ((s.line || "") !== (orig.line || "")) edit.line = s.line || "";
        if ((s.action || "") !== (orig.action || "")) edit.action = s.action || "";
        return edit;
      })
      .filter((e) => "line" in e || "action" in e);
  };
  const pollRef = useRef(null);
  const tickRef = useRef(null);

  const stopTimers = useCallback(() => {
    clearInterval(pollRef.current);
    clearInterval(tickRef.current);
  }, []);
  useEffect(() => stopTimers, [stopTimers]);

  const reset = () => {
    stopTimers();
    setPhase("input");
    setTake("");
    setClip(null);
    setVariations([]);
    setChosen(-1);
    setRound(0);
    setError("");
    setScriptOpen(false);
    setScriptFeedback("");
    setOptionsOpen(false);
    setDirection("");
    setReference(null);
  };

  // Cancel at the approval gate: delete the clip (nothing rendered, nothing
  // charged) and put the take back in the composer via ?prompt= so it isn't
  // lost. reset() also runs inline for the case where the URL doesn't change
  // and the search effect won't refire.
  const cancelScript = async () => {
    if (!clip) return;
    setScriptBusy("cancel");
    setError("");
    try {
      const keep = clip.take || "";
      await api.deleteClip(clip.id);
      reset();
      setTake(keep);
      nav(`/studio?prompt=${encodeURIComponent(keep)}`, { replace: true });
    } catch (e) {
      setError(e.message);
    } finally {
      setScriptBusy("");
    }
  };

  // Scene editing: exact per-scene quote at the video's own rate (the same
  // per-second price the video was quoted at), rounded up per scene.
  const scenePrice = (s) => Math.max(1, Math.ceil((Number(s?.seconds) || 4) * videoPrice(1, clip?.resolution || "720p")));
  const openSceneEditor = () => {
    setSceneDraft((clip?.script?.scenes || []).map((s) => ({ line: s.line || "", action: s.action || "", seconds: s.seconds })));
    setSceneSel([]);
    setError("");
    setSceneEditOpen(true);
  };
  const editScene = (i, field, value) => {
    setSceneDraft((d) => d.map((s, k) => (k === i ? { ...s, [field]: value } : s)));
    setSceneSel((sel) => (sel.includes(i) ? sel : [...sel, i]));
  };
  const toggleScene = (i) => setSceneSel((sel) => (sel.includes(i) ? sel.filter((k) => k !== i) : [...sel, i]));
  const sceneQuote = sceneSel.reduce((sum, i) => sum + scenePrice(clip?.script?.scenes?.[i]), 0);
  const submitSceneEdits = async () => {
    if (!clip || !sceneSel.length) return;
    setSceneBusy(true);
    setError("");
    try {
      const scenes = sceneSel.slice().sort((a, b) => a - b).map((i) => {
        const orig = clip.script.scenes[i] || {};
        const s = { index: i };
        if ((sceneDraft[i]?.line || "") !== (orig.line || "")) s.line = sceneDraft[i].line;
        if ((sceneDraft[i]?.action || "") !== (orig.action || "")) s.action = sceneDraft[i].action;
        return s;
      });
      const c = await api.rerenderScenes(clip.id, scenes);
      setSceneEditOpen(false);
      setClip(c);
      watchClip(c.id, Date.now());
    } catch (e) {
      setError(e.message);
    } finally {
      setSceneBusy(false);
    }
  };

  // Opened from My Clips as /studio?clip=<id>: jump straight to that clip's
  // state — live status while it renders, the player when it is done.
  useEffect(() => {
    const id = new URLSearchParams(search).get("clip");
    const prompt = new URLSearchParams(search).get("prompt");
    if (!id) {
      reset();
      if (prompt) setTake(prompt.slice(0, takeLimit));
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const c = await api.getClip(id);
        if (cancelled) return;
        setClip(c);
        if (c.status === "ready") setPhase("result");
        else if (c.status === "failed") setPhase("failed");
        else if (c.status === "paused") setPhase("paused");
        else if (c.status === "script_ready") setPhase("script");
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

  const valid = take.trim().length >= 10 && take.length <= takeLimit;
  // Trending and enhancement need one sport to key off. The user's pick wins,
  // then what they follow, then the app's busiest sport.
  const primarySport = sports[0] || profile.sports?.[0] || "Soccer";
  const subjectIdeas = suggestionsFor(sports.length ? sports : profile.sports, "players", 6)
    .filter((s) => !subjects.includes(s));
  const addSubject = (value) => {
    const name = String(value || "").trim().replace(/,$/, "");
    if (name && !subjects.includes(name) && subjects.length < 8) {
      setSubjects([...subjects, name]);
    }
    setSubjectInput("");
  };
  // Exact menu price of the configured video (PRICING §7) — never estimated.
  const thisPrice = videoPrice(duration, resolution);
  // Whether the approval-gate options differ from what the clip was created
  // with — drives the "rewrite with new options" path and the new quote line.
  const optChanged =
    clip?.status === "script_ready" &&
    (optTone !== clip.tone || optDuration !== clip.duration_target || optResolution !== clip.resolution);

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
          } else if (c.status === "paused") {
            stopTimers();
            setPhase("paused");
            refreshClips();
          } else if (c.status === "script_ready") {
            // The script is written; nothing renders until it's approved.
            stopTimers();
            setPhase("script");
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
      const res = await api.enhanceTakeVariations(take.trim(), primarySport, tone, round);
      if (res.variations?.length) {
        setVariations(res.variations);
        setChosen(-1); // never auto-select: the user's own take stays chosen
        setRound((r) => r + 1);
      } else {
        setError("Couldn't come up with a better angle — your take is good as is.");
      }
    } catch (e) {
      if (e.code === "insufficient_credits") setTopupOpen(true);
      else setError(`Enhance is unavailable right now (${e.message}). Your take still works.`);
    } finally {
      setEnhancing(false);
      refreshUsage(); // the enhance credit left the wallet
    }
  };

  const generate = async () => {
    if (!valid) return;
    if (credits < thisPrice) {
      setTopupOpen(true);
      return;
    }
    setError("");
    setBusy(true);
    try {
      const uploaded = reference ? await api.uploadReference(reference) : null;
      const c = await api.createClip(activeTake, sports, tone, duration, resolution, subjects, direction, uploaded?.key);
      setClip(c);
      refreshClips(); // the new in-flight clip shows up in My Clips immediately
      watchClip(c.id, new Date(c.created_at).getTime());
    } catch (e) {
      // Empty balance → top up, never an upgrade prompt (PRICING rule 2).
      if (e.code === "insufficient_credits") setTopupOpen(true);
      else if (e.code === "upgrade_required") setUpgradeOpen(true);
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
      if (e.code === "insufficient_credits") setTopupOpen(true);
      else setError(e.message);
    }
  };

  // A trending suggestion fills the take like the user typed it (real flow),
  // and nudges tone/length to the suggestion's fit — without ever selecting
  // a locked length on the Free plan.
  const useTrending = (p) => {
    setTake(p.take);
    setVariations([]);
    setChosen(-1);
    if (TONES.some((t) => t.key === p.tone)) setTone(p.tone);
    if (DURATIONS.includes(p.seconds) && (p.seconds <= FREE_MAX_DURATION || plan === "creator")) {
      setDuration(p.seconds);
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
    api.track("trending_take_used", { sport: primarySport, tone: p.tone, seconds: p.seconds });
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
            <h1 style={{ fontSize: "clamp(28px, 7vw, 42px)", fontWeight: 800, color: "var(--app-text)", margin: "18px 0 10px" }}>Build your banter</h1>
            <div style={{ fontSize: "clamp(14px, 3.8vw, 16px)", color: "var(--app-muted)" }}>Simple choices in. A production-ready video prompt out.</div>
          </div>

          {/* take input */}
          <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>WHAT DO YOU WANT TO SAY?</span>
          <div style={{ position: "relative" }}>
            <textarea
              value={take}
              onChange={(e) => setTake(e.target.value)}
              placeholder="Messi is still the GOAT."
              rows={4}
              className="panel"
              style={{ width: "100%", padding: "clamp(16px, 4vw, 22px) clamp(16px, 4vw, 24px)", fontSize: "clamp(16px, 4.5vw, 19px)", fontWeight: 500, color: "var(--app-text)", resize: "vertical", background: "var(--app-surface)", border: "1.5px solid var(--app-border)", borderRadius: 20, lineHeight: 1.45, boxSizing: "border-box" }}
            />
            <span
              onClick={() => plan !== "creator" && take.length > takeLimit && setUpgradeOpen(true)}
              style={{ position: "absolute", right: 16, bottom: 14, fontSize: 12, color: take.length > takeLimit ? "var(--app-error)" : "var(--app-muted2)", cursor: plan !== "creator" && take.length > takeLimit ? "pointer" : "default" }}
            >
              {take.length} / {takeLimit}
              {plan !== "creator" && take.length > takeLimit && " · up to 500 on Creator →"}
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>WHAT HAPPENS?</span>
              <span style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>optional · describe the setting or action</span>
            </div>
            <textarea
              value={direction}
              onChange={(e) => setDirection(e.target.value.slice(0, 400))}
              placeholder="Press room after the derby. The manager stays calm while the mascot celebrates behind him."
              rows={3}
              className="panel"
              style={{ width: "100%", boxSizing: "border-box", padding: "13px 14px", resize: "vertical", fontSize: 14.5, color: "var(--app-text)" }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>REFERENCE PHOTO OR VIDEO</span>
              <span style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>optional · JPEG or MP4 · up to 15 MB</span>
            </div>
            <label className="panel" style={{ padding: "12px 14px", cursor: "pointer", color: reference ? "var(--app-text)" : "var(--app-muted)", fontSize: 14 }}>
              {reference ? `✓ ${reference.name}` : "+ Choose a reference"}
              <input
                type="file"
                accept="image/jpeg,video/mp4"
                hidden
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  if (file && file.size > 15 * 1024 * 1024) setError("Reference must be 15 MB or smaller.");
                  else { setReference(file); setError(""); }
                }}
              />
            </label>
            {reference && <button type="button" onClick={() => setReference(null)} style={{ alignSelf: "flex-start", border: 0, background: "none", color: "var(--app-muted)", cursor: "pointer", padding: 0 }}>Remove reference</button>}
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
                  ? `Enhance again · ${prices.enhance_take} credit`
                  : `Enhance take · ${prices.enhance_take} credit`}
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

          {/* trending — real topics from today's internet, per sport */}
          <Trending sport={primarySport} onUse={useTrending} />

          {/* Sport — optional and multi-select. Most takes name their own
              league or player, so this is a hint, not a gate: leave it alone
              and the server works the sport out from the words. */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>SPORT</span>
              <span style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>
                optional · {sports.length
                  ? "pick more than one to cross them over"
                  : "we'll work it out from your take"}
              </span>
              {sports.length > 0 && (
                <button onClick={() => setSports([])}
                        style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--app-muted)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                  Clear
                </button>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {SPORT_KEYS.map((s) => {
                const on = sports.includes(s);
                return (
                  <button
                    key={s}
                    className={`chip${on ? " on" : ""}`}
                    onClick={() => setSports(on ? sports.filter((x) => x !== s) : [...sports, s].slice(0, 4))}
                    style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                  >
                    <span aria-hidden="true">{sportIcon(s)}</span> {s}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Teams / players — optional specificity. Anyone named here is a
              requirement for the script, not a suggestion. */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>WHO IS IN IT?</span>
              <span style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>optional · anyone you add will be in the video</span>
            </div>
            {subjects.length > 0 && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {subjects.map((s) => (
                  <button key={s} className="chip on" onClick={() => setSubjects(subjects.filter((x) => x !== s))}
                          title="Remove" style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                    {s} <span style={{ opacity: 0.7 }}>×</span>
                  </button>
                ))}
              </div>
            )}
            <input
              value={subjectInput}
              onChange={(e) => setSubjectInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addSubject(subjectInput); }
              }}
              onBlur={() => addSubject(subjectInput)}
              placeholder="Add a team or player — Arsenal, Mbappé, LeBron…"
              className="panel"
              style={{ padding: "11px 14px", fontSize: 14.5, color: "var(--app-text)", background: "var(--app-surface)", border: "1px solid var(--app-border)", borderRadius: 12, boxSizing: "border-box", width: "100%" }}
            />
            {subjectIdeas.length > 0 && (
              <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
                {subjectIdeas.map((s) => (
                  <button key={s} className="chip" onClick={() => addSubject(s)}
                          style={{ fontSize: 12, opacity: 0.85 }}>+ {s}</button>
                ))}
              </div>
            )}
          </div>

          {/* tone cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>STYLE</span>
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

          {/* credits bar — the exact quote, and top-up (never upgrade) when short */}
          <div className="panel" style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 18px", borderRadius: 14, flexWrap: "wrap" }}>
            <span style={{ color: "var(--app-cyan)" }}>⚡</span>
            <span style={{ fontSize: 13.5, color: "var(--app-muted)" }}>
              This video: <b style={{ color: "var(--app-text)" }}>{thisPrice} credits</b>
              {" · "}you have <b style={{ color: credits < thisPrice ? "var(--app-error)" : "var(--app-text)" }}>{credits.toLocaleString()}</b>
              {" · "}charged only when your video completes
            </span>
            <div style={{ flex: 1 }} />
            <button onClick={() => setTopupOpen(true)} style={{ background: "none", border: "none", color: "var(--app-cyan)", fontWeight: 700, fontSize: 13.5, cursor: "pointer" }}>
              + Top up credits
            </button>
          </div>

          {error && (
            <div style={{ fontSize: 13.5, color: "var(--app-error)", background: "rgba(240,84,108,.1)", borderRadius: 12, padding: "12px 16px" }}>
              {error}
            </div>
          )}

          {/* generate */}
          <button className="grad-btn" style={{ padding: 18, fontSize: 17, borderRadius: 16 }} disabled={!valid || busy} onClick={generate}>
            {busy ? (reference ? "Uploading reference…" : "Starting…") : "🪄 Build My Banter"}
          </button>
          <div style={{ fontSize: 12.5, color: "var(--app-muted2)", textAlign: "center", marginTop: -8 }}>
            Hot Take format · cinematic scenes · {duration}s vertical MP4 · {resolution}
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
                      <div style={{ fontSize: 10.5, color: c.status === "failed" ? "var(--app-error)" : "var(--app-muted)", marginTop: 3, display: "flex", alignItems: "center", gap: 5 }}>
                        <span>{c.sport} · {c.tone}{c.status !== "ready" ? ` · ${c.status}` : ""}</span>
                        <PublishedTo publishes={c.publishes} size={13} label="" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {(phase === "generating" || phase === "failed" || phase === "paused" || phase === "script") && clip && (
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
              <div className="card" style={{ padding: "clamp(18px, 4.5vw, 26px) clamp(16px, 5vw, 28px)" }}>
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

          {phase === "script" && clip.script && (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", borderRadius: 12, background: "rgba(34,211,238,.08)", border: "1px solid rgba(34,211,238,.3)" }}>
                <span style={{ fontSize: 20 }}>📝</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15.5, color: "var(--app-text)" }}>Your script is ready — review it</div>
                  <div style={{ fontSize: 12.5, color: "var(--app-muted)" }}>
                    Nothing is generated (and nothing is used up) until you approve.
                  </div>
                </div>
              </div>

              <div className="card" style={{ padding: "clamp(14px, 3vw, 22px)" }}>
                <ScriptView script={draft || clip.script} editable onEdit={editDraft} />
              </div>
              <div style={{ fontSize: 12, color: "var(--app-muted2)", marginTop: -12 }}>
                ✏️ Every line and action above is editable — your words are what gets performed.
              </div>

              {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}

              <button
                className="grad-btn"
                style={{ padding: 16, fontSize: 16, borderRadius: 14 }}
                disabled={!!scriptBusy}
                onClick={async () => {
                  setScriptBusy("approve");
                  setError("");
                  try {
                    const edits = draftEdits();
                    if (edits.length) await api.updateScript(clip.id, { scenes: edits });
                    const c = await api.approveScript(clip.id);
                    setClip(c);
                    watchClip(c.id, Date.now());
                  } catch (e) {
                    setError(e.message);
                  } finally {
                    setScriptBusy("");
                  }
                }}
              >
                {scriptBusy === "approve"
                  ? "Starting…"
                  : draftEdits().length
                    ? "✅ Save edits & generate video"
                    : "✅ Approve script & generate video"}
              </button>

              <div className="panel" style={{ padding: "12px 14px", borderRadius: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                <input
                  value={scriptFeedback}
                  onChange={(e) => setScriptFeedback(e.target.value)}
                  placeholder="Optional: what should change? e.g. “funnier, and set it in the press room”"
                  style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", fontSize: 13.5, color: "var(--app-text)", background: "var(--app-surface)", border: "1px solid var(--app-border)", borderRadius: 9 }}
                />

                <button
                  onClick={() => setOptionsOpen((o) => !o)}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: "2px 0", alignSelf: "flex-start", fontSize: 13, fontWeight: 700, color: optChanged ? "var(--app-cyan)" : "var(--app-muted)", display: "inline-flex", alignItems: "center", gap: 7 }}
                >
                  ⚙ Different options {optionsOpen ? "▴" : "▾"}
                  {optChanged && !optionsOpen && (
                    <span style={{ fontSize: 9.5, fontWeight: 800, letterSpacing: ".05em", padding: "2px 7px", borderRadius: 999, background: "rgba(34,211,238,.12)", color: "var(--app-cyan)" }}>
                      CHANGED
                    </span>
                  )}
                </button>

                {optionsOpen && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "12px 12px", borderRadius: 10, background: "var(--app-surface)", border: "1px solid var(--app-border)" }}>
                    <div style={{ display: "flex", gap: 7, flexWrap: "wrap", alignItems: "center" }}>
                      <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1, color: "var(--app-muted2)", width: 54, flexShrink: 0 }}>STYLE</span>
                      {TONES.map((t) => (
                        <button
                          key={t.key}
                          className={`chip${optTone === t.key ? " on" : ""}`}
                          style={{ padding: "7px 11px", fontSize: 12.5 }}
                          onClick={() => setOptTone(t.key)}
                        >
                          {t.icon} {t.key}
                        </button>
                      ))}
                    </div>
                    <div style={{ display: "flex", gap: 7, flexWrap: "wrap", alignItems: "center" }}>
                      <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1, color: "var(--app-muted2)", width: 54, flexShrink: 0 }}>LENGTH</span>
                      {DURATIONS.map((d) => {
                        const locked = d > FREE_MAX_DURATION && plan !== "creator";
                        return (
                          <button
                            key={d}
                            className={`chip${optDuration === d ? " on" : ""}`}
                            style={{ padding: "7px 11px", fontSize: 12.5, ...(locked ? { color: "var(--app-muted2)", borderStyle: "dashed", display: "inline-flex", alignItems: "center", gap: 5 } : {}) }}
                            title={locked ? "Videos longer than 15 seconds are a Creator feature" : undefined}
                            onClick={() => (locked ? setUpgradeOpen(true) : setOptDuration(d))}
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
                    <div style={{ display: "flex", gap: 7, flexWrap: "wrap", alignItems: "center" }}>
                      <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1, color: "var(--app-muted2)", width: 54, flexShrink: 0 }}>QUALITY</span>
                      {RESOLUTIONS.map((r) => {
                        const locked = r.key === "1080p" && plan !== "creator";
                        return (
                          <button
                            key={r.key}
                            className={`chip${optResolution === r.key ? " on" : ""}`}
                            style={{ padding: "7px 11px", fontSize: 12.5, ...(locked ? { color: "var(--app-muted2)", borderStyle: "dashed", display: "inline-flex", alignItems: "center", gap: 5 } : {}) }}
                            title={locked ? "1080p video is a Creator feature — Free renders at 720p" : undefined}
                            onClick={() => (locked ? setUpgradeOpen(true) : setOptResolution(r.key))}
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
                    {optChanged && (
                      <div style={{ fontSize: 12.5, color: "var(--app-muted)" }}>
                        ⚡ New quote: <b style={{ color: "var(--app-text)" }}>{videoPrice(optDuration, optResolution)} credits</b>
                        {" · was "}{videoPrice(clip.duration_target, clip.resolution)}
                        {" · still charged only when the video completes"}
                      </div>
                    )}
                  </div>
                )}

                <button
                  className="ghost-btn"
                  style={{ padding: "11px 16px", fontSize: 14 }}
                  disabled={!!scriptBusy}
                  onClick={async () => {
                    setScriptBusy("regen");
                    setError("");
                    try {
                      const options = optChanged
                        ? { tone: optTone, duration: optDuration, resolution: optResolution }
                        : {};
                      const c = await api.regenerateScript(clip.id, scriptFeedback.trim(), options);
                      setClip(c);
                      setScriptFeedback("");
                      watchClip(c.id, Date.now());
                    } catch (e) {
                      setError(e.message);
                    } finally {
                      setScriptBusy("");
                    }
                  }}
                >
                  {scriptBusy === "regen"
                    ? "Rewriting…"
                    : optChanged
                      ? "↻ Rewrite with new options (free)"
                      : "↻ Write a different script (free)"}
                </button>
              </div>

              <button
                disabled={!!scriptBusy}
                onClick={cancelScript}
                style={{ alignSelf: "center", background: "none", border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600, color: "var(--app-muted2)", padding: 6 }}
              >
                {scriptBusy === "cancel" ? "Cancelling…" : "✕ Cancel this video — nothing has been charged"}
              </button>
            </>
          )}

          {phase === "failed" && (
            <div className="card" style={{ padding: "30px 28px", display: "flex", flexDirection: "column", gap: 16, alignItems: "flex-start" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 44, height: 44, borderRadius: 13, background: "rgba(240,84,108,.14)", display: "grid", placeItems: "center", fontSize: 20 }}>⚠️</div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 19, color: "var(--app-text)" }}>Generation failed</div>
                  <div style={{ fontSize: 13, color: "var(--app-muted)" }}>You were not charged.</div>
                </div>
              </div>
              <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.55 }}>{clip.error}</div>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <button className="grad-btn" style={{ padding: "13px 24px", fontSize: 15 }} onClick={retry}>
                  ↻ Retry for free
                </button>
                <button className="ghost-btn" style={{ padding: "13px 24px", fontSize: 15 }} onClick={reset}>
                  Start over
                </button>
              </div>
            </div>
          )}

          {/* Paused: the provider ran out of credits mid-render. Progress is
              checkpointed server-side, so Resume finishes only the missing
              scenes — and nothing has been charged. */}
          {phase === "paused" && (
            <div className="card" style={{ padding: "30px 28px", display: "flex", flexDirection: "column", gap: 16, alignItems: "flex-start", borderColor: "rgba(225,158,60,.5)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 44, height: 44, borderRadius: 13, background: "rgba(225,158,60,.14)", display: "grid", placeItems: "center", fontSize: 20 }}>⏸</div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 19, color: "var(--app-text)" }}>Generation paused</div>
                  <div style={{ fontSize: 13, color: "var(--app-muted)" }}>
                    Progress saved · you haven't been charged
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 12.5, color: "var(--app-muted2)", lineHeight: 1.55 }}>{clip.error}</div>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <button className="grad-btn" style={{ padding: "13px 24px", fontSize: 15 }} onClick={retry}>
                  ▶ Resume — finished scenes won't re-render
                </button>
                <button className="ghost-btn" style={{ padding: "13px 24px", fontSize: 15 }} onClick={reset}>
                  Start something else
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {phase === "result" && clip && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", borderRadius: 12, background: "rgba(52,226,122,.1)", border: "1px solid rgba(52,226,122,.35)", marginTop: 12, flexWrap: "wrap" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#34e27a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="m8 12.5 2.6 2.6L16 9.5" />
            </svg>
            <span style={{ fontSize: 15, fontWeight: 600, color: "var(--app-green)" }}>Video ready · 0:{String(Math.round(clip.duration_seconds || 14)).padStart(2, "0")}</span>
            <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--app-muted)" }}>
              {clip.sport} · {clip.tone}
              {clip.credits_charged > 0 &&
                ` · ⚡ ${clip.credits_charged} credits (${clip.duration_target}s ${clip.resolution === "1080p" ? "HD" : "Standard"})`}
              {clip.credits_edits > 0 && ` + ${clip.credits_edits} scene edits`}
            </span>
          </div>
          {/* Full take, untruncated — opened from My Clips this is the only
              place the whole thing is readable. */}
          <div className="panel" style={{ padding: "14px 18px", borderRadius: 12, fontSize: 14.5, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.5 }}>
            “{clip.take}”
          </div>
          {clip.error && (
            <div style={{ padding: "11px 14px", borderRadius: 12, fontSize: 13, color: "var(--app-text)", background: "rgba(225,158,60,.12)", border: "1px solid rgba(225,158,60,.4)" }}>
              ⚠️ {clip.error}
            </div>
          )}
          {clip.reference_url && (
            <div className="panel" style={{ padding: "10px 14px", borderRadius: 12, display: "flex", alignItems: "center", gap: 12 }}>
              <a href={clip.reference_url} target="_blank" rel="noreferrer" title="Open the reference in full">
                {clip.reference_url.includes(".mp4") ? (
                  <video src={clip.reference_url} muted style={{ width: 46, height: 46, borderRadius: 10, objectFit: "cover", border: "1px solid var(--app-border)", display: "block" }} />
                ) : (
                  <img src={clip.reference_url} alt="Reference" style={{ width: 46, height: 46, borderRadius: 10, objectFit: "cover", border: "1px solid var(--app-border)", display: "block" }} />
                )}
              </a>
              <div style={{ fontSize: 12.5, color: "var(--app-muted)" }}>
                <b style={{ color: "var(--app-text)" }}>📎 Reference</b> — this {clip.reference_url.includes(".mp4") ? "video" : "photo"} anchored
                the person in your video
              </div>
            </div>
          )}
          <div className="result-grid" style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 28, alignItems: "start" }}>
            <div className="card" style={{ padding: 20, display: "grid", placeItems: "center" }}>
              <div className="result-player" style={{ position: "relative", width: "100%", aspectRatio: "9/16", borderRadius: 16, overflow: "hidden", background: "#000" }}>
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
              {clip.publishes?.some((p) => p.status === "published") && (
                <div className="panel" style={{ padding: "11px 14px", borderRadius: 10, fontSize: 13 }}>
                  <PublishedTo publishes={clip.publishes} size={20} />
                </div>
              )}
              <button className="grad-btn" style={{ padding: 15, fontSize: 16 }} onClick={() => setPublishOpen(true)}>
                Publish{watermarked ? " · free" : ""}
              </button>
              {canDownload ? (
                <DownloadButton
                  clip={clip}
                  className="ghost-btn"
                  label="⬇ Download MP4 · no watermark"
                  style={{ padding: 14, fontSize: 15, color: "var(--app-text)" }}
                  onError={(e) => (e.code === "upgrade_required" || e.status === 403
                    ? setUpgradeOpen(true)
                    : setError(e.message))}
                />
              ) : (
                <button className="ghost-btn" style={{ padding: 14, fontSize: 15, color: "var(--app-muted)" }} onClick={() => setUpgradeOpen(true)}>
                  🔒 Download HD — Creator feature
                </button>
              )}
              {clip.script && (
                <button className="ghost-btn" style={{ padding: 14, fontSize: 15 }} onClick={() => setScriptOpen(true)}>
                  📝 Show script
                </button>
              )}
              {clip.editable ? (
                <button className="ghost-btn" style={{ padding: 14, fontSize: 15, borderColor: sceneEditOpen ? "var(--app-cyan)" : undefined }} onClick={() => (sceneEditOpen ? setSceneEditOpen(false) : openSceneEditor())}>
                  ✂️ Edit scenes — re-render only what you change
                </button>
              ) : !clip.is_simulated && (
                <div style={{ fontSize: 12, color: "var(--app-muted2)", lineHeight: 1.5 }}>
                  ✂️ Scene editing is available for 7 days after a video is made.
                </div>
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

          {sceneEditOpen && clip.script && (
            <div className="card" style={{ padding: "clamp(14px, 3vw, 22px)", display: "flex", flexDirection: "column", gap: 14, borderColor: "rgba(34,211,238,.35)" }}>
              <div>
                <div style={{ fontWeight: 800, fontSize: 17, color: "var(--app-text)" }}>✂️ Edit scenes</div>
                <div style={{ fontSize: 12.5, color: "var(--app-muted)", marginTop: 4, lineHeight: 1.5 }}>
                  Tick the scenes to re-render, and change their line or action if you like. Untouched scenes are reused as they are — you only pay for what's re-rendered, and only once the new cut lands. Your current video stays until then.
                </div>
              </div>
              {clip.script.scenes.map((s, i) => {
                const on = sceneSel.includes(i);
                return (
                  <div key={i} style={{ display: "flex", flexDirection: "column", gap: 8, padding: "12px 14px", borderRadius: 12, background: on ? "rgba(34,211,238,.06)" : "var(--app-surface)", border: `1.5px solid ${on ? "var(--app-cyan)" : "var(--app-border)"}` }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", fontSize: 13.5, fontWeight: 700, color: "var(--app-text)" }}>
                      <input type="checkbox" checked={on} onChange={() => toggleScene(i)} style={{ width: 16, height: 16 }} />
                      Scene {i + 1} · {s.seconds}s
                      <span style={{ marginLeft: "auto", fontSize: 12, fontWeight: 600, color: on ? "var(--app-cyan)" : "var(--app-muted2)" }}>⚡ {scenePrice(s)} credits to re-render</span>
                    </label>
                    <textarea
                      value={sceneDraft[i]?.line ?? ""}
                      onChange={(e) => editScene(i, "line", e.target.value.slice(0, 220))}
                      placeholder="(silent — no line in this shot)"
                      rows={2}
                      style={{ width: "100%", boxSizing: "border-box", padding: "9px 11px", fontSize: 13.5, color: "var(--app-text)", background: "var(--app-bg)", border: "1px solid var(--app-border)", borderRadius: 9, resize: "vertical", lineHeight: 1.45 }}
                    />
                    <textarea
                      value={sceneDraft[i]?.action ?? ""}
                      onChange={(e) => editScene(i, "action", e.target.value.slice(0, 400))}
                      placeholder="What happens in the shot"
                      rows={2}
                      style={{ width: "100%", boxSizing: "border-box", padding: "9px 11px", fontSize: 12.5, color: "var(--app-muted)", background: "var(--app-bg)", border: "1px solid var(--app-border)", borderRadius: 9, resize: "vertical", lineHeight: 1.45 }}
                    />
                  </div>
                );
              })}
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <span style={{ fontSize: 13.5, color: "var(--app-muted)" }}>
                  {sceneSel.length ? <>Re-render <b style={{ color: "var(--app-text)" }}>{sceneSel.length} scene{sceneSel.length > 1 ? "s" : ""}</b> · <b style={{ color: "var(--app-text)" }}>{sceneQuote} credits</b> · you have {credits.toLocaleString()}</> : "Tick at least one scene"}
                </span>
                <div style={{ marginLeft: "auto", display: "flex", gap: 10 }}>
                  <button className="ghost-btn" style={{ padding: "11px 16px", fontSize: 14 }} onClick={() => setSceneEditOpen(false)} disabled={sceneBusy}>Cancel</button>
                  {sceneSel.length > 0 && credits < sceneQuote ? (
                    <button className="grad-btn" style={{ padding: "11px 18px", fontSize: 14 }} onClick={() => setTopupOpen(true)}>⚡ Top up credits</button>
                  ) : (
                    <button className="grad-btn" style={{ padding: "11px 18px", fontSize: 14 }} disabled={!sceneSel.length || sceneBusy} onClick={submitSceneEdits}>
                      {sceneBusy ? "Starting…" : `✨ Re-render ${sceneSel.length || ""} scene${sceneSel.length === 1 ? "" : "s"} · ${sceneQuote} credits`}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {upgradeOpen && <UpgradeModal reason="download" onClose={() => setUpgradeOpen(false)} />}
      {topupOpen && <TopUpModal needed={thisPrice} onClose={() => { setTopupOpen(false); refreshUsage(); }} />}
      {publishOpen && clip && <PublishModal clip={clip} onClose={() => setPublishOpen(false)} />}
      {scriptOpen && clip?.script && <ScriptDialog script={clip.script} onClose={() => setScriptOpen(false)} />}
    </div>
  );
}
