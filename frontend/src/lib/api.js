// Thin API client for the BanterClips backend.
// VITE_API_URL points at the FastAPI server (droplet in prod, :8000 locally).

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
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
  createClip: (take, sport, tone) =>
    request("/clips", { method: "POST", body: { take, sport, tone } }),
  getClip: (id) => request(`/clips/${id}`),
  retryClip: (id) => request(`/clips/${id}/retry`, { method: "POST" }),
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

  // billing (mock Stripe for now)
  upgrade: () => request("/billing/upgrade", { method: "POST" }),
  cancelPlan: () => request("/billing/cancel", { method: "POST" }),

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
