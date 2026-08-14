/** The spec we actually deliver — stated once, used everywhere.
 *
 * This exists because it already went wrong. The pipeline used to upscale
 * every clip to 1080x1920; when that stopped and delivery moved to the
 * generator's native size, four separate hardcoded "1080 × 1920" labels
 * across two pages quietly became false advertising. One constant means the
 * next resolution change updates the copy by itself.
 *
 * Keep in step with WIDTH/HEIGHT in backend/app/video/media.py.
 */
export const VIDEO_WIDTH = 720;
export const VIDEO_HEIGHT = 1280;

/** e.g. "720 × 1280" — note the real multiplication sign, not an "x". */
export const VIDEO_RES = `${VIDEO_WIDTH} × ${VIDEO_HEIGHT}`;

/** e.g. "720 × 1280 · 9:16" */
export const VIDEO_RES_RATIO = `${VIDEO_RES} · 9:16`;

/** Per-clip label now that resolution is a user choice: "1080p" → "1080 ×
 * 1920 · 9:16". Clips from before the choice existed fall back to the
 * constant above. Height mirrors the backend's even-floored 16:9 maths. */
export const resolutionLabel = (resolution) => {
  const w = parseInt(resolution, 10);
  if (!w) return VIDEO_RES_RATIO;
  return `${w} × ${Math.floor((w * 16) / 9 / 2) * 2} · 9:16`;
};

// Deliberately no frame rate here. Clips are copied through at whatever the
// generator produced (24fps today) and only re-encoded to a fixed rate on the
// fallback path, so any single number we printed would be wrong half the time.
