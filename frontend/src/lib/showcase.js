/* The showcase catalog — real clips this pipeline produced, served from public
 * Supabase storage. Single source of truth for both the landing-page strip and
 * the public /showcase/:slug pages, so a clip added here appears in both.
 *
 * To add one: upload final.mp4 and poster.jpg under showcase/<slug>/ in the
 * clips bucket, then add a row here. `cap` is the take the clip was generated
 * from. `duration` is ISO-8601 (ffprobe the mp4); `uploadDate` comes from the
 * storage object's Last-Modified. Both feed the VideoObject structured data on
 * the clip's page — Google requires uploadDate, so don't guess it.
 * Remember to add the new URL to public/sitemap.xml as well.
 */

export const SHOWCASE_BASE =
  "https://taphbakizdagamimbhjh.supabase.co/storage/v1/object/public/clips/showcase";

export const videoUrl = (slug) => `${SHOWCASE_BASE}/${slug}/final.mp4`;
export const posterUrl = (slug) => `${SHOWCASE_BASE}/${slug}/poster.jpg`;

export const showcaseClips = [
  {
    // Leads the strip: the first clip made after kits stopped being banned,
    // and the only one showing legible "RONALDO 7" and a readable sign.
    slug: "ronaldo-penalties",
    sport: "Soccer",
    cap: "He takes penalties so the camera has somewhere to point.",
    blurb:
      "A penalty-box wind-up about Ronaldo's favourite way to score, staged as a broadcast moment — floodlights, a readable crowd sign, and the number 7 kit in frame. Generated from the one-line take above: script, casting, voiceover and captions are all the pipeline's work.",
    duration: "PT16S",
    uploadDate: "2026-08-13",
    c1: "#facc15",
    c2: "#1d4ed8",
  },
  {
    slug: "wemby-hide-and-seek",
    sport: "NBA",
    cap: "Seven foot four and Wemby still couldn't find Brunson.",
    blurb:
      "The height gap between Wembanyama and Brunson, played as a game of hide-and-seek in the paint. The take went in as one sentence; the scene, dialogue and lip-synced delivery came out the other end.",
    duration: "PT19S",
    uploadDate: "2026-08-13",
    c1: "#0f172a",
    c2: "#334155",
  },
  {
    slug: "wemby-roof",
    sport: "NBA",
    cap: "Wemby's so tall the Spurs just pass him the roof.",
    blurb:
      "A tall joke taken literally: San Antonio runs its offense through the ceiling. Sixteen seconds from a one-line take, with burned-in captions timed to the punchline so it lands muted.",
    duration: "PT16S",
    uploadDate: "2026-08-13",
    c1: "#2563eb",
    c2: "#0ea5e9",
  },
  {
    slug: "goat-debate",
    sport: "Soccer",
    cap: "Messi and Ronaldo argued so long they forgot to retire.",
    blurb:
      "The GOAT debate as its own explanation for two twenty-year careers. Both legends appear in their iconic kits, each speaking their own lines — the pipeline casts, scripts and voices every character from the single take above.",
    duration: "PT16S",
    uploadDate: "2026-08-13",
    c1: "#16a34a",
    c2: "#65a30d",
  },
  {
    slug: "spurs-collapse",
    sport: "NBA",
    cap: "Blowing a 29-point lead takes real commitment.",
    blurb:
      "A eulogy for a 29-point lead, delivered dead seriously — which is the joke. Written, voiced and cut by the pipeline from the caption above, in the tone the take deserved: savage.",
    duration: "PT16S",
    uploadDate: "2026-08-13",
    c1: "#111827",
    c2: "#4b5563",
  },
  {
    slug: "wemby-blocks",
    sport: "NBA",
    cap: "Wemby blocks everything except the losing streak.",
    blurb:
      "Wembanyama's block reel meets the standings. One sentence in, a finished 9:16 clip out — commentator voice, crowd noise and captions included, ready for Reels.",
    duration: "PT16S",
    uploadDate: "2026-08-13",
    c1: "#7c3aed",
    c2: "#db2777",
  },
];

export const findClip = (slug) => showcaseClips.find((c) => c.slug === slug);
