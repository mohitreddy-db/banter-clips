import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import { UpgradeModal, PublishModal } from "../components/Modals.jsx";
import DownloadButton from "../components/DownloadButton.jsx";
import { PublishedTo, SocialIcon } from "../components/SocialIcon.jsx";

import { useSeo } from "../lib/seo.js";
const STATUS_LABEL = {
  queued: "Queued…",
  planning_story: "Planning story…",
  designing_characters: "Designing characters…",
  generating_scenes: "Generating scenes…",
  animating_scenes: "Animating scenes…",
  assembling_video: "Assembling video…",
  validating: "Validating…",
  script_ready: "📝 Script ready — tap to review",
  paused: "⏸ Paused — progress saved",
};

export default function Clips() {
  useSeo({
    title: "Your clips — BanterClips",
    description: "Every video you have generated, ready to publish or download.",
    path: "/clips",
    noindex: true,
  });

  const nav = useNavigate();
  const { clips, canDownload, refreshClips } = useApp();
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [publishClip, setPublishClip] = useState(null);
  const [error, setError] = useState("");

  // Always refetch on mount — jobs may have started elsewhere (Studio)
  // since the context last loaded the list.
  useEffect(() => {
    refreshClips();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep in-flight generations AND in-flight publishes live while this page
  // is open (publishing is async — the modal doesn't wait for it).
  const generating = clips.some(
    (c) => !["ready", "failed", "paused", "script_ready"].includes(c.status)
  );
  const publishing = clips.some((c) =>
    ["queued", "uploading"].includes(c.publishes?.[0]?.status)
  );
  useEffect(() => {
    if (!generating && !publishing) return;
    const t = setInterval(refreshClips, 1500);
    return () => clearInterval(t);
  }, [generating, publishing, refreshClips]);

  const retry = async (clip) => {
    try {
      await api.retryClip(clip.id);
      refreshClips();
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (clip) => {
    if (!window.confirm("Delete this clip permanently?")) return;
    try {
      await api.deleteClip(clip.id);
      refreshClips();
    } catch (e) {
      setError(e.message);
    }
  };

  if (clips.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "80px 20px", color: "var(--app-muted)" }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>🎬</div>
        <div style={{ fontSize: 18, fontWeight: 600, color: "var(--app-text)", marginBottom: 6 }}>No clips yet</div>
        <div style={{ fontSize: 14 }}>Head to Create and drop your first hot take.</div>
      </div>
    );
  }

  return (
    <div>
      {error && (
        <div style={{ fontSize: 13.5, color: "var(--app-error)", background: "rgba(240,84,108,.1)", borderRadius: 12, padding: "12px 16px", marginBottom: 16 }}>
          {error}
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(230px,1fr))", gap: 20 }}>
        {clips.map((c) => {
          const latestPub = c.publishes?.[0];
          const published = c.publishes?.some((p) => p.status === "published");
          const pubInFlight = ["queued", "uploading"].includes(latestPub?.status);
          const pubFailed = latestPub?.status === "failed";
          const inFlight = !["ready", "failed", "paused"].includes(c.status);
          return (
            <div key={c.id} className="card" style={{ overflow: "hidden", borderRadius: 16, display: "flex", flexDirection: "column" }}>
              {/* media frame: video covers the whole box, no gaps */}
              <div style={{ position: "relative", width: "100%", height: 300, background: c.thumb_gradient || "linear-gradient(160deg,#22d3ee,#3d2c8d)", overflow: "hidden" }}>
                {c.status === "ready" && c.video_url ? (
                  <video
                    src={c.video_url}
                    // A real frame instead of a black box before play, and it
                    // means the card shows the clip without downloading 12 MB.
                    poster={c.poster_url || undefined}
                    preload="none"
                    controls
                    playsInline
                    controlsList="nodownload noremoteplayback"
                    disablePictureInPicture
                    onContextMenu={(e) => e.preventDefault()}
                    onPlay={() => api.track("preview_played")}
                    style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
                  />
                ) : (
                  // Not watchable yet — the whole panel opens the clip in the
                  // Studio, where an in-flight one shows its live status and a
                  // failed one offers the free retry.
                  <div
                    role="button"
                    tabIndex={0}
                    title={inFlight ? "Watch progress" : "Open"}
                    onClick={() => nav(`/studio?clip=${c.id}`)}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && nav(`/studio?clip=${c.id}`)}
                    style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", cursor: "pointer", background: "radial-gradient(circle at 30% 15%,#ffffff22,transparent 55%)" }}
                  >
                    {inFlight ? (
                      <div style={{ textAlign: "center", color: "#fff" }}>
                        <span style={{ display: "inline-block", width: 26, height: 26, borderRadius: "50%", border: "3px solid rgba(255,255,255,.25)", borderTopColor: "#fff", animation: "spin 1s linear infinite" }} />
                        <div style={{ fontSize: 11.5, fontWeight: 600, marginTop: 8 }}>{c.current_step || STATUS_LABEL[c.status] || "Working…"}</div>
                        <div style={{ fontSize: 10.5, fontWeight: 600, marginTop: 6, opacity: 0.75 }}>Tap to watch progress →</div>
                      </div>
                    ) : c.status === "ready" ? (
                      // Finished but the video URL hasn't landed yet (storage
                      // hiccup) — this is not a failure, don't call it one.
                      <div style={{ textAlign: "center", color: "#fff", padding: "0 14px" }}>
                        <div style={{ fontSize: 12.5, fontWeight: 700 }}>🎬 Video is being prepared</div>
                        <div style={{ fontSize: 10.5, fontWeight: 600, marginTop: 6, opacity: 0.8 }}>Check back in a minute</div>
                      </div>
                    ) : c.status === "paused" ? (
                      <div style={{ textAlign: "center", color: "#fff", padding: "0 14px" }}>
                        <div style={{ fontSize: 12.5, fontWeight: 700 }}>⏸ Paused — provider credits low</div>
                        <div style={{ fontSize: 10.5, fontWeight: 600, marginTop: 6, opacity: 0.8 }}>
                          Progress saved · not charged · tap to resume
                        </div>
                      </div>
                    ) : (
                      <div style={{ textAlign: "center", color: "#fff", fontSize: 12.5, fontWeight: 700 }}>⚠️ Failed</div>
                    )}
                  </div>
                )}
                {c.status === "ready" && c.watermarked && (
                  <div style={{ position: "absolute", right: 8, bottom: 40, background: "rgba(0,0,0,.5)", color: "#fff", fontSize: 9, fontWeight: 700, padding: "3px 7px", borderRadius: 6, pointerEvents: "none" }}>
                    ▶ BanterClips
                  </div>
                )}
                <div style={{ position: "absolute", top: 10, left: 10, background: "rgba(0,0,0,.55)", color: "#fff", fontSize: 9.5, fontWeight: 700, padding: "3px 7px", borderRadius: 6, pointerEvents: "none" }}>
                  {c.sport} · {c.tone?.toUpperCase()}
                </div>
                {/* The uploaded reference, so it's always visible which photo
                    a clip was anchored to. Images only — a video ref gets its
                    full preview when the clip is opened. */}
                {c.reference_url && !c.reference_url.includes(".mp4") && (
                  <img
                    src={c.reference_url}
                    alt=""
                    title="Generated with a reference photo"
                    style={{ position: "absolute", top: 10, right: 10, width: 30, height: 30, borderRadius: "50%", objectFit: "cover", border: "2px solid rgba(255,255,255,.85)", pointerEvents: "none" }}
                  />
                )}
              </div>
              <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10, flex: 1 }}>
                {/* Fixed two-line title box so action rows align across cards.
                    Clicking it opens the clip in full — the whole take, its
                    status and its live steps — since two lines is not enough
                    to read a 280-character take. */}
                <div
                  role="button"
                  tabIndex={0}
                  title="Open this clip"
                  onClick={() => nav(`/studio?clip=${c.id}`)}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && nav(`/studio?clip=${c.id}`)}
                  style={{ fontSize: 14, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.35, minHeight: 38, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", cursor: "pointer" }}
                >
                  {c.take}
                </div>
                <div style={{ fontSize: 12, color: "var(--app-muted)", display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <span>
                    {c.status === "ready"
                      ? `${c.duration_seconds || 14}s`
                      : c.status === "failed"
                        ? "failed · retry is free"
                        : STATUS_LABEL[c.status]}
                  </span>
                  {c.status === "ready" && pubInFlight && (
                    <span style={{ color: "var(--app-cyan)", display: "inline-flex", alignItems: "center", gap: 5 }}>
                      <span style={{ width: 10, height: 10, borderRadius: "50%", border: "2px solid #12303d", borderTopColor: "var(--app-cyan)", animation: "spin 1s linear infinite", display: "inline-block" }} />
                      publishing to
                      <SocialIcon platform={latestPub?.platform} size={13} />…
                    </span>
                  )}
                  {/* Where it landed, as the platforms' own logos — each one
                      links straight to the live post. */}
                  {c.status === "ready" && !pubInFlight && published && (
                    <PublishedTo publishes={c.publishes} size={15} />
                  )}
                  {c.status === "ready" && !pubInFlight && !published && !pubFailed && <span>· not published yet</span>}
                  {c.status === "ready" && pubFailed && (
                    <span style={{ color: "var(--app-error)", fontWeight: 600 }}>· publish failed — retry below, it’s free</span>
                  )}
                </div>
                {c.status === "ready" && (
                  <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
                    <button
                      className="grad-btn"
                      style={{ flex: 1, height: 38, padding: 0, fontSize: 13, borderRadius: 9, whiteSpace: "nowrap", opacity: pubInFlight ? 0.55 : 1 }}
                      disabled={pubInFlight}
                      onClick={() => setPublishClip(c)}
                    >
                      {pubInFlight ? "Publishing…" : pubFailed ? "Retry publish" : "Publish"}
                    </button>
                    {canDownload ? (
                      <DownloadButton
                        clip={c}
                        className="ghost-btn"
                        compact
                        label="⬇ Download"
                        style={{ flex: 1, height: 38, padding: 0, fontSize: 13, borderRadius: 9, whiteSpace: "nowrap", color: "var(--app-text)" }}
                        onError={(e) => (e.status === 403 ? setUpgradeOpen(true) : setError(e.message))}
                      />
                    ) : (
                      // BR-08: visible-but-locked download is the upgrade prompt.
                      <button
                        title="Downloading in HD without the watermark is a Creator feature"
                        style={{
                          flex: 1, height: 38, padding: 0, fontSize: 12, borderRadius: 9, cursor: "pointer",
                          background: "transparent", border: "1px dashed var(--app-border)",
                          color: "var(--app-muted2)", display: "inline-flex", alignItems: "center",
                          justifyContent: "center", gap: 5, fontWeight: 600, whiteSpace: "nowrap",
                        }}
                        onClick={() => setUpgradeOpen(true)}
                      >
                        🔒 Download
                        <span style={{ fontSize: 8, fontWeight: 800, letterSpacing: ".04em", padding: "2px 5px", borderRadius: 999, background: "rgba(34,211,238,.12)", color: "var(--app-cyan)" }}>
                          CREATOR
                        </span>
                      </button>
                    )}
                  </div>
                )}
                {(c.status === "failed" || c.status === "paused") && (
                  <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
                    <button className="grad-btn" style={{ flex: 1, height: 38, padding: 0, fontSize: 13, borderRadius: 9 }} onClick={() => retry(c)}>
                      {c.status === "paused" ? "▶ Resume" : "↻ Retry free"}
                    </button>
                    <button className="ghost-btn" style={{ height: 38, padding: "0 14px", fontSize: 13, borderRadius: 9, color: "var(--app-muted)" }} onClick={() => remove(c)}>
                      🗑
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {upgradeOpen && <UpgradeModal reason="download" onClose={() => setUpgradeOpen(false)} />}
      {publishClip && <PublishModal clip={publishClip} onClose={() => setPublishClip(null)} />}
    </div>
  );
}
