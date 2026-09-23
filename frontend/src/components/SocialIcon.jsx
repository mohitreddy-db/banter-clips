import instagramLogo from "../assets/instagram.svg";
import tiktokLogo from "../assets/tiktok.svg";
import youtubeLogo from "../assets/youtube.png";

/**
 * Official platform artwork, served from the repo — no CDN or runtime request.
 * The YouTube PNG is the unmodified red digital icon from the Core YouTube
 * Icon package at https://brand.youtube/youtube-icon (downloaded 2026-09-12).
 */

const LOGOS = { instagram: instagramLogo, tiktok: tiktokLogo, youtube: youtubeLogo };
const NAMES = { instagram: "Instagram", tiktok: "TikTok", youtube: "YouTube" };

export const platformName = (platform) => NAMES[platform] || platform || "";

export function SocialIcon({ platform, size = 24, title, style }) {
  const src = LOGOS[platform];
  if (!src) return null;
  // Google's review report requires every YouTube mark to be at least 20dp.
  // Use 24 CSS px as the floor so the approved asset and its clear space never
  // collapse below that threshold in compact status rows.
  const renderedSize = platform === "youtube" ? Math.max(24, size) : size;
  return (
    <img
      src={src}
      alt={NAMES[platform]}
      title={title || NAMES[platform]}
      width={renderedSize}
      height={renderedSize}
      style={{
        display: "block",
        flexShrink: 0,
        objectFit: "contain",
        borderRadius: platform === "youtube" ? 0 : Math.round(renderedSize * 0.26),
        ...style,
      }}
    />
  );
}

/**
 * "Published to [logo] [logo]" — one logo per platform this clip actually
 * reached, each linking to the live post when the platform gave us a URL.
 * Renders nothing when the clip has never published, so callers can drop it
 * in unconditionally.
 */
export function PublishedTo({ publishes, size = 24, label = "Published to", style }) {
  const done = (publishes || []).filter((p) => p.status === "published");
  if (!done.length) return null;
  // Newest publish wins per platform (the API returns newest first), so a
  // re-publish updates the link rather than adding a second logo.
  const byPlatform = new Map();
  for (const p of done) if (p.platform && !byPlatform.has(p.platform)) byPlatform.set(p.platform, p);

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, ...style }}>
      {label ? <span style={{ color: "var(--app-green)", fontWeight: 600 }}>{label}</span> : null}
      {[...byPlatform.values()].map((p) => {
        // Branding rules require a YouTube mark to link to YouTube content (or
        // the in-app component). After the 30-day API-data purge removes the
        // video's URL, keep the mark linked to YouTube itself.
        const href = p.external_url || (p.platform === "youtube" ? "https://www.youtube.com/" : "");
        return href ? (
          <a
            key={p.platform}
            href={href}
            target="_blank"
            rel="noreferrer"
            title={`${p.external_url ? "View post on" : "Open"} ${platformName(p.platform)} ↗`}
            onClick={(e) => e.stopPropagation()}
            style={{ display: "inline-flex", lineHeight: 0 }}
          >
            <SocialIcon platform={p.platform} size={size} />
          </a>
        ) : (
          <SocialIcon key={p.platform} platform={p.platform} size={size} />
        );
      })}
    </span>
  );
}
