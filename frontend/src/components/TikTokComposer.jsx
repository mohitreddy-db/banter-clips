/**
 * TikTok post settings — the composer TikTok's Content Sharing Guidelines
 * require before a Direct Post.
 *
 * Every control here exists because the audit checks for it, and the rules are
 * stricter than they look:
 *
 * - The audience selector has NO default. TikTok treats a pre-selected privacy
 *   level as the app choosing for the creator, which is a rejection.
 * - The options come from `creator_info`, not from a hardcoded list. A private
 *   account is never offered "Everyone".
 * - Comment / Duet / Stitch start OFF and are disabled — with a reason — when
 *   the creator's own TikTok settings forbid them.
 * - Commercial content disclosure is off by default; turning it on forces a
 *   choice between "Your brand" and "Branded content", and branded content
 *   cannot be posted privately.
 * - The consent declaration sits directly above the post button and its
 *   wording changes with the disclosure selection.
 *
 * `emptyTikTokOptions`, `tiktokBlocker` and `toApiOptions` keep those rules in
 * one place so the dialog and the request agree about what is postable.
 */

const MUSIC_URL = "https://www.tiktok.com/legal/page/global/music-usage-confirmation/en";
const BRANDED_URL = "https://www.tiktok.com/legal/page/global/bc-policy/en";

const PRIVACY_LABELS = {
  PUBLIC_TO_EVERYONE: "Everyone",
  MUTUAL_FOLLOW_FRIENDS: "Friends",
  FOLLOWER_OF_CREATOR: "Followers",
  SELF_ONLY: "Only me",
};

export const emptyTikTokOptions = () => ({
  // Deliberately blank: the creator picks, we never pre-select.
  privacy_level: "",
  allow_comment: false,
  allow_duet: false,
  allow_stitch: false,
  disclose: false,
  brand_organic: false,
  branded_content: false,
});

/** What the API takes — `disclose` is the UI's toggle, not a TikTok field. */
export const toApiOptions = (v) => ({
  privacy_level: v.privacy_level,
  allow_comment: v.allow_comment,
  allow_duet: v.allow_duet,
  allow_stitch: v.allow_stitch,
  brand_organic: v.disclose && v.brand_organic,
  branded_content: v.disclose && v.branded_content,
});

/** Why posting is not allowed yet, or "" when it is. Drives the button. */
export function tiktokBlocker(v, info) {
  if (!info) return "Loading your TikTok settings…";
  if (!v.privacy_level) return "Choose who can view this video";
  if (v.disclose && !v.brand_organic && !v.branded_content)
    return "Pick what this video promotes";
  if (v.disclose && v.branded_content && v.privacy_level === "SELF_ONLY")
    return "Branded content cannot be private";
  return "";
}

const label = { fontSize: 11, fontWeight: 600, letterSpacing: 1, color: "var(--app-muted)" };
const hint = { fontSize: 11.5, color: "var(--app-muted2)", lineHeight: 1.45 };

