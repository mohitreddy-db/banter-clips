import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "../lib/api.js";
import { supabase, supabaseEnabled, urlIsPasswordRecovery } from "../lib/supabase.js";

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

  // Trade a Supabase access token for a BanterClips API session.
  const exchange = useCallback(
    async (supabaseAccessToken) => {
      const session = await api.exchangeSupabase(supabaseAccessToken);
      setToken(session.access_token);
      await loadAll();
      return session.user;
    },
    [loadAll]
  );

  // Real auth (Supabase): email + password.
  const signUp = useCallback(
    async (email, password, displayName) => {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { display_name: displayName || email.split("@")[0] },
          emailRedirectTo: `${window.location.origin}/signin`,
        },
      });
      if (error) throw new Error(error.message);
      // With email confirmation enabled there is no session yet.
      if (!data.session) return { needsConfirmation: true };
      return { user: await exchange(data.session.access_token) };
    },
    [exchange]
  );

  const signInPassword = useCallback(
    async (email, password) => {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw new Error(error.message);
      return exchange(data.session.access_token);
    },
    [exchange]
  );

  // Google via Supabase OAuth. Full-page redirect to Google; on return the
  // onAuthStateChange listener below exchanges the session automatically.
  const signInWithGoogle = useCallback(async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/signin` },
    });
    if (error) throw new Error(error.message);
  }, []);

  // Password reset (also how a Google-signup account adds a password):
  // email link → /reset-password → updatePassword() in the recovery session.
  const resetPassword = useCallback(async (email) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    if (error) throw new Error(error.message);
  }, []);

  const updatePassword = useCallback(async (password) => {
    const { error } = await supabase.auth.updateUser({ password });
    if (error) throw new Error(error.message);
  }, []);

  const sendMagicLink = useCallback(async (email) => {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/signin` },
    });
    if (error) throw new Error(error.message);
  }, []);

  // Dev fallback when Supabase isn't configured (backend DEV_MODE only).
  const devSignIn = useCallback(
    async (email) => {
      const { dev_token } = await api.requestLink(email);
      if (!dev_token) throw new Error("Check your inbox for the sign-in link.");
      const session = await api.verify(dev_token);
      setToken(session.access_token);
      await loadAll();
      return session.user;
    },
    [loadAll]
  );

  // When the user lands back from a confirmation / magic-link / Google OAuth
  // redirect, Supabase picks the session out of the URL — exchange it for an
  // API session. If Supabase dropped us on a public page (its redirect
  // allow-list can fall back to the Site URL → landing), forward into the app.
  useEffect(() => {
    if (!supabaseEnabled) return;
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      // A recovery link must land on the reset form, no matter where the
      // Supabase redirect allow-list dropped us.
      if (session && urlIsPasswordRecovery && window.location.pathname !== "/reset-password") {
        window.location.replace("/reset-password");
        return;
      }
      if (event === "SIGNED_IN" && session && !getToken()) {
        exchange(session.access_token)
          .then((u) => {
            if (urlIsPasswordRecovery) return;
            if (["/", "/signin"].includes(window.location.pathname)) {
              window.location.replace(
                u?.preferences?.onboarding_completed ? "/studio" : "/onboarding"
              );
            }
          })
          .catch(() => {});
      }
    });
    return () => sub.subscription.unsubscribe();
  }, [exchange]);

  const signOut = useCallback(() => {
    clearToken();
    if (supabaseEnabled) supabase.auth.signOut().catch(() => {});
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

  const refreshUser = useCallback(async () => {
    setUser(await api.me());
    await refreshUsage();
  }, [refreshUsage]);

  // Real path: Stripe Checkout — returns a URL to redirect the browser to.
  // Falls back to the dev mock upgrade when Stripe isn't configured (503).
  const startCheckout = useCallback(async () => {
    try {
      const { url } = await api.checkout();
      return url;
    } catch (e) {
      if (e.status === 503) return null; // caller uses the mock path
      throw e;
    }
  }, []);

  const upgrade = useCallback(async () => {
    await api.upgrade();
    await refreshUser();
  }, [refreshUser]);

  const cancelPlan = useCallback(async () => {
    await api.cancelPlan();
    setUser(await api.me());
  }, []);

  const connectSocial = useCallback(
    async (platform) => {
      if (platform === "instagram") {
        // Real Instagram Business Login when the Meta app is configured —
        // the whole tab goes to Meta's consent screen and comes back.
        try {
          const { url } = await api.igOauthUrl(window.location.pathname);
          if (url) {
            window.location.href = url;
            return null;
          }
        } catch (e) {
          if (e.status !== 503) throw e;
          // 503 → OAuth not configured; fall through to the mock connector.
        }
      }
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
    supabaseEnabled,
    signUp,
    signInPassword,
    signInWithGoogle,
    sendMagicLink,
    resetPassword,
    updatePassword,
    devSignIn,
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
    refreshUser,
    startCheckout,
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
