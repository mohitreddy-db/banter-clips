import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import { SocialIcon } from "./SocialIcon.jsx";
import { YouTubeTerms } from "./YouTubeTerms.jsx";
import TikTokComposer, {
  emptyTikTokOptions,
  TikTokDeclaration,
  tiktokBlocker,
  toApiOptions,
} from "./TikTokComposer";

// How a publish attempt reads in the UI, per status.
const PUBLISH_STATE = {
  published: { text: "✓ Published", color: "var(--app-green)" },
  queued: { text: "Publishing…", color: "var(--app-cyan)" },
  uploading: { text: "Publishing…", color: "var(--app-cyan)" },
  failed: { text: "Failed — try again, it's free", color: "var(--app-error)" },
};

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
            {["Download in HD — no watermark", "Publish without the watermark", "Full HD 1080p quality", "500-character prompts", "30-second videos", "150 credits every month", "Priority render queue"].map((f) => (
              <div key={f} style={{ display: "flex", gap: 10, fontSize: 14, color: "var(--app-text)", fontWeight: 500 }}>
                <span style={{ color: "var(--app-green)", fontWeight: 700 }}>✓</span> {f}
              </div>
            ))}
          </div>
          {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}
          <button className="grad-btn" style={{ padding: 14, fontSize: 15.5 }} onClick={doUpgrade}>
            Upgrade to Creator — $19/mo
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
  const { instagram, tiktok, youtube, connectSocial, watermarked, refreshClips } = useApp();
  const [caption, setCaption] = useState(`${clip.take} 😤 #${clip.sport} #HotTake #BanterClips`);
  // TikTok post settings. Kept blank until the creator chooses — TikTok's UX
  // guidelines forbid pre-selecting an audience on their behalf.
  const [ttOptions, setTtOptions] = useState(emptyTikTokOptions);
  const [ttInfo, setTtInfo] = useState(null);
  const [ttLoading, setTtLoading] = useState(false);
  const [ttError, setTtError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  // Where this clip goes. Defaults to the first connected platform.
  const [platform, setPlatform] = useState(instagram ? "instagram" : tiktok ? "tiktok" : youtube ? "youtube" : "instagram");
  const PLATFORMS = [
    { key: "instagram", name: "Instagram", account: instagram, how: "publishes as a Reel" },
    { key: "tiktok", name: "TikTok", account: tiktok, how: "posts to your TikTok" },
    { key: "youtube", name: "YouTube", account: youtube, how: "uploads as a YouTube Short" },
  ];
  const selected = PLATFORMS.find((p) => p.key === platform);
  const connected = !!selected.account;

  // Live publish state for THIS clip. The dialog stays open after publishing:
  // it shows where the clip has landed, links to each live post, and lets the
  // user send it to the other platform (or the same one again) without
  // reopening anything. Publishing is async, so poll while any attempt runs.
  const [publishes, setPublishes] = useState(clip.publishes || []);
  const latestFor = (key) => publishes.find((p) => p.platform === key) || null;
  const anyInFlight = publishes.some((p) => ["queued", "uploading"].includes(p.status));

  useEffect(() => {
    if (!anyInFlight) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.getClip(clip.id);
        setPublishes(fresh.publishes || []);
        refreshClips();
      } catch {
        /* keep the last known status; the poll retries */
      }
    }, 4000);
    return () => clearInterval(timer);
  }, [anyInFlight, clip.id, refreshClips]);
  // TikTok requires `creator_info` immediately before each post, and the
  // composer is built from the answer — so load it whenever TikTok becomes
  // the selected destination, and again after connecting an account.
  const loadTikTok = useCallback(async () => {
    setTtLoading(true);
    setTtError("");
    try {
      setTtInfo(await api.tiktokCreatorInfo());
    } catch (e) {
      setTtInfo(null);
      setTtError(e.message || "Could not load your TikTok settings.");
    }
    setTtLoading(false);
  }, []);

  useEffect(() => {
    if (platform !== "tiktok" || !tiktok) return;
    loadTikTok();
  }, [platform, tiktok, loadTikTok]);

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
      await connectSocial(platform);
    } catch (e) {
      setError(e.message);
    }
    setConnecting(false);
  };

  // The upload runs server-side; the status panel below follows it live, so
  // the dialog stays open and the user can send the clip to the other
  // platform (or re-post it) without reopening anything.
  const publish = async () => {
    if (!selected.account) return;
    setError("");
    setSending(true);
    try {
      const pub = await api.publishClip(
        clip.id,
        selected.account.id,
        caption,
        selected.key === "tiktok" ? toApiOptions(ttOptions) : null
      );
      // Show it in flight at once; the poll above takes over from here.
      setPublishes((list) => [
        { ...pub, platform: selected.key, handle: selected.account.handle },
        ...list.filter((p) => p.platform !== selected.key),
      ]);
      refreshClips();
    } catch (e) {
      setError(e.message);
    }
    setSending(false);
  };

  const attempted = PLATFORMS.filter((p) => latestFor(p.key));
  const selectedPub = latestFor(platform);
  // TikTok is the one destination that can be connected and still not ready to
  // post: the audience is a required choice, and disclosure must be resolved.
  const ttBlocker = platform === "tiktok" && connected ? tiktokBlocker(ttOptions, ttInfo) : "";
  // TikTok's guidelines call the action "Post"; the rest of the product (and
  // the other two platforms) say "Publish". Follow each where it applies.
  const verb = platform === "tiktok" ? "Post" : "Publish";

  return (
    <Overlay onClose={onClose}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 20, color: "var(--app-text)" }}>Publish clip</div>
          {/* platform picker — two big tap targets, wraps on narrow screens */}
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {PLATFORMS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => { setPlatform(p.key); setError(""); }}
                style={{
                  flex: 1, minWidth: 140, display: "flex", alignItems: "center", gap: 10,
                  padding: "12px 14px", borderRadius: 12, cursor: "pointer", textAlign: "left",
                  background: platform === p.key ? "rgba(34,211,238,.10)" : "var(--app-panel)",
                  border: `1.5px solid ${platform === p.key ? "var(--app-cyan)" : "var(--app-border)"}`,
                }}
              >
                <SocialIcon platform={p.key} size={28} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--app-text)" }}>{p.name}</div>
                  {(() => {
                    const s = PUBLISH_STATE[latestFor(p.key)?.status];
                    const color = s ? s.color : p.account ? "var(--app-green)" : "var(--app-muted2)";
                    const text = s ? s.text : p.account ? `● ${p.account.handle}` : "Not connected";
                    return (
                      <div style={{ fontSize: 11, color, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {text}
                      </div>
                    );
                  })()}
                </div>
              </button>
            ))}
          </div>
          {/* Where this clip has already been — both platforms, live, with a
              link straight to each post. */}
          {attempted.length > 0 && (
            <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 10, padding: "12px 14px" }}>
              {attempted.map((p) => {
                const pub = latestFor(p.key);
                const s = PUBLISH_STATE[pub.status] || { text: pub.status, color: "var(--app-muted)" };
                return (
                  <div key={p.key} style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <SocialIcon platform={p.key} size={22} />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--app-text)" }}>
                        {p.name}{pub.handle ? ` · ${pub.handle}` : ""}
                      </div>
                      <div style={{ fontSize: 11.5, color: s.color, display: "flex", alignItems: "center", gap: 6 }}>
                        {["queued", "uploading"].includes(pub.status) && (
                          <span style={{ width: 9, height: 9, borderRadius: "50%", border: "2px solid #12303d", borderTopColor: "var(--app-cyan)", animation: "spin 1s linear infinite", display: "inline-block" }} />
                        )}
                        {s.text}
                      </div>
                    </div>
                    {pub.status === "published" && pub.external_url && (
                      <a href={pub.external_url} target="_blank" rel="noreferrer"
                         style={{ fontSize: 12.5, fontWeight: 700, color: "var(--app-cyan)", textDecoration: "none", whiteSpace: "nowrap" }}>
                        View post ↗
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {/* The picker above already names the destination and its handle,
              so a connected platform only needs the one-line "what happens".
              Not connected is the one case that still needs a panel + CTA. */}
          {connected ? (
            <div style={{ fontSize: 12, color: "var(--app-muted)", marginTop: -6 }}>
              Publishing to <b style={{ color: "var(--app-text)" }}>{selected.account.handle}</b> — {selected.how}.
            </div>
          ) : (
            <div className="panel" style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px" }}>
              <SocialIcon platform={selected.key} size={30} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--app-text)" }}>Connect {selected.name} to publish</div>
                {selected.key === "youtube" && <YouTubeTerms style={{ marginTop: 2 }} />}
              </div>
              <button className="grad-btn" style={{ padding: "8px 16px", fontSize: 13, borderRadius: 9, opacity: connecting ? 0.7 : 1 }} disabled={connecting} onClick={doConnect}>
                {connecting ? "Connecting…" : "Connect"}
              </button>
            </div>
          )}
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
              ℹ️ Free plan: your clip is published <b style={{ color: "var(--app-text)" }}>with the BanterClips watermark</b>. Upgrade to Creator to publish clean.
            </div>
          )}
          {/* TikTok's Content Sharing Guidelines require these controls, built
              from a live creator_info call, before a Direct Post is allowed. */}
          {platform === "tiktok" && connected && (
            <TikTokComposer
              info={ttInfo}
              loading={ttLoading}
              error={ttError}
              onRetry={loadTikTok}
              value={ttOptions}
              onChange={setTtOptions}
            />
          )}
          {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}
          {/* TikTok requires this consent line directly above the post button,
              and its wording follows the disclosure selection. */}
          {platform === "tiktok" && connected && ttInfo && <TikTokDeclaration value={ttOptions} />}
          {/* Publishing again is never blocked: a clip can go to any platform,
              and a post the user deleted is worth re-posting. */}
          <button
            className="grad-btn"
            style={{ padding: 14, fontSize: 15.5, opacity: sending || ttBlocker ? 0.7 : 1 }}
            disabled={!connected || sending || !!ttBlocker}
            onClick={publish}
          >
            {!connected
              ? `Connect ${selected.name} first`
              : ttBlocker
                ? ttBlocker
                : sending
                  ? "Sending…"
                  : selectedPub?.status === "published"
                    ? `${verb} to ${selected.name} again`
                    : ["queued", "uploading"].includes(selectedPub?.status)
                      ? `${verb}ing to ${selected.name}…`
                      : `${verb} to ${selected.name}`}
          </button>
          <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
            <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--app-muted)", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
              Done
            </button>
            <button onClick={() => { onClose(); nav("/clips"); }} style={{ background: "none", border: "none", color: "var(--app-cyan)", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
              Track in My Clips →
            </button>
          </div>
        </div>
    </Overlay>
  );
}
