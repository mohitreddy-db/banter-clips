import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";

function Overlay({ children, onClose }) {
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 100, background: "rgba(4,6,12,.72)", backdropFilter: "blur(6px)", display: "grid", placeItems: "center", padding: 20, animation: "fadeUp .2s ease both" }}
    >
      <div onClick={(e) => e.stopPropagation()} className="card app-font" style={{ width: "100%", maxWidth: 440, padding: 28 }}>
        {children}
      </div>
    </div>
  );
}

export function UpgradeModal({ onClose, reason }) {
  const { upgrade, startCheckout } = useApp();
  const [state, setState] = useState("offer"); // offer | paying | done
  const [error, setError] = useState("");

  const doUpgrade = async () => {
    setState("paying");
    setError("");
    api.track("upgrade_started");
    try {
      // Stripe Checkout (hosted page). Null → Stripe not configured → dev mock.
      const url = await startCheckout();
      if (url) {
        window.location.href = url;
        return;
      }
      await Promise.all([upgrade(), new Promise((r) => setTimeout(r, 1400))]);
      setState("done");
    } catch (e) {
      setError(e.message);
      setState("offer");
    }
  };

  return (
    <Overlay onClose={() => state === "offer" && onClose(false)}>
      {state === "offer" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: 16, background: "rgba(34,211,238,.12)", display: "grid", placeItems: "center", fontSize: 24 }}>🔓</div>
          <div style={{ fontWeight: 700, fontSize: 21, color: "var(--app-text)" }}>
            {reason === "download" ? "Downloading is a Creator feature" : reason === "limit" ? "You've hit this month's limit" : "Go Creator"}
          </div>
          <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.55 }}>
            On the Free plan you publish with the BanterClips watermark — every post promotes you <i>and</i> us. Creator unlocks the full kit:
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            {["Download in HD — no watermark", "Publish without the watermark", "30 videos a month (vs 5)", "Priority render queue"].map((f) => (
              <div key={f} style={{ display: "flex", gap: 10, fontSize: 14, color: "var(--app-text)", fontWeight: 500 }}>
                <span style={{ color: "var(--app-green)", fontWeight: 700 }}>✓</span> {f}
              </div>
            ))}
          </div>
          {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}
          <button className="grad-btn" style={{ padding: 14, fontSize: 15.5 }} onClick={doUpgrade}>
            Upgrade to Creator — $9.99/mo
          </button>
          <button onClick={() => onClose(false)} style={{ background: "none", border: "none", color: "var(--app-muted)", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
            Maybe later
          </button>
        </div>
      )}
      {state === "paying" && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "22px 0", textAlign: "center" }}>
          <div style={{ width: 34, height: 34, borderRadius: "50%", border: "3px solid #12303d", borderTopColor: "#22d3ee", animation: "spin 1s linear infinite" }} />
          <div style={{ fontWeight: 600, fontSize: 16, color: "var(--app-text)" }}>Opening secure Stripe checkout…</div>
          <div style={{ fontSize: 12.5, color: "var(--app-muted)" }}>Beta mode — no card will be charged.</div>
        </div>
      )}
      {state === "done" && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, padding: "12px 0", textAlign: "center" }}>
          <div style={{ width: 60, height: 60, borderRadius: 18, background: "rgba(52,226,122,.14)", display: "grid", placeItems: "center", fontSize: 26 }}>🎉</div>
          <div style={{ fontWeight: 700, fontSize: 20, color: "var(--app-text)" }}>Welcome to Creator</div>
          <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.5 }}>
            Watermark-free downloads and publishing are now unlocked.
          </div>
          <button className="grad-btn" style={{ padding: "13px 26px", fontSize: 15 }} onClick={() => onClose(true)}>
            Continue
          </button>
        </div>
      )}
    </Overlay>
  );
}

export function PublishModal({ clip, onClose }) {
  const nav = useNavigate();
  const { instagram, connected, connectSocial, watermarked, refreshClips } = useApp();
  const [caption, setCaption] = useState(`${clip.take} 😤 #${clip.sport} #HotTake #BanterClips`);
  const [state, setState] = useState("compose"); // compose | queued
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");

  const doConnect = async () => {
    setConnecting(true);
    setError("");
    try {
      await connectSocial("instagram");
    } catch (e) {
      setError(e.message);
    }
    setConnecting(false);
  };

  // Fire-and-forget: the upload runs server-side; My Clips shows live status.
  const publish = async () => {
    if (!instagram) return;
    setError("");
    try {
      await api.publishClip(clip.id, instagram.id, caption);
      refreshClips();
      setState("queued");
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <Overlay onClose={() => state !== "publishing" && onClose()}>
      {state === "compose" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 20, color: "var(--app-text)" }}>Publish to Instagram</div>
          <div className="panel" style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px" }}>
            <div style={{ width: 30, height: 30, borderRadius: "50%", background: "linear-gradient(140deg,#7b2ff7,#f0546c)" }} />
            {connected ? (
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--app-text)" }}>Instagram · {instagram.handle}</div>
                <div style={{ fontSize: 11.5, color: "var(--app-green)" }}>● Connected — publishes as a Reel</div>
              </div>
            ) : (
              <>
                <div style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: "var(--app-text)" }}>Connect Instagram to publish</div>
                <button className="grad-btn" style={{ padding: "8px 16px", fontSize: 13, borderRadius: 9, opacity: connecting ? 0.7 : 1 }} disabled={connecting} onClick={doConnect}>
                  {connecting ? "Connecting…" : "Connect"}
                </button>
              </>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1, color: "var(--app-muted)" }}>CAPTION</label>
            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={3}
              className="panel"
              style={{ padding: "12px 14px", fontSize: 14, color: "var(--app-text)", resize: "vertical", background: "var(--app-panel)" }}
            />
          </div>
          {watermarked && (
            <div style={{ fontSize: 12.5, color: "var(--app-muted)", background: "rgba(34,211,238,.07)", borderRadius: 10, padding: "10px 12px", lineHeight: 1.5 }}>
              ℹ️ Free plan: your Reel is published <b style={{ color: "var(--app-text)" }}>with the BanterClips watermark</b>. Upgrade to Creator to publish clean.
            </div>
          )}
          {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}
          <button className="grad-btn" style={{ padding: 14, fontSize: 15.5 }} disabled={!connected} onClick={publish}>
            {connected ? "Publish now" : "Connect Instagram first"}
          </button>
        </div>
      )}
      {state === "queued" && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, padding: "12px 0", textAlign: "center" }}>
          <div style={{ width: 60, height: 60, borderRadius: 18, background: "rgba(34,211,238,.12)", display: "grid", placeItems: "center", fontSize: 26 }}>🚀</div>
          <div style={{ fontWeight: 700, fontSize: 20, color: "var(--app-text)" }}>Publishing in the background</div>
          <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.55 }}>
            Your Reel is uploading to Instagram{watermarked ? " (with watermark)" : ""}. Track live status in
            <b style={{ color: "var(--app-text)" }}> My Clips</b> — you can keep creating meanwhile.
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="ghost-btn" style={{ padding: "11px 18px", fontSize: 14 }} onClick={() => onClose()}>
              Done
            </button>
            <button className="grad-btn" style={{ padding: "11px 18px", fontSize: 14 }} onClick={() => { onClose(); nav("/clips"); }}>
              Track in My Clips →
            </button>
          </div>
        </div>
      )}
    </Overlay>
  );
}
