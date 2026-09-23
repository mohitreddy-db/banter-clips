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
    // Leads the strip: the strongest thing the pipeline has produced — a real
    // Real Madrid press room, Mourinho's likeness and mannerisms, and a
    // legible "FOR DEFENSE ONLY" prop it invented and rendered cleanly.
    slug: "mbappe-cone-drills",
    sport: "Soccer",
    cap: "Mbappé just turned Real Sociedad's defense into cone drills.",
    blurb:
      "A press-conference bit built on a real week in Madrid: Mbappé fields questions in the club's own media room while Mourinho works the crowd with a hand-lettered \"FOR DEFENSE ONLY\" sign. Casting, script, dialogue, voices and captions all came from the single line above — including the joke prop.",
    duration: "PT18S",
    uploadDate: "2026-08-29",
    c1: "#1e3a8a",
    c2: "#7c3aed",
  },
  {
    slug: "lewis-skelly-vs-yamal",
    sport: "Soccer",
    cap: "Lewis-Skelly is as good as Yamal — so where's the fuss?",
    blurb:
      "Two 19-year-olds, one argument. Lamine Yamal in the Barcelona kit and Myles Lewis-Skelly in Arsenal red make the case on a training pitch, with \"MLS\" whiteboards as the running gag. The pipeline researched both players before writing a word.",
    duration: "PT17S",
    uploadDate: "2026-08-29",
    c1: "#a50044",
    c2: "#004d98",
  },
  {
    slug: "arsenal-trust-the-process",
    sport: "Soccer",
    cap: "Arsenal bottled the title again and the fans still say trust the process.",
    blurb:
      "Confetti on the pitch, a \"TRUST THE PROCESS\" banner and Arteta talking his squad through another almost. Eleven words of take became four shots, three characters and a punchline delivered to camera.",
    duration: "PT16S",
    uploadDate: "2026-08-29",
    c1: "#ef4444",
    c2: "#1f2937",
  },
  {
    slug: "arsenal-undefeated-2026",
    sport: "Soccer",
    cap: "Arsenal fans are acting undefeated — give it two weeks.",
    blurb:
      "One game into the season and the banner is already printed. Face paint, a cardboard crown and Arteta handing out tissues at the Emirates — the tone dial was set to Savage and the script came back accordingly.",
    duration: "PT17S",
    uploadDate: "2026-08-29",
    c1: "#dc2626",
    c2: "#0f172a",
  },
  {
    slug: "klay-south-beach",
    sport: "NBA",
    cap: "Klay Thompson and Spoelstra might cook up Heat basketball that makes Giannis sweat.",
    blurb:
      "Miami in the sun: a fan sprinting down the boardwalk, a tactics board on the sand and Klay in Heat colours. Twelve seconds, one take, and a voice that sounds like it actually believes it.",
    duration: "PT12S",
    uploadDate: "2026-08-29",
    c1: "#f97316",
    c2: "#0891b2",
  },
  {
    slug: "mourinho-mop-meltdown",
    sport: "Soccer",
    cap: "Mourinho at Real Madrid again? I'm rehearsing my sideline meltdowns with a mop.",
    blurb:
      "A fan rehearsing for the return of the Special One, mop in hand, while Mourinho runs his own touchline theatre in the background. Absurd, committed and entirely generated — props, blocking and all.",
    duration: "PT17S",
    uploadDate: "2026-08-29",
    c1: "#facc15",
    c2: "#111827",
  },
];

export const findClip = (slug) => showcaseClips.find((c) => c.slug === slug);
