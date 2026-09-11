import { SocialIcon } from "./SocialIcon.jsx";
import { YouTubeTerms } from "./YouTubeTerms.jsx";

export const youtubeDefaults = (clip) => ({
  title: Array.from(clip?.take || "Untitled BanterClips video").slice(0, 100).join(""),
  description: `${clip?.take || ""} 😤 #${clip?.sport || "Sports"} #HotTake #BanterClips`,
  // Deliberately blank: YouTube's Required Minimum Functionality requires the
  // creator to choose public, private, or unlisted for every upload.
  privacy_status: "",
});

export const utf8Bytes = (value) => new TextEncoder().encode(value || "").length;
export const unicodeCharacters = (value) => Array.from(value || "").length;

export function youtubeBlocker(value) {
  const title = value?.title || "";
  const description = value?.description || "";
  if (!title.trim()) return "Add a YouTube title";
  if (unicodeCharacters(title) > 100) return "Shorten the YouTube title";
  if (title.includes("<") || title.includes(">")) return "Remove < or > from the title";
  if (utf8Bytes(description) > 5000) return "Shorten the YouTube description";
  if (description.includes("<") || description.includes(">")) return "Remove < or > from the description";
  if (!value?.privacy_status) return "Choose YouTube visibility";
  return "";
}

const VISIBILITY = [
  ["public", "Public", "Anyone can watch"],
  ["unlisted", "Unlisted", "Anyone with the link can watch"],
  ["private", "Private", "Only you and people you choose"],
];

export default function YouTubeComposer({ clip, account, value, onChange }) {
  const update = (patch) => onChange({ ...value, ...patch });
  const titleCharacters = unicodeCharacters(value.title);
  const descriptionBytes = utf8Bytes(value.description);
  const titleInvalid = value.title.includes("<") || value.title.includes(">");
  const descriptionInvalid = value.description.includes("<") || value.description.includes(">");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="panel" style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px" }}>
        <a href="https://www.youtube.com/" target="_blank" rel="noreferrer" title="Open YouTube" style={{ display: "inline-flex" }}>
          <SocialIcon platform="youtube" size={30} />
        </a>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--app-text)" }}>Review your YouTube upload</div>
          <div style={{ fontSize: 11.5, color: "var(--app-muted)", marginTop: 2 }}>
            Destination: {account?.handle || "the channel selected in Google"} · uploads as a Short
          </div>
        </div>
        {clip?.poster_url && (
          <img
            src={clip.poster_url}
            alt="Video thumbnail"
            style={{ width: 34, height: 52, objectFit: "cover", borderRadius: 7, border: "1px solid var(--app-border)" }}
          />
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        <label htmlFor="youtube-title" style={{ display: "flex", gap: 8, fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "var(--app-muted)" }}>
          TITLE <span style={{ marginLeft: "auto", letterSpacing: 0, color: titleCharacters > 100 || titleInvalid ? "var(--app-error)" : "var(--app-muted2)" }}>{titleCharacters}/100</span>
        </label>
        <input
          id="youtube-title"
          value={value.title}
          onChange={(event) => update({ title: event.target.value })}
          className="panel"
          placeholder="Video title"
          style={{ padding: "11px 13px", fontSize: 15, color: "var(--app-text)", background: "var(--app-panel)", width: "100%", boxSizing: "border-box" }}
        />
        {titleInvalid && <div style={{ fontSize: 11.5, color: "var(--app-error)" }}>YouTube titles cannot contain &lt; or &gt;.</div>}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        <label htmlFor="youtube-description" style={{ display: "flex", gap: 8, fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "var(--app-muted)" }}>
          DESCRIPTION <span style={{ marginLeft: "auto", letterSpacing: 0, color: descriptionBytes > 5000 || descriptionInvalid ? "var(--app-error)" : "var(--app-muted2)" }}>{descriptionBytes}/5000 bytes</span>
        </label>
        <textarea
          id="youtube-description"
          value={value.description}
          rows={4}
          onChange={(event) => update({ description: event.target.value })}
          className="panel"
          placeholder="Tell viewers about this video"
          style={{ padding: "11px 13px", fontSize: 14, lineHeight: 1.45, color: "var(--app-text)", resize: "vertical", background: "var(--app-panel)", width: "100%", boxSizing: "border-box" }}
        />
        {descriptionInvalid && <div style={{ fontSize: 11.5, color: "var(--app-error)" }}>YouTube descriptions cannot contain &lt; or &gt;.</div>}
      </div>

      <fieldset style={{ margin: 0, padding: 0, border: 0 }}>
        <legend style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "var(--app-muted)", marginBottom: 8 }}>
          VISIBILITY · CHOOSE ONE
        </legend>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
          {VISIBILITY.map(([key, label, detail]) => {
            const selected = value.privacy_status === key;
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => update({ privacy_status: key })}
                style={{
                  minHeight: 78,
                  padding: "10px 8px",
                  borderRadius: 11,
                  cursor: "pointer",
                  textAlign: "left",
                  background: selected ? "rgba(34,211,238,.10)" : "var(--app-panel)",
                  border: `1.5px solid ${selected ? "var(--app-cyan)" : "var(--app-border)"}`,
                }}
              >
                <span style={{ display: "block", color: selected ? "var(--app-cyan)" : "var(--app-text)", fontSize: 13, fontWeight: 700 }}>{selected ? "● " : "○ "}{label}</span>
                <span style={{ display: "block", color: "var(--app-muted2)", fontSize: 10.5, lineHeight: 1.35, marginTop: 5 }}>{detail}</span>
              </button>
            );
          })}
        </div>
      </fieldset>

      <div style={{ fontSize: 11.5, lineHeight: 1.5, color: "var(--app-muted2)" }}>
        BanterClips sends this exact title, description, and visibility only after you press Upload. The video is marked as containing synthetic media.
      </div>
      <YouTubeTerms />
    </div>
  );
}
