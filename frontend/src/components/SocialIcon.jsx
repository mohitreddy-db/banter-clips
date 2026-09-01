import instagramLogo from "../assets/instagram.svg";
import tiktokLogo from "../assets/tiktok.svg";

/**
 * The real platform logos, served from the repo (src/assets/*.svg) — no CDN,
 * no external request, brand colours baked into the file. Used anywhere a
 * platform is named, so "Instagram" and "TikTok" always look like themselves.
 */

const LOGOS = { instagram: instagramLogo, tiktok: tiktokLogo };
const NAMES = { instagram: "Instagram", tiktok: "TikTok", youtube: "YouTube" };

export const platformName = (platform) => NAMES[platform] || platform || "";

export function SocialIcon({ platform, size = 20, title, style }) {
  if (platform === "youtube") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" role="img" aria-label="YouTube" title={title || "YouTube"} style={{ display: "block", flexShrink: 0, ...style }}>
        <rect x="2" y="5" width="20" height="14" rx="4" fill="#ff0033" />
        <path d="m10 9 5 3-5 3Z" fill="#fff" />
      </svg>
    );
  }
  const src = LOGOS[platform];
  if (!src) return null;
  return (
    <img
      src={src}
      alt={NAMES[platform]}
      title={title || NAMES[platform]}
      width={size}
      height={size}
      style={{ display: "block", flexShrink: 0, borderRadius: Math.round(size * 0.26), ...style }}
    />
  );
}

/**
 * "Published to [logo] [logo]" — one logo per platform this clip actually
 * reached, each linking to the live post when the platform gave us a URL.
 * Renders nothing when the clip has never published, so callers can drop it
 * in unconditionally.
 */
export function PublishedTo({ publishes, size = 16, label = "Published to", style }) {
  const done = (publishes || []).filter((p) => p.status === "published");
  if (!done.length) return null;
  // Newest publish wins per platform (the API returns newest first), so a
  // re-publish updates the link rather than adding a second logo.
  const byPlatform = new Map();
  for (const p of done) if (p.platform && !byPlatform.has(p.platform)) byPlatform.set(p.platform, p);

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, ...style }}>
      {label ? <span style={{ color: "var(--app-green)", fontWeight: 600 }}>{label}</span> : null}
      {[...byPlatform.values()].map((p) =>
        p.external_url ? (
          <a
            key={p.platform}
            href={p.external_url}
            target="_blank"
            rel="noreferrer"
            title={`View post on ${platformName(p.platform)} ↗`}
            onClick={(e) => e.stopPropagation()}
            style={{ display: "inline-flex", lineHeight: 0 }}
          >
            <SocialIcon platform={p.platform} size={size} />
          </a>
        ) : (
          <SocialIcon key={p.platform} platform={p.platform} size={size} />
        )
      )}
    </span>
  );
}