function Check({ checked, disabled, onChange, title, children, note }) {
  return (
    <label
      title={title}
      style={{
        display: "flex", gap: 10, alignItems: "flex-start", cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.45 : 1,
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        style={{ marginTop: 2, width: 16, height: 16, accentColor: "var(--app-cyan)", colorScheme: "dark", cursor: "inherit" }}
      />
      <span style={{ minWidth: 0 }}>
        <span style={{ fontSize: 13.5, color: "var(--app-text)" }}>{children}</span>
        {note && <span style={{ ...hint, display: "block" }}>{note}</span>}
      </span>
    </label>
  );
}

function Switch({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      style={{
        width: 40, height: 23, borderRadius: 999, position: "relative", flexShrink: 0, cursor: "pointer",
        background: checked ? "var(--app-cyan)" : "var(--app-border)",
        border: "none", padding: 0, transition: "background .15s",
      }}
    >
      <span
        style={{
          position: "absolute", top: 3, left: checked ? 20 : 3, width: 17, height: 17, borderRadius: "50%",
          background: "#fff", transition: "left .15s",
        }}
      />
    </button>
  );
}

/** The consent line TikTok requires immediately above the post button. */
export function TikTokDeclaration({ value }) {
  const branded = value.disclose && value.branded_content;
  return (
    <div style={{ ...hint, textAlign: "center" }}>
      By posting, you agree to TikTok's{" "}
      {branded && (
        <>
          <a href={BRANDED_URL} target="_blank" rel="noreferrer" style={{ color: "var(--app-cyan)" }}>
            Branded Content Policy
          </a>{" "}
          and{" "}
        </>
      )}
      <a href={MUSIC_URL} target="_blank" rel="noreferrer" style={{ color: "var(--app-cyan)" }}>
        Music Usage Confirmation
      </a>
      .
    </div>
  );
}

export default function TikTokComposer({ info, loading, error, onRetry, value, onChange }) {
  const set = (patch) => onChange({ ...value, ...patch });

  if (loading) {
    return (
      <div className="panel" style={{ padding: "12px 14px", fontSize: 12.5, color: "var(--app-muted)" }}>
        Loading your TikTok settings…
      </div>
    );
  }
  if (error) {
    return (
      <div className="panel" style={{ padding: "12px 14px", display: "flex", gap: 12, alignItems: "center" }}>
        <div style={{ flex: 1, fontSize: 12.5, color: "var(--app-error)" }}>{error}</div>
        <button
          type="button"
          onClick={onRetry}
          style={{ background: "none", border: "none", color: "var(--app-cyan)", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}
        >
          Retry
        </button>
      </div>
    );
  }
  if (!info) return null;

  // Branded content must be visible to someone, so TikTok forbids pairing it
  // with "Only me". Grey the option out rather than letting the post fail.
  const brandedOn = value.disclose && value.branded_content;
  const disclosureLabel = brandedOn
    ? "Paid partnership"
    : value.disclose && value.brand_organic
      ? "Promotional content"
      : "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* Who is posting — the audit expects the creator to be identifiable. */}
      <div className="panel" style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px" }}>
        {info.avatar_url ? (
          <img
            src={info.avatar_url}
            alt=""
            width={34}
            height={34}
            style={{ borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
          />
        ) : (
          <div style={{ width: 34, height: 34, borderRadius: "50%", background: "var(--app-border)", flexShrink: 0 }} />
        )}
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--app-text)" }}>
            {info.nickname || "Your TikTok account"}
          </div>
          {info.username && info.username !== (info.nickname || "").replace(/^@/, "") && (
            <div style={hint}>@{info.username}</div>
          )}
        </div>
      </div>

      {info.unaudited && (
        <div style={{ fontSize: 12.5, color: "var(--app-muted)", background: "rgba(34,211,238,.07)", borderRadius: 10, padding: "10px 12px", lineHeight: 1.5 }}>
          ℹ️ BanterClips is under TikTok's app review. Until it clears, TikTok
          accepts posts only as <b style={{ color: "var(--app-text)" }}>Only me</b>, and only from a
          private TikTok account — any other audience is rejected.
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        <label htmlFor="tt-privacy" style={label}>
          WHO CAN VIEW THIS VIDEO
        </label>
        <select
          id="tt-privacy"
          value={value.privacy_level}
          onChange={(e) => set({ privacy_level: e.target.value })}
          className="panel"
          style={{
            padding: "11px 12px", fontSize: 14, width: "100%", boxSizing: "border-box",
            color: value.privacy_level ? "var(--app-text)" : "var(--app-muted2)",
            background: "var(--app-panel)", colorScheme: "dark", cursor: "pointer",
          }}
        >
          <option value="" disabled>
            Select who can view this video
          </option>
          {info.privacy_level_options.map((p) => (
            <option key={p} value={p} disabled={brandedOn && p === "SELF_ONLY"}>
              {PRIVACY_LABELS[p] || p}
              {brandedOn && p === "SELF_ONLY" ? " — not available for branded content" : ""}
            </option>
          ))}
        </select>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        <span style={label}>ALLOW USERS TO</span>
        <Check
          checked={value.allow_comment}
          disabled={info.comment_disabled}
          onChange={(allow_comment) => set({ allow_comment })}
          title={info.comment_disabled ? "You have turned comments off in your TikTok settings" : undefined}
        >
          Comment
        </Check>
        <Check
          checked={value.allow_duet}
          disabled={info.duet_disabled}
          onChange={(allow_duet) => set({ allow_duet })}
          title={info.duet_disabled ? "You have turned Duet off in your TikTok settings" : undefined}
        >
          Duet
        </Check>
        <Check
          checked={value.allow_stitch}
          disabled={info.stitch_disabled}
          onChange={(allow_stitch) => set({ allow_stitch })}
          title={info.stitch_disabled ? "You have turned Stitch off in your TikTok settings" : undefined}
        >
          Stitch
        </Check>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--app-text)" }}>Disclose video content</div>
            <div style={hint}>
              Turn on to disclose that this video promotes goods or services in exchange for
              something of value. Your video could promote yourself, a third party, or both.
            </div>
          </div>
          <Switch
            checked={value.disclose}
            onChange={(disclose) =>
              // Clearing the sub-choices on the way off keeps the request and
              // the visible state from ever disagreeing.
              set(disclose ? { disclose } : { disclose, brand_organic: false, branded_content: false })
            }
          />
        </div>
        {value.disclose && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingLeft: 2 }}>
            <Check
              checked={value.brand_organic}
              onChange={(brand_organic) => set({ brand_organic })}
              note="You are promoting yourself or your own business. This video will be classified as Brand Organic."
            >
              Your brand
            </Check>
            <Check
              checked={value.branded_content}
              onChange={(branded_content) =>
                set(
                  // Branded content and "Only me" cannot coexist; drop the
                  // audience so the creator re-picks rather than being blocked
                  // by a selection they can no longer see.
                  branded_content && value.privacy_level === "SELF_ONLY"
                    ? { branded_content, privacy_level: "" }
                    : { branded_content }
                )
              }
              note="You are promoting another brand or a third party. This video will be classified as Branded Content."
            >
              Branded content
            </Check>
            {disclosureLabel && (
              <div style={{ fontSize: 12.5, color: "var(--app-muted)", background: "rgba(34,211,238,.07)", borderRadius: 10, padding: "10px 12px", lineHeight: 1.5 }}>
                Your video will be labeled "<b style={{ color: "var(--app-text)" }}>{disclosureLabel}</b>".
                This cannot be changed once you post.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
