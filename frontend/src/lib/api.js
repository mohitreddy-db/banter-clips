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
  createClip: (take, sport, tone, duration = 15, resolution = "720p") =>
    request("/clips", { method: "POST", body: { take, sport, tone, duration, resolution } }),
  getClip: (id) => request(`/clips/${id}`),
  // Three written caption options to pick between when publishing.
  captionSuggestions: (id, avoid = []) =>
    request(`/clips/${id}/captions${avoid.length ? `?avoid=${encodeURIComponent(avoid.join("\n"))}` : ""}`),
  retryClip: (id) => request(`/clips/${id}/retry`, { method: "POST" }),
  // Script approval: nothing renders (or costs) until the script is approved.
  approveScript: (id) => request(`/clips/${id}/script/approve`, { method: "POST" }),
  regenerateScript: (id, feedback = "") =>
    request(`/clips/${id}/script/regenerate`, { method: "POST", body: { feedback } }),
  deleteClip: (id) => request(`/clips/${id}`, { method: "DELETE" }),

  // publishing
  publishClip: (clipId, social_account_id, caption) =>
    request(`/clips/${clipId}/publish`, { method: "POST", body: { social_account_id, caption } }),
  getPublish: (clipId, publishId) => request(`/clips/${clipId}/publishes/${publishId}`),

  // socials
  listSocials: () => request("/socials"),
  igOauthUrl: (next) => request(`/socials/instagram/oauth-url?next=${encodeURIComponent(next || "/account")}`),
  connectSocial: (platform) => request("/socials/connect", { method: "POST", body: { platform } }),
  disconnectSocial: (platform) => request(`/socials/${platform}`, { method: "DELETE" }),

  // billing — Stripe Checkout when configured, mock upgrade as dev fallback
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

  // analytics (fire-and-forget)
  track: (name, props = {}) =>
    request("/events", { method: "POST", body: { name, props } }).catch(() => {}),
};

// Downloads need the Authorization header, so fetch as a blob.
export async function downloadClip(clip) {
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
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `banterclips-${clip.sport.toLowerCase()}-${clip.id.slice(0, 8)}.mp4`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
