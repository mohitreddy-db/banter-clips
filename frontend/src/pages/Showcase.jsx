import { useParams, useNavigate, Navigate, Link } from "react-router-dom";
import { useSeo, useJsonLd, SITE_URL } from "../lib/seo.js";
import { showcaseClips, findClip, videoUrl, posterUrl } from "../lib/showcase.js";

/* Public, indexable pages for the showcase clips — one URL per clip plus an
 * index. Before these existed the six videos lived only as <video> tags in the
 * landing-page strip: Google's live test reported "Video detected" but had no
 * title, thumbnail, duration or date for any of them, so none could surface in
 * video search. One clip per URL with VideoObject markup fixes that, and turns
 * every shared clip into a landing page instead of a dead-end file.
 *
 * Path is /showcase/:slug, NOT /clips/:slug — /clips is the gated user library.
 */

function Logo({ size = 26 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34">
      <defs>
        <linearGradient id="sclg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="1" stopColor="#34e27a" />
        </linearGradient>
      </defs>
      <rect width="34" height="34" rx="9" fill="url(#sclg)" />
      <path d="M13 10.5 L25 17 L13 23.5 Z" fill="#06121A" />
    </svg>
  );
}

/** Shared public chrome: top bar with sign-up CTA, footer with legal links. */
function PublicFrame({ children }) {
  const nav = useNavigate();
  return (
    <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "flex", flexDirection: "column" }}>
      <div style={{ borderBottom: "1px solid var(--app-border)", padding: "14px clamp(18px, 4vw, 28px)", display: "flex", alignItems: "center", gap: 12 }}>
        <div onClick={() => nav("/")} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
          <Logo />
          <span style={{ fontWeight: 700, fontSize: 17, color: "var(--app-text)" }}>BanterClips</span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
          <span onClick={() => nav("/signin")} style={{ cursor: "pointer", fontSize: 14, fontWeight: 600, color: "var(--app-muted)" }}>Sign in</span>
          <button className="grad-btn" style={{ padding: "10px 18px", fontSize: 13.5 }} onClick={() => nav("/signin")}>
            Start Creating Free
          </button>
        </div>
      </div>
      <div style={{ flex: 1 }}>{children}</div>
      <div style={{ borderTop: "1px solid var(--app-border)", padding: "22px clamp(18px, 4vw, 28px)", textAlign: "center", fontSize: 13, color: "var(--app-muted2)" }}>
        All videos are AI-generated parody. ·{" "}
        <a href="/pricing" style={{ color: "var(--app-muted)" }}>Pricing</a> ·{" "}
        <a href="/privacy" style={{ color: "var(--app-muted)" }}>Privacy</a> ·{" "}
        <a href="/terms" style={{ color: "var(--app-muted)" }}>Terms</a> ·{" "}
        <a href="https://www.google.com/preferences/source?q=banterclips.com" target="_blank" rel="noopener" style={{ color: "var(--app-muted)" }}>★ Prefer us on Google</a>
      </div>
    </div>
  );
}

function ClipCard({ clip, large = false }) {
  return (
    <Link
      to={`/showcase/${clip.slug}`}
      style={{
        position: "relative", borderRadius: 16, overflow: "hidden", aspectRatio: "9/16",
        background: `linear-gradient(160deg,${clip.c1},${clip.c2})`, display: "block", textDecoration: "none",
      }}
    >
      <img
        src={posterUrl(clip.slug)}
        alt={clip.cap}
        loading="lazy"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />
      <div style={{ position: "absolute", top: 10, left: 10, background: "#00000055", backdropFilter: "blur(4px)", color: "#fff", fontSize: 9.5, fontWeight: 800, padding: "3px 7px", borderRadius: 6 }}>
        {clip.sport}
      </div>
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to top,#000000b0 0%,transparent 55%)" }} />
      <div style={{ position: "absolute", left: 10, right: 10, bottom: 12, color: "#fff", fontWeight: 700, fontSize: large ? 15 : 13.5, lineHeight: 1.3, textShadow: "0 2px 10px #0008" }}>
        {clip.cap}
      </div>
    </Link>
  );
}

/** /showcase — the index. Links every clip page so crawlers find them all. */
export function ShowcaseIndex() {
  useSeo({
    title: "Made with BanterClips — AI sports video examples",
    description:
      "Real AI-generated sports clips, each made from a single written take — NBA and soccer parody videos with voiceover, lip-sync and animated captions.",
    path: "/showcase",
  });

  return (
    <PublicFrame>
      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "clamp(28px, 6vw, 48px) clamp(18px, 4vw, 28px) 56px" }}>
        <h1 style={{ fontSize: "clamp(26px, 6vw, 34px)", fontWeight: 800, color: "var(--app-text)", margin: "0 0 10px" }}>
          Made with BanterClips
        </h1>
        <p style={{ fontSize: 15.5, color: "var(--app-muted)", maxWidth: 620, lineHeight: 1.55, margin: "0 0 32px" }}>
          Every clip below started as one written sentence. The pipeline wrote the script, cast the
          scene, generated the voiceover and burned in the captions — these are the unedited results.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
          {showcaseClips.map((c) => (
            <ClipCard key={c.slug} clip={c} />
          ))}
        </div>
      </div>
    </PublicFrame>
  );
}

