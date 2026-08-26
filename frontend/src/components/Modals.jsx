import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";

function Overlay({ children, onClose }) {
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 100, background: "rgba(4,6,12,.72)", backdropFilter: "blur(6px)", display: "grid", placeItems: "center", padding: 16, animation: "fadeUp .2s ease both" }}
    >
      <div onClick={(e) => e.stopPropagation()} className="card app-font modal-card" style={{ width: "100%", maxWidth: 440, padding: 28 }}>
        {children}
      </div>
    </div>
  );
}

/**
 * Top Up Credits — the ONLY thing offered when a balance runs short
 * (PRICING rule 2: top up, never upgrade). Packs come from the server so
 * admin price changes appear without a release. Credits are granted by the
 * Stripe webhook after payment, not on redirect.
 */
export function TopUpModal({ onClose, needed = 0 }) {
  const { credits } = useApp();
  const [packs, setPacks] = useState(null);
  const [available, setAvailable] = useState(true);
  const [buying, setBuying] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.packs()
      .then((d) => { setPacks(d.packs || []); setAvailable(d.available); })
      .catch(() => { setPacks([]); setAvailable(false); });
  }, []);

  const buy = async (key) => {
    setBuying(key);
    setError("");
    api.track("topup_pack_clicked", { pack: key });
    try {
      const { url } = await api.topup(key);
      window.location.href = url;
    } catch (e) {
      setError(e.message);
      setBuying("");
    }
  };

  const short = needed > 0 && credits < needed;
  return (
    <Overlay onClose={() => !buying && onClose()}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ fontWeight: 700, fontSize: 21, color: "var(--app-text)" }}>⚡ Top Up Credits</div>
        <div style={{ fontSize: 13.5, color: "var(--app-muted)", lineHeight: 1.5 }}>
          {short
            ? <>This video needs <b style={{ color: "var(--app-text)" }}>{needed}</b> credits — you have <b style={{ color: "var(--app-text)" }}>{credits.toLocaleString()}</b>. Top-up credits never expire.</>
            : <>You have <b style={{ color: "var(--app-text)" }}>{credits.toLocaleString()}</b> credits. Top-up credits never expire.</>}
        </div>

        {packs === null && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="shimmer" style={{ height: 104, borderRadius: 14, border: "1px solid var(--app-border)" }} />
            ))}
          </div>
        )}
        {packs !== null && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {packs.map((p) => (
              <button
                key={p.key}
                onClick={() => buy(p.key)}
                disabled={!!buying || !available}
                style={{
                  position: "relative", display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
                  padding: "18px 10px 14px", borderRadius: 14, cursor: available ? "pointer" : "not-allowed",
                  background: "var(--app-surface)",
                  border: `1.5px solid ${p.popular ? "var(--app-cyan)" : "var(--app-border)"}`,
                  opacity: buying && buying !== p.key ? 0.5 : 1,
                }}
              >
                {p.popular && (
                  <span style={{ position: "absolute", top: -9, right: 10, fontSize: 9.5, fontWeight: 800, letterSpacing: ".05em", padding: "3px 9px", borderRadius: 999, background: "var(--app-cyan)", color: "#04121a" }}>
                    POPULAR
                  </span>
                )}
                <span style={{ fontSize: 24, fontWeight: 800, color: "var(--app-text)" }}>
                  {buying === p.key ? "…" : p.credits.toLocaleString()}
                </span>
                <span style={{ fontSize: 11.5, color: "var(--app-muted)" }}>credits</span>
                <span style={{ fontSize: 15.5, fontWeight: 700, color: "var(--app-cyan)", marginTop: 6 }}>
                  ${p.usd.toFixed(2)}
                </span>
              </button>
            ))}
          </div>
        )}

        {!available && packs !== null && (
          <div style={{ fontSize: 12.5, color: "var(--app-muted)" }}>Payments aren't configured on this server.</div>
        )}
        {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}
        <div style={{ fontSize: 11.5, color: "var(--app-muted2)", textAlign: "center" }}>
          Secure payment via Stripe. Your card details never touch our servers.
        </div>
        <button onClick={() => !buying && onClose()} style={{ background: "none", border: "none", color: "var(--app-muted)", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
          Close
        </button>
      </div>
    </Overlay>
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
            {["Download in HD — no watermark", "Publish without the watermark", "Full HD 1080p quality", "30-second videos", "150 credits every month", "Priority render queue"].map((f) => (
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
  // Written captions to pick between. Three options beat a blank box, and
  // beat one suggestion — a list gets chosen from, a single one gets ignored.
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(true);
  // Everything shown so far — sent back on regenerate so new options are new.
  const seenRef = useRef([]);

  const fetchSuggestions = useCallback(
    async (regenerate = false) => {
      setLoadingSuggestions(true);
      try {
        const { captions } = await api.captionSuggestions(
          clip.id, regenerate ? seenRef.current : []
        );
        if (captions?.length) {
          seenRef.current = [...seenRef.current, ...captions];
          setSuggestions(captions);
          setCaption((current) =>
            // Follow along unless the user typed their own caption.
            !regenerate || seenRef.current.includes(current) || current === ""
              ? captions[0]
              : current
          );
        }
      } catch {
        /* suggestions are a nicety — the box still works without them */
      } finally {
        setLoadingSuggestions(false);
      }
    },
    [clip.id]
  );

  useEffect(() => {
    fetchSuggestions(false);
  }, [fetchSuggestions]);

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
              style={{ padding: "12px 14px", fontSize: 16, color: "var(--app-text)", resize: "vertical", background: "var(--app-panel)", width: "100%", boxSizing: "border-box" }}
            />
            {(loadingSuggestions || suggestions.length > 0) && (
              <div style={{ display: "flex", flexDirection: "column", gap: 7, paddingTop: 2 }}>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: 0.8, color: "var(--app-muted2)" }}>
                    {loadingSuggestions ? "WRITING SUGGESTIONS…" : "OR PICK ONE"}
                  </span>
                  {!loadingSuggestions && suggestions.length > 0 && (
                    <button
                      type="button"
                      onClick={() => fetchSuggestions(true)}
                      title="Write three new caption suggestions"
                      style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "var(--app-cyan)", fontSize: 12, fontWeight: 600, padding: 0, display: "inline-flex", alignItems: "center", gap: 5 }}
                    >
                      ↻ New suggestions
                    </button>
                  )}
                </div>
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setCaption(s)}
                    title="Use this caption"
                    style={{
                      textAlign: "left", padding: "9px 12px", borderRadius: 10, cursor: "pointer",
                      fontSize: 13, lineHeight: 1.45,
                      color: caption === s ? "var(--app-text)" : "var(--app-muted)",
                      background: caption === s ? "rgba(34,211,238,.10)" : "transparent",
                      border: `1px solid ${caption === s ? "var(--app-cyan)" : "var(--app-border)"}`,
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
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
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
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
