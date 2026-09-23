import { useState } from "react";
import { downloadClip } from "../lib/api.js";

const mb = (bytes) => `${(bytes / 1048576).toFixed(1)} MB`;

/**
 * Download, with the wait made visible. A clip is 5-20 MB and the file only
 * reaches the browser's save prompt once every byte has arrived — on a phone
 * that gap is long enough that the button reads as broken. This fills it in
 * with real received bytes, and falls back to an indeterminate bar when the
 * server sends no content-length.
 */
export default function DownloadButton({
  clip, onError, label = "⬇ Download", className = "ghost-btn", style,
  compact = false,
}) {
  const [dl, setDl] = useState(null);

  const start = async () => {
    if (dl) return;
    setDl({ received: 0, total: 0, pct: 0 });
    try {
      await downloadClip(clip, setDl);
      // Let "Saved" register before the button goes back to its idle label.
      setTimeout(() => setDl(null), 1400);
    } catch (e) {
      setDl(null);
      onError?.(e);
    }
  };

  // `compact` is for the side-by-side buttons on a clip card, which are only
  // ~110px wide: "Downloading… 82%" overflowed and the progress bar's own
  // overflow:hidden clipped it mid-number ("Downloading… 8").
  const progress = dl?.pct === null ? mb(dl.received) : `${dl?.pct}%`;
  const text = !dl
    ? label
    : dl.pct === 100
      ? "✓ Saved"
      : compact
        ? `⬇ ${progress}`
        : `Downloading… ${progress}`;

  return (
    <button
      className={className}
      disabled={!!dl}
      onClick={start}
      title={dl ? `Downloading… ${progress}` : "Save this clip as an MP4"}
      style={{
        position: "relative", overflow: "hidden",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        ...style, opacity: 1,
      }}
    >
      {dl && (
        <span
          aria-hidden="true"
          style={{
            position: "absolute", left: 0, top: 0, bottom: 0,
            width: dl.pct === null ? "100%" : `${dl.pct}%`,
            background: dl.pct === 100 ? "rgba(52,226,122,.22)" : "rgba(34,211,238,.20)",
            transition: "width .2s linear",
            animation: dl.pct === null ? "pulseGlow 1.2s ease-in-out infinite" : "none",
          }}
        />
      )}
      <span style={{ position: "relative", whiteSpace: "nowrap", padding: "0 8px" }}>{text}</span>
    </button>
  );
}