/** /showcase/:slug — one clip, one page, one VideoObject. */
export function ShowcaseClip() {
  const { slug } = useParams();
  const clip = findClip(slug);

  // Hooks before the unknown-slug bail-out (rules of hooks). An unknown slug
  // still calls them — with a throwaway noindex config — then redirects.
  useSeo(
    clip
      ? {
          title: `${clip.cap} — Made with BanterClips`,
          description: `${clip.sport} parody clip generated by BanterClips from the take: "${clip.cap}" — AI voiceover, lip-sync and animated captions, ready for Reels.`,
          path: `/showcase/${clip.slug}`,
          image: posterUrl(clip.slug),
        }
      : { noindex: true }
  );
  useJsonLd(
    "showcase-video",
    clip && {
      "@context": "https://schema.org",
      "@type": "VideoObject",
      name: clip.cap,
      description: clip.blurb,
      thumbnailUrl: posterUrl(clip.slug),
      contentUrl: videoUrl(clip.slug),
      uploadDate: clip.uploadDate,
      duration: clip.duration,
      url: `${SITE_URL}/showcase/${clip.slug}`,
      publisher: { "@id": `${SITE_URL}/#organization` },
    }
  );

  if (!clip) return <Navigate to="/showcase" replace />;
  const others = showcaseClips.filter((c) => c.slug !== clip.slug);

  return (
    <PublicFrame>
      <div className="showcase-detail" style={{ maxWidth: 980, margin: "0 auto", padding: "clamp(24px, 5vw, 44px) clamp(18px, 4vw, 28px) 56px" }}>
        <Link to="/showcase" style={{ fontSize: 13.5, fontWeight: 600, color: "var(--app-muted)", textDecoration: "none" }}>
          ← All examples
        </Link>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 340px) 1fr", gap: "clamp(22px, 4vw, 40px)", alignItems: "start", marginTop: 18 }} className="showcase-grid">
          <video
            src={videoUrl(clip.slug)}
            poster={posterUrl(clip.slug)}
            controls
            playsInline
            preload="metadata"
            style={{ width: "100%", aspectRatio: "9/16", borderRadius: 18, background: `linear-gradient(160deg,${clip.c1},${clip.c2})`, objectFit: "cover" }}
          />
          <div>
            <div style={{ display: "inline-block", background: "var(--app-surface)", border: "1px solid var(--app-border)", color: "var(--app-muted)", fontSize: 11.5, fontWeight: 800, padding: "4px 10px", borderRadius: 999, letterSpacing: ".05em", marginBottom: 14 }}>
              {clip.sport} · {clip.duration.replace("PT", "").toLowerCase()}
            </div>
            <h1 style={{ fontSize: "clamp(22px, 5vw, 30px)", fontWeight: 800, color: "var(--app-text)", lineHeight: 1.2, margin: "0 0 14px" }}>
              {clip.cap}
            </h1>
            <p style={{ fontSize: 15, color: "var(--app-muted)", lineHeight: 1.6, margin: "0 0 22px" }}>{clip.blurb}</p>
            <div style={{ background: "var(--app-surface)", border: "1px solid var(--app-border)", borderRadius: 14, padding: "16px 18px", marginBottom: 24 }}>
              <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--app-muted2)", marginBottom: 6 }}>
                The entire input
              </div>
              <div style={{ fontSize: 15.5, fontWeight: 600, color: "var(--app-text)" }}>“{clip.cap}”</div>
            </div>
            <Link to="/signin" className="grad-btn" style={{ display: "inline-block", padding: "13px 24px", fontSize: 15, textDecoration: "none" }}>
              Make one from your take →
            </Link>
            <div style={{ fontSize: 12.5, color: "var(--app-muted2)", marginTop: 10 }}>
              Free plan · no credit card · AI-generated parody
            </div>
          </div>
        </div>

        <h2 style={{ fontSize: 19, fontWeight: 800, color: "var(--app-text)", margin: "44px 0 16px" }}>More examples</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 14 }}>
          {others.map((c) => (
            <ClipCard key={c.slug} clip={c} />
          ))}
        </div>
      </div>
    </PublicFrame>
  );
}
