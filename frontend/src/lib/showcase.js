/* The showcase catalog — clips this pipeline produced, served from public
 * Supabase storage. Single source of truth for both the landing-page strip and
 * the public /showcase/:slug pages, so a clip added here appears in both.
 *
 * Currently empty; see the note on `showcaseClips`.
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
  // Empty on purpose. Every clip here starred a real athlete or manager — an
  // AI Mbappé in a Real Madrid press room, a Mourinho impression, Klay
  // Thompson in Heat colours — which is what App Review rejected under
  // guideline 4.1(a), and the same exposure applied on the web. The clips are
  // hosted remotely, so removing the rows is what takes them off the site.
  //
  // To put the strip back: generate clips with the current,
  // original-character catalog (backend/app/video/catalog/), upload
  // final.mp4 + poster.jpg under showcase/<slug>/, add a row here, and add
  // the URL to public/sitemap.xml. Every surface reads this list and hides
  // itself while it is empty.
];

export const findClip = (slug) => showcaseClips.find((c) => c.slug === slug);
