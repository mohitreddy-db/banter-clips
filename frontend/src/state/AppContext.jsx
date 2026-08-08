import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "../lib/api.js";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [booted, setBooted] = useState(false);
  const [user, setUser] = useState(null);
  const [usage, setUsage] = useState(null);
  const [clips, setClips] = useState([]);
  const [socials, setSocials] = useState([]);
  const [apiDown, setApiDown] = useState(false);

  const refreshUsage = useCallback(async () => {
    try {
      setUsage(await api.usage());
    } catch {
      /* keep last known usage */
    }
  }, []);

  const refreshClips = useCallback(async () => {
    try {
      setClips(await api.listClips());
    } catch {
      /* keep last known clips */
    }
  }, []);

  const refreshSocials = useCallback(async () => {
    try {
      setSocials(await api.listSocials());
    } catch {
      /* keep last known socials */
    }
  }, []);

  const loadAll = useCallback(async () => {
    const [me, u, c, s] = await Promise.all([
      api.me(),
      api.usage(),
      api.listClips(),
      api.listSocials(),
    ]);
    setUser(me);
    setUsage(u);
    setClips(c);
    setSocials(s);
  }, []);

  // Boot: restore the session if a token exists.
  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          await loadAll();
        } catch (e) {
          if (e.status === 401) clearToken();
          else if (e.status === 0) setApiDown(true);
        }
      }
      setBooted(true);
    })();
  }, [loadAll]);

  const signIn = useCallback(
    async (email) => {
      // Magic-link flow. DEV_MODE hands the token straight back so the demo
      // signs in without a mailbox; production emails a real link.
      const { dev_token } = await api.requestLink(email);
      if (!dev_token) throw new Error("Check your inbox for the sign-in link.");
      const session = await api.verify(dev_token);
      setToken(session.access_token);
      await loadAll();
      return session.user;
    },
    [loadAll]
  );

  const signOut = useCallback(() => {
    clearToken();
    setUser(null);
    setUsage(null);
    setClips([]);
    setSocials([]);
    window.location.href = "/";
  }, []);

  const savePreferences = useCallback(async (prefs) => {
    const saved = await api.updatePreferences(prefs);
    setUser((u) => (u ? { ...u, preferences: saved } : u));
    return saved;
  }, []);

  const upgrade = useCallback(async () => {
    await api.upgrade();
    const me = await api.me();
    setUser(me);
    await refreshUsage();
  }, [refreshUsage]);

  const cancelPlan = useCallback(async () => {
    await api.cancelPlan();
    setUser(await api.me());
  }, []);

  const connectSocial = useCallback(
    async (platform) => {
      const acc = await api.connectSocial(platform);
      await refreshSocials();
      return acc;
    },
    [refreshSocials]
  );

  const disconnectSocial = useCallback(
    async (platform) => {
      await api.disconnectSocial(platform);
      await refreshSocials();
    },
    [refreshSocials]
  );

  // Derived plan gating (client non-negotiable #1):
  //   Free  → publish-only (watermarked), no download.
  //   Paid  → download + publish without watermark.
  const plan = usage?.plan ?? user?.plan ?? "free";
  const limit = usage?.limit ?? (plan === "creator" ? 30 : 5);
  const used = usage?.used ?? 0;
  const left = usage?.left ?? Math.max(0, limit - used);
  const canDownload = usage?.can_download ?? plan === "creator";
  const watermarked = usage?.watermarked ?? plan !== "creator";

  const onboarded = !!user?.preferences?.onboarding_completed;
  const instagram = socials.find((s) => s.platform === "instagram") || null;

  const value = {
    booted,
    apiDown,
    user,
    signedIn: !!user,
    signIn,
    signOut,
    plan,
    used,
    limit,
    left,
    canDownload,
    watermarked,
    onboarded,
    profile: user?.preferences || { sports: [], teams: [], players: [], role: "" },
    savePreferences,
    upgrade,
    cancelPlan,
    clips,
    setClips,
    refreshClips,
    refreshUsage,
    socials,
    instagram,
    connected: !!instagram,
    connectSocial,
    disconnectSocial,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp outside provider");
  return ctx;
}
