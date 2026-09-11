import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import { TopUpModal } from "../components/Modals.jsx";
import { SocialIcon } from "../components/SocialIcon.jsx";

import { useSeo } from "../lib/seo.js";
import { YouTubeTerms } from "../components/YouTubeTerms.jsx";
export default function Account() {
  useSeo({
    title: "Account — BanterClips",
    description: "Manage your BanterClips plan, credits and connected accounts.",
    path: "/account",
    noindex: true,
  });

  const nav = useNavigate();
  const {
    user, plan, credits, videoPrice, profile, signOut, cancelPlan, refreshUser,
    refreshUsage, instagram, tiktok, youtube, connected, connectSocial, disconnectSocial,
  } = useApp();
  const isCreator = plan === "creator";
  const [busy, setBusy] = useState(false);
  const [topupOpen, setTopupOpen] = useState(false);
  const [error, setError] = useState("");
  const [params, setParams] = useSearchParams();
  const [igNotice, setIgNotice] = useState(null);
  const [billingStatus, setBillingStatus] = useState(null);

  // The shared plan can be funded by Stripe, Apple, Google, or more than one.
  // Load source-level state before offering provider-specific management.
  useEffect(() => {
    if (!isCreator) {
      setBillingStatus(null);
      return;
    }
    let active = true;
    api.billingStatus()
      .then((status) => { if (active) setBillingStatus(status); })
      .catch(() => { if (active) setBillingStatus({ providers: [] }); });
    return () => { active = false; };
  }, [isCreator, user?.id]);

  // Result of an OAuth round-trip (?ig=... for Instagram, ?tt=... for TikTok).
  useEffect(() => {
    for (const [param, name, at] of [["ig", "Instagram", "@"], ["tt", "TikTok", ""], ["yt", "YouTube", ""]]) {
      const result = params.get(param);
      if (!result) continue;
      if (result === "connected") setIgNotice({ ok: true, text: `${name} connected${params.get("handle") ? ` as ${at}${params.get("handle")}` : ""}.` });
      else setIgNotice({ ok: false, text: `${name} connect ${result === "denied" ? "was cancelled" : "failed"}${params.get("reason") ? ` — ${params.get("reason")}` : ""}.` });
      setParams({}, { replace: true });
      return;
    }
  }, [params, setParams]);

  // Return from a top-up Checkout (?topup=success|cancelled). Credits are
  // granted by the webhook, which can lag a beat — poll the wallet briefly.
  useEffect(() => {
    const t = params.get("topup");
    if (!t) return;
    setParams({}, { replace: true });
    if (t === "cancelled") {
      setIgNotice({ ok: false, text: "Top-up cancelled — no payment was made." });
      return;
    }
    setIgNotice({ ok: true, text: "Payment received — adding your credits…" });
    let tries = 0;
    const timer = setInterval(async () => {
      tries += 1;
      await refreshUsage();
      if (tries >= 8) {
        clearInterval(timer);
        setIgNotice({ ok: true, text: "Credits added. ⚡" });
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [params, setParams, refreshUsage]);

  // Return from Stripe Checkout (?checkout=success|cancelled). The webhook
  // flips the plan server-side, which can lag a beat — poll briefly.
  useEffect(() => {
    const co = params.get("checkout");
    if (!co) return;
    setParams({}, { replace: true });
    if (co === "cancelled") {
      setIgNotice({ ok: false, text: "Checkout cancelled — you're still on the Free plan." });
      return;
    }
    setIgNotice({ ok: true, text: "Payment received — activating Creator…" });
    let tries = 0;
    const t = setInterval(async () => {
      tries += 1;
      await refreshUser();
      const me = await api.me().catch(() => null);
      if (me?.plan === "creator" || tries >= 10) {
        clearInterval(t);
        setIgNotice(
          me?.plan === "creator"
            ? { ok: true, text: "Welcome to Creator — downloads and watermark-free publishing are unlocked. 🎉" }
            : { ok: false, text: "Payment is processing — refresh in a moment if the plan hasn't updated." }
        );
      }
    }, 1500);
    return () => clearInterval(t);
  }, [params, setParams, refreshUser]);

  const withBusy = (fn) => async () => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };

  const joined = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, { month: "short", year: "numeric" })
    : "";
  const billingProviders = billingStatus?.providers || [];
  const hasStripeBilling = billingProviders.includes("stripe");
  const hasAppleBilling = billingProviders.includes("ios");
  const hasGoogleBilling = billingProviders.includes("android");

  return (
    <div style={{ maxWidth: 760, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* profile */}
      <div className="card" style={{ padding: "clamp(18px, 4.5vw, 24px) clamp(16px, 5vw, 28px)", display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div style={{ width: 44, height: 44, borderRadius: "50%", background: "linear-gradient(140deg,#7b2ff7,#f0546c)", display: "grid", placeItems: "center", color: "#fff", fontWeight: 700, flexShrink: 0 }}>
          {(user?.display_name || user?.email || "?")[0].toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 16, color: "var(--app-text)", overflowWrap: "anywhere" }}>{user?.email}</div>
          <div style={{ fontSize: 13, color: "var(--app-muted)", marginTop: 2 }}>
            Beta creator{profile.role ? ` · ${profile.role}` : ""}{joined ? ` · joined ${joined}` : ""}
          </div>
        </div>
        <button className="ghost-btn" style={{ padding: "10px 18px", fontSize: 14 }} onClick={signOut}>Sign out</button>
      </div>

      {error && (
        <div style={{ fontSize: 13.5, color: "var(--app-error)", background: "rgba(240,84,108,.1)", borderRadius: 12, padding: "12px 16px" }}>
          {error}
        </div>
      )}
      {igNotice && (
        <div style={{ fontSize: 13.5, color: igNotice.ok ? "var(--app-green)" : "var(--app-error)", background: igNotice.ok ? "rgba(52,226,122,.1)" : "rgba(240,84,108,.1)", borderRadius: 12, padding: "12px 16px" }}>
          {igNotice.text}
        </div>
      )}

      {/* plan & usage */}
      <div className="card" style={{ padding: "clamp(18px, 4.5vw, 24px) clamp(16px, 5vw, 28px)", display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: 1.2, color: "var(--app-muted)" }}>PLAN & CREDITS</span>
          <span style={{ marginLeft: "auto", fontSize: 12, fontWeight: 700, padding: "4px 12px", borderRadius: 999, background: isCreator ? "rgba(52,226,122,.14)" : "#161e30", color: isCreator ? "var(--app-green)" : "var(--app-muted)", border: "1px solid var(--app-border)" }}>
            {isCreator ? "CREATOR" : "FREE"}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 800, fontSize: "clamp(28px, 7vw, 34px)", color: "var(--app-text)" }}>⚡ {credits.toLocaleString()}</span>
          <span style={{ fontSize: 15, color: "var(--app-muted)" }}>credits available</span>
        </div>
        <div style={{ fontSize: 13, color: "var(--app-muted)" }}>
          ≈ {Math.floor(credits / videoPrice(15, "720p"))} videos at 15s Standard
          {isCreator ? ` · ≈ ${Math.floor(credits / videoPrice(15, "1080p"))} at 15s HD` : ""}
          {" · "}only successful videos charge — failures are refunded.
        </div>
        <div style={{ display: "flex", gap: 12, paddingTop: 4, flexWrap: "wrap" }}>
          <button className="grad-btn" style={{ padding: "13px 22px", fontSize: 14.5 }} onClick={() => setTopupOpen(true)}>
            ⚡ Top up credits
          </button>
        </div>
        {!isCreator ? (
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button className="ghost-btn" style={{ padding: "13px 22px", fontSize: 14.5 }} onClick={() => nav("/pricing")}>
              Creator plan — 1080p, 30s, 500-char prompts, no watermark, 150 credits/mo
            </button>
          </div>
        ) : billingStatus === null ? (
          <div style={{ fontSize: 13, color: "var(--app-muted)" }}>Loading billing details…</div>
        ) : (
          <>
            {user?.cancel_at_period_end && (
              <div style={{ fontSize: 13, color: "var(--app-muted)", background: "rgba(34,211,238,.07)", borderRadius: 10, padding: "10px 14px" }}>
                Creator stays active until the end of the billing period, then you move to Free unless another subscription remains active. Your videos are never deleted.
              </div>
            )}
            <div style={{ display: "flex", gap: 12, paddingTop: 4, flexWrap: "wrap" }}>
              {hasStripeBilling && (
                <>
                  <button
                    className="ghost-btn"
                    style={{ padding: "11px 20px", fontSize: 13.5, opacity: busy ? 0.7 : 1, color: "var(--app-text)" }}
                    disabled={busy}
                    onClick={withBusy(async () => {
                      const { url } = await api.billingPortal();
                      window.location.href = url;
                    })}
                  >
                    Manage Stripe billing ↗
                  </button>
                  <button
                    className="ghost-btn"
                    style={{ padding: "11px 20px", fontSize: 13.5, color: "var(--app-muted)", opacity: busy ? 0.7 : 1 }}
                    disabled={busy}
                    onClick={withBusy(async () => {
                      await cancelPlan();
                      setBillingStatus(await api.billingStatus());
                    })}
                  >
                    Cancel Stripe — applies at period end
                  </button>
                </>
              )}
              {hasAppleBilling && (
                <a className="ghost-btn" style={{ padding: "11px 20px", fontSize: 13.5, color: "var(--app-text)", textDecoration: "none" }} href="https://apps.apple.com/account/subscriptions" target="_blank" rel="noreferrer">
                  Manage Apple subscription ↗
                </a>
              )}
              {hasGoogleBilling && (
                <a className="ghost-btn" style={{ padding: "11px 20px", fontSize: 13.5, color: "var(--app-text)", textDecoration: "none" }} href="https://play.google.com/store/account/subscriptions" target="_blank" rel="noreferrer">
                  Manage Google Play subscription ↗
                </a>
              )}
              {billingProviders.length === 0 && (
                <span style={{ fontSize: 13, color: "var(--app-muted)" }}>Creator access is managed by BanterClips support.</span>
              )}
            </div>
          </>
        )}
      </div>

      {/* connected accounts */}
      <div className="card" style={{ padding: "clamp(18px, 4.5vw, 24px) clamp(16px, 5vw, 28px)", display: "flex", flexDirection: "column", gap: 14 }}>
        <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: 1.2, color: "var(--app-muted)" }}>CONNECTED ACCOUNTS</span>
        {[
          { key: "instagram", name: "Instagram", account: instagram, blurb: "Connected · clips publish as Reels · explicit per-clip publishing only" },
          { key: "tiktok", name: "TikTok", account: tiktok, blurb: "Connected · clips post to your TikTok · explicit per-clip publishing only" },
          { key: "youtube", name: "YouTube", account: youtube, blurb: "Connected · vertical clips upload as Shorts · explicit per-clip publishing only", legal: true },
        ].map(({ key, name, account, blurb, legal }) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
            {key === "youtube" ? (
              <a href="https://www.youtube.com/" target="_blank" rel="noreferrer" title="Open YouTube" style={{ display: "inline-flex" }}>
                <SocialIcon platform={key} size={36} />
              </a>
            ) : <SocialIcon platform={key} size={36} />}
            <div style={{ flex: 1, minWidth: 180 }}>
              <div style={{ fontWeight: 600, fontSize: 15, color: "var(--app-text)" }}>
                {name} {account ? `— ${account.handle}` : ""}
              </div>
              <div style={{ fontSize: 12, color: "var(--app-muted)", marginTop: 2 }}>
                {account ? blurb : "Not connected"}
              </div>
              {/* YouTube API Services Developer Policies: these two links must
                  sit where the channel is connected, not only in the policy. */}
              {legal && <YouTubeTerms style={{ marginTop: 4 }} />}
            </div>
            {account ? (
              <button
                className="ghost-btn"
                style={{ padding: "10px 18px", fontSize: 14, opacity: busy ? 0.7 : 1 }}
                disabled={busy}
                onClick={withBusy(async () => {
                  const detail = key === "youtube"
                    ? "This immediately revokes BanterClips in Google and deletes stored YouTube tokens and API-returned video links. Videos already on YouTube are not deleted."
                    : `This removes the stored ${name} connection and tokens. Published posts stay on ${name}.`;
                  if (!window.confirm(`Disconnect ${name}?\n\n${detail}`)) return;
                  await disconnectSocial(key);
                  setIgNotice({ ok: true, text: `${name} disconnected and its stored authorization data was deleted.` });
                })}
              >
                Disconnect
              </button>
            ) : (
              <button className="grad-btn" style={{ padding: "10px 20px", fontSize: 14, borderRadius: 10, opacity: busy ? 0.7 : 1 }} disabled={busy} onClick={withBusy(() => connectSocial(key))}>
                Connect
              </button>
            )}
          </div>
        ))}
        <div style={{ fontSize: 12, color: "var(--app-muted2)" }}>Instagram, TikTok and YouTube are available in beta. X arrives later.</div>
      </div>

      {/* preferences */}
      <div className="card" style={{ padding: "clamp(18px, 4.5vw, 24px) clamp(16px, 5vw, 28px)", display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: 1.2, color: "var(--app-muted)" }}>STUDIO PREFERENCES</span>
          <button onClick={() => nav("/onboarding")} style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--app-cyan)", fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}>
            Edit in onboarding →
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[...(profile.sports || []), ...(profile.teams || []), ...(profile.players || [])].map((t) => (
            <span key={t} className="chip" style={{ cursor: "default", fontSize: 12.5 }}>{t}</span>
          ))}
          {!(profile.sports?.length || profile.teams?.length || profile.players?.length) && (
            <span style={{ fontSize: 13, color: "var(--app-muted)" }}>Nothing picked yet — onboarding pre-fills your Studio.</span>
          )}
        </div>
      </div>

      {/* data & privacy */}
      <div className="card" style={{ padding: "clamp(18px, 4.5vw, 24px) clamp(16px, 5vw, 28px)", display: "flex", flexDirection: "column", gap: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: 1.2, color: "var(--app-muted)" }}>DATA & PRIVACY</span>
        <div style={{ fontSize: 14, color: "var(--app-muted)", lineHeight: 1.55 }}>
          Your videos are private to your account and are kept until you delete them or request account deletion. Nothing is published without your explicit action.
        </div>
        <div style={{ display: "flex", gap: "14px 24px", paddingTop: 4, flexWrap: "wrap" }}>
          <a href="/data-deletion#request-copy" style={{ fontSize: 13, fontWeight: 600, color: "var(--app-cyan)", textDecoration: "none" }}>Request a copy of my data</a>
          <a href="mailto:support@banterclips.com?subject=Delete%20my%20account" style={{ fontSize: 13, fontWeight: 600, color: "var(--app-error)", textDecoration: "none" }}>Request account and video deletion</a>
          <a href="/privacy" style={{ fontSize: 13, fontWeight: 600, color: "var(--app-muted)", textDecoration: "none" }}>Privacy Policy</a>
          <a href="/terms" style={{ fontSize: 13, fontWeight: 600, color: "var(--app-muted)", textDecoration: "none" }}>Terms</a>
        </div>
      </div>
      {topupOpen && <TopUpModal onClose={() => { setTopupOpen(false); refreshUsage(); }} />}
    </div>
  );
}
