// Thin API client for the BanterClips backend.
// VITE_API_URL points at the FastAPI server (droplet in prod, :8000 locally).

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const API_BASE = BASE;
const TOKEN_KEY = "banterclips-session";

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request(path, { method = "GET", body } = {}) {
  const headers = { "content-type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the BanterClips server. Is the backend running?");
  }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    const code = typeof detail === "object" ? detail?.code : undefined;
    const message =
      (typeof detail === "object" ? detail?.message : detail) ||
      data?.message ||
      `Request failed (${res.status})`;
    throw new ApiError(res.status, code, message);
  }
  return data;
}

// Build a querystring, dropping empty/undefined values.
const qs = (params = {}) => {
  const pairs = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== ""
  );
  if (!pairs.length) return "";
  return `?${new URLSearchParams(pairs).toString()}`;
};

export const api = {
  // auth
  exchangeSupabase: (access_token) =>
    request("/auth/supabase", { method: "POST", body: { access_token } }),
  // dev-only fallback (backend returns 404 unless DEV_MODE)
  requestLink: (email, display_name) =>
    request("/auth/request-link", { method: "POST", body: { email, display_name } }),
  verify: (token) => request("/auth/verify", { method: "POST", body: { token } }),

  // me
  me: () => request("/me"),
  usage: () => request("/me/usage"),
  updatePreferences: (prefs) => request("/me/preferences", { method: "PATCH", body: prefs }),

  // clips
  listClips: () => request("/clips"),
  // Sharpens the take and returns what still needs asking. Cheap and
  // read-only, so it is safe to call again after every answer.
  enhanceTake: (take, sport, tone, duration, answers = {}) =>
    request("/clips/enhance", { method: "POST", body: { take, sport, tone, duration, answers } }),
  // Two fresh variations of a take, for the input page. Repeatable: `round`
  // only widens the search so repeat presses give new ideas.
  enhanceTakeVariations: (take, sport, tone, round = 0) =>
    request("/clips/enhance-take", { method: "POST", body: { take, sport, tone, round } }),
  // Trending feed for the create page. Cheap: served from a shared
  // 20-minute server cache per sport.
  trending: (sport) => request(`/clips/trending?sport=${encodeURIComponent(sport)}`),
  // `sports` and `subjects` are optional hints — the server infers the sport
  // from the take when nothing is picked.
  createClip: (take, sports = [], tone, duration = 15, resolution = "720p", subjects = []) =>
    request("/clips", {
      method: "POST",
      body: { take, sports, subjects, tone, duration, resolution },
    }),
  getClip: (id) => request(`/clips/${id}`),
  // Three written caption options to pick between when publishing.
  captionSuggestions: (id, avoid = []) =>
    request(`/clips/${id}/captions${avoid.length ? `?avoid=${encodeURIComponent(avoid.join("\n"))}` : ""}`),
  retryClip: (id) => request(`/clips/${id}/retry`, { method: "POST" }),
  // Script approval: nothing renders (or costs) until the script is approved.
  approveScript: (id) => request(`/clips/${id}/script/approve`, { method: "POST" }),
  // Edit dialogue/actions before approving; lines are fitted server-side.
  updateScript: (id, body) => request(`/clips/${id}/script`, { method: "PATCH", body }),
  regenerateScript: (id, feedback = "") =>
    request(`/clips/${id}/script/regenerate`, { method: "POST", body: { feedback } }),
  deleteClip: (id) => request(`/clips/${id}`, { method: "DELETE" }),

  // publishing
  publishClip: (clipId, social_account_id, caption) =>
    request(`/clips/${clipId}/publish`, { method: "POST", body: { social_account_id, caption } }),
  getPublish: (clipId, publishId) => request(`/clips/${clipId}/publishes/${publishId}`),

  // socials
  listSocials: () => request("/socials"),
  // Real OAuth consent URL for a platform (instagram | tiktok); 503 when
  // that platform's app isn't configured server-side.
  oauthUrl: (platform, next) => request(`/socials/${platform}/oauth-url?next=${encodeURIComponent(next || "/account")}`),
  connectSocial: (platform) => request("/socials/connect", { method: "POST", body: { platform } }),
  disconnectSocial: (platform) => request(`/socials/${platform}`, { method: "DELETE" }),

  // billing — Stripe Checkout when configured, mock upgrade as dev fallback
  // Credit top-ups: pack list + one-time Checkout (credits granted by webhook).
  packs: () => request("/billing/packs"),
  topup: (pack) => request("/billing/topup", { method: "POST", body: { pack } }),
  checkout: () => request("/billing/checkout", { method: "POST" }),
  billingPortal: () => request("/billing/portal", { method: "POST" }),
  upgrade: () => request("/billing/upgrade", { method: "POST" }),
  cancelPlan: () => request("/billing/cancel", { method: "POST" }),

  // admin — 404s for non-admins by design
  adminCatalog: () => request("/admin/catalog"),
  adminCreateCharacter: (body) => request("/admin/catalog", { method: "POST", body }),
  adminUpdateCharacter: (id, body) => request(`/admin/catalog/${id}`, { method: "PATCH", body }),
  adminStills: (id) => request(`/admin/catalog/${id}/stills`),
  // Generates candidate stills (~$0.10); nothing is applied until approved.
  adminGenerateStills: (id, notes = "") =>
    request(`/admin/catalog/${id}/references`, { method: "POST", body: { notes } }),
  adminApproveStills: (id, still_ids) =>
    request(`/admin/catalog/${id}/references`, { method: "PUT", body: { still_ids } }),
  adminResearch: (id) => request(`/admin/catalog/${id}/research`, { method: "POST" }),

  // admin console — aggregate + action endpoints (see backend admin_console.py)
  adminOverview: (days = 7) => request(`/admin/overview${qs({ days })}`),
  adminUsers: (params = {}) => request(`/admin/users${qs(params)}`),
  adminUserDetail: (id) => request(`/admin/users/${id}`),
  adminBlockUser: (id, blocked, reason = "") =>
    request(`/admin/users/${id}/block`, { method: "POST", body: { blocked, reason } }),
  adminDeleteUser: (id, confirm_email, reason = "") =>
    request(`/admin/users/${id}/delete`, { method: "POST", body: { confirm_email, reason } }),
  adminRetention: (weeks = 5) => request(`/admin/retention${qs({ weeks })}`),
  adminVideos: (params = {}) => request(`/admin/videos${qs(params)}`),
  adminVideoDetail: (id) => request(`/admin/videos/${id}`),
  adminVideoRetry: (id, reason = "") =>
    request(`/admin/videos/${id}/retry`, { method: "POST", body: { reason } }),
  adminVideoDelete: (id, reason = "") =>
    request(`/admin/videos/${id}/delete`, { method: "POST", body: { reason } }),
  adminJobs: () => request("/admin/jobs"),
  adminJobRetry: (id, reason = "") =>
    request(`/admin/jobs/${id}/retry`, { method: "POST", body: { reason } }),
  adminJobCancel: (id, reason = "") =>
    request(`/admin/jobs/${id}/cancel`, { method: "POST", body: { reason } }),
  adminSpendSettings: () => request("/admin/settings/spend"),
  adminSaveSpendSettings: (body) => request("/admin/settings/spend", { method: "PUT", body }),
  adminCosts: (days = 7) => request(`/admin/costs${qs({ days })}`),
  adminRevenue: () => request("/admin/revenue"),
  adminPublishing: () => request("/admin/publishing"),
  adminPublishRetry: (id, reason = "") =>
    request(`/admin/publishes/${id}/retry`, { method: "POST", body: { reason } }),
  adminAudit: (params = {}) => request(`/admin/audit${qs(params)}`),
  adminAdmins: () => request("/admin/admins"),
  adminAddAdmin: (email, reason) =>
    request("/admin/admins/add", { method: "POST", body: { email, reason } }),
  adminRemoveAdmin: (email, reason) =>
    request("/admin/admins/remove", { method: "POST", body: { email, reason } }),
  adminCredits: () => request("/admin/credits"),
  adminGrantCredits: (email, delta, reason) =>
    request("/admin/credits/grant", { method: "POST", body: { email, delta, reason } }),
  adminSaveCreditSettings: (body) =>
    request("/admin/settings/credits", { method: "PUT", body }),

  // analytics (fire-and-forget)
  track: (name, props = {}) =>
    request("/events", { method: "POST", body: { name, props } }).catch(() => {}),
};

