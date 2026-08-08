import { useEffect, useState } from "react";
import { useApp } from "../state/AppContext.jsx";
import { api, downloadClip } from "../lib/api.js";
import { UpgradeModal, PublishModal } from "../components/Modals.jsx";

const STATUS_LABEL = {
  queued: "Queued…",
  planning_story: "Planning story…",
  creating_voice: "Creating voice…",
  designing_characters: "Designing characters…",
  generating_scenes: "Generating scenes…",
  animating_scenes: "Animating scenes…",
  assembling_video: "Assembling video…",
  validating: "Validating…",
};

export default function Clips() {
  const { clips, canDownload, refreshClips } = useApp();
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [publishClip, setPublishClip] = useState(null);
  const [error, setError] = useState("");

  // Keep in-flight generations live while this page is open.
  const generating = clips.some((c) => c.status !== "ready" && c.status !== "failed");
  useEffect(() => {
    if (!generating) return;
    const t = setInterval(refreshClips, 1500);
    return () => clearInterval(t);
  }, [generating, refreshClips]);

  const download = async (clip) => {
    try {
      await downloadClip(clip);
    } catch (e) {
      if (e.status === 403) setUpgradeOpen(true);
      else setError(e.message);
    }
  };

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
          const published = c.publishes?.some((p) => p.status === "published");
          const inFlight = c.status !== "ready" && c.status !== "failed";
          return (
            <div key={c.id} className="card" style={{ overflow: "hidden", borderRadius: 16 }}>
              {/* media frame: fixed height, 9:16 video centered inside */}
              <div style={{ position: "relative", width: "100%", height: 300, background: "#080C16", display: "grid", placeItems: "center" }}>
                <div style={{ position: "relative", height: "100%", aspectRatio: "9/16", background: c.thumb_gradient || "linear-gradient(160deg,#22d3ee,#3d2c8d)", borderRadius: 4, overflow: "hidden" }}>
                  {c.status === "ready" && c.video_url ? (
                    <video
                      src={c.video_url}
                      controls
                      playsInline
                      controlsList="nodownload noremoteplayback"
                      disablePictureInPicture
                      onContextMenu={(e) => e.preventDefault()}
                      onPlay={() => api.track("preview_played")}
                      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  ) : (
                    <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", background: "radial-gradient(circle at 30% 15%,#ffffff22,transparent 55%)" }}>
                      {inFlight ? (
                        <div style={{ textAlign: "center", color: "#fff" }}>
                          <span style={{ display: "inline-block", width: 26, height: 26, borderRadius: "50%", border: "3px solid rgba(255,255,255,.25)", borderTopColor: "#fff", animation: "spin 1s linear infinite" }} />
                          <div style={{ fontSize: 11.5, fontWeight: 600, marginTop: 8 }}>{STATUS_LABEL[c.status] || "Working…"}</div>
                        </div>
                      ) : (
                        <div style={{ textAlign: "center", color: "#fff", fontSize: 12.5, fontWeight: 700 }}>⚠️ Failed</div>
                      )}
                    </div>
                  )}
                  {c.status === "ready" && c.watermarked && (
                    <div style={{ position: "absolute", right: 6, bottom: 38, background: "rgba(0,0,0,.5)", color: "#fff", fontSize: 9, fontWeight: 700, padding: "3px 7px", borderRadius: 6, pointerEvents: "none" }}>
                      ▶ BanterClips
                    </div>
                  )}
                </div>
                <div style={{ position: "absolute", top: 10, left: 10, background: "rgba(0,0,0,.55)", color: "#fff", fontSize: 9.5, fontWeight: 700, padding: "3px 7px", borderRadius: 6, pointerEvents: "none" }}>
                  {c.sport} · {c.tone?.toUpperCase()}
                </div>
              </div>
              <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.35 }}>{c.take}</div>
                <div style={{ fontSize: 12, color: "var(--app-muted)" }}>
                  {c.status === "ready"
                    ? `${c.duration_seconds || 14}s ${published ? "" : "· not published yet"}`
                    : c.status === "failed"
                      ? "failed · retry is free"
                      : STATUS_LABEL[c.status]}
                  {published && <span style={{ color: "var(--app-green)" }}> · published</span>}
                </div>
                {c.status === "ready" && (
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="grad-btn" style={{ flex: 1, padding: "9px 0", fontSize: 13, borderRadius: 9 }} onClick={() => setPublishClip(c)}>
                      ⤴ Publish
                    </button>
                    {canDownload ? (
                      <button className="ghost-btn" style={{ flex: 1, padding: "9px 0", fontSize: 13, borderRadius: 9, color: "var(--app-text)" }} onClick={() => download(c)}>
                        ⬇ Download
                      </button>
                    ) : (
                      // BR-08: visible-but-locked download is the upgrade prompt.
                      <button
                        title="Downloading in HD without the watermark is a Creator feature"
                        style={{
                          flex: 1, padding: "9px 0", fontSize: 12, borderRadius: 9, cursor: "pointer",
                          background: "transparent", border: "1px dashed var(--app-border)",
                          color: "var(--app-muted2)", display: "inline-flex", alignItems: "center",
                          justifyContent: "center", gap: 6, fontWeight: 600,
                        }}
                        onClick={() => setUpgradeOpen(true)}
                      >
                        🔒 Download
                        <span style={{ fontSize: 9, fontWeight: 800, letterSpacing: ".05em", padding: "2px 6px", borderRadius: 999, background: "rgba(34,211,238,.12)", color: "var(--app-cyan)" }}>
                          CREATOR
                        </span>
                      </button>
                    )}
                  </div>
                )}
                {c.status === "failed" && (
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="grad-btn" style={{ flex: 1, padding: "9px 0", fontSize: 13, borderRadius: 9 }} onClick={() => retry(c)}>
                      ↻ Retry free
                    </button>
                    <button className="ghost-btn" style={{ padding: "9px 14px", fontSize: 13, borderRadius: 9, color: "var(--app-muted)" }} onClick={() => remove(c)}>
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