// Downloads need the Authorization header, so fetch as a blob.
export async function downloadClip(clip, onProgress) {
  // A clip is 5-20 MB, so on a phone the gap between tapping Download and the
  // browser's own download prompt is long enough to read as a dead button.
  // The body is streamed rather than awaited as one blob so `onProgress` can
  // report real bytes ({received, total, pct}); pct is null when the server
  // sent no content-length, and callers show an indeterminate bar.
  onProgress?.({ received: 0, total: 0, pct: 0 });
  const res = await fetch(`${BASE}/clips/${clip.id}/download`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = data?.detail;
    throw new ApiError(
      res.status,
      typeof detail === "object" ? detail?.code : undefined,
      (typeof detail === "object" ? detail?.message : detail) || "Download failed"
    );
  }
  const total = Number(res.headers.get("content-length")) || 0;
  let blob;
  if (res.body?.getReader) {
    const reader = res.body.getReader();
    const chunks = [];
    let received = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.length;
      onProgress?.({
        received,
        total,
        pct: total ? Math.min(99, Math.round((received / total) * 100)) : null,
      });
    }
    blob = new Blob(chunks, { type: res.headers.get("content-type") || "video/mp4" });
  } else {
    blob = await res.blob();   // no streaming support: still downloads fine
  }
  onProgress?.({ received: blob.size, total: blob.size, pct: 100 });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `banterclips-${clip.sport.toLowerCase()}-${clip.id.slice(0, 8)}.mp4`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
