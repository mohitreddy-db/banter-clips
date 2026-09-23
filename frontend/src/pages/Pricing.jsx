import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import { UpgradeModal } from "../components/Modals.jsx";
import AppShell from "../components/AppShell.jsx";
import Logo from "../components/BrandMark.jsx";
import { useSeo } from "../lib/seo.js";

/* The one app page that is deliberately PUBLIC. Pricing queries are the
   highest-intent search a SaaS gets, and while this route lived behind the
   AppShell gate a crawler only ever saw a redirect to /signin — so it was
   noindex and unrankable. Now the route is top-level: signed-out visitors
   (and Googlebot) get a standalone marketing layout, signed-in users get the
   same cards wrapped back in the app chrome via AppShell's children mode. */

const FREE = [
  [true, "60 welcome credits — your first video on us"],
  [true, "One-click publish to Instagram & TikTok"],
  [true, "Funny · Savage · Hype tones"],
  [true, "Free retries — failures never count"],
  [true, "Prompts up to 280 characters"],
  [false, "720p HD only"],
  [false, "Publishes with BanterClips watermark"],
  [false, "No downloads"],
];
const CREATOR = [
  [true, "150 credits added every month"],
  [true, "Full HD 1080p quality"],
  [true, "Prompts up to 500 characters"],
  [true, "Download in HD — no watermark"],
  [true, "Publish without the watermark"],
  [true, "Priority render queue"],
  [true, "First access to new platforms"],
  [true, "Everything in Free"],
];

export default function Pricing() {
  useSeo({
    title: "Pricing — BanterClips plans from $0",
    description:
      "BanterClips pricing: Free plan with welcome credits to make your first AI sports video, or Creator at $19/mo with monthly credits, 1080p and watermark-free downloads. No credit card to start.",
    path: "/pricing",
  });

  const { plan, booted, signedIn } = useApp();
  const nav = useNavigate();
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const isCreator = plan === "creator";

  useEffect(() => {
    api.track("pricing_viewed");
  }, []);

  // Signed-out CTAs route to sign-up; signed-in ones keep the upgrade flow.
  const cards = (
    <div className="price-cards" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
      <PlanCard
        name="Free"
        price="$0"
        tagline="Your clips, published everywhere."
        features={FREE}
        cta={signedIn ? (isCreator ? "Included in Creator" : "Current plan") : "Start free"}
        current={signedIn && !isCreator}
        onCta={signedIn ? undefined : () => nav("/signin")}
      />
      <PlanCard
        name="Creator"
        price="$19"
        tagline="For creators posting every week."
        features={CREATOR}
        popular
        cta={signedIn ? (isCreator ? "✓ Your plan" : "Upgrade to Creator") : "Go Creator"}
        current={signedIn && isCreator}
        onCta={signedIn ? () => !isCreator && setUpgradeOpen(true) : () => nav("/signin")}
      />
    </div>
  );

  const fineprint = (
    <div style={{ fontSize: 12.5, color: "var(--app-muted2)", textAlign: "center", lineHeight: 1.6 }}>
      Prices are introductory and may change after beta. The AI-parody disclosure stays on every video on every plan.
      Only successful videos use credits — failures are refunded. Cancel anytime — your videos are never deleted.
    </div>
  );

  // Signed-in: same page, back inside the app chrome. Signed-out and
  // still-booting visitors get the public layout immediately — crawlers have
  // no session, so waiting on boot would block them on nothing.
  if (booted && signedIn) {
    return (
      <AppShell>
        <div style={{ maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: 28, paddingTop: 8 }}>
          <div style={{ textAlign: "center" }}>
            <h1 style={{ fontSize: "clamp(24px, 6vw, 30px)", fontWeight: 800, color: "var(--app-text)", margin: "0 0 8px" }}>Pick your plan</h1>
            <div style={{ fontSize: 15, color: "var(--app-muted)" }}>
              Publish free — every share promotes you. Upgrade to download without the watermark.
            </div>
          </div>
          {cards}
          {fineprint}
          {upgradeOpen && <UpgradeModal onClose={() => setUpgradeOpen(false)} />}
        </div>
      </AppShell>
    );
  }

  // Public marketing layout — what crawlers index and signed-out visitors see.
  return (
    <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "flex", flexDirection: "column" }}>
      <div style={{ borderBottom: "1px solid var(--app-border)", padding: "14px clamp(18px, 4vw, 28px)", display: "flex", alignItems: "center", gap: 12 }}>
        <div onClick={() => nav("/")} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
          <Logo />
          <span style={{ fontWeight: 700, fontSize: 17, color: "var(--app-text)" }}>BanterClips</span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
          <span onClick={() => nav("/signin")} style={{ cursor: "pointer", fontSize: 14, fontWeight: 600, color: "var(--app-muted)" }}>Sign in</span>
          <button className="grad-btn" style={{ padding: "10px 18px", fontSize: 13.5 }} onClick={() => nav("/signin")}>
            Start Creating Free
          </button>
        </div>
      </div>

      <div style={{ maxWidth: 860, width: "100%", margin: "0 auto", display: "flex", flexDirection: "column", gap: 28, padding: "clamp(28px, 6vw, 48px) clamp(18px, 4vw, 28px) 64px", boxSizing: "border-box" }}>
        <div style={{ textAlign: "center" }}>
          <h1 style={{ fontSize: "clamp(26px, 6vw, 34px)", fontWeight: 800, color: "var(--app-text)", margin: "0 0 10px" }}>
            Simple, creator-friendly pricing
          </h1>
          <div style={{ fontSize: 15.5, color: "var(--app-muted)", maxWidth: 560, margin: "0 auto", lineHeight: 1.55 }}>
            Turn a written sports take into a finished 9:16 AI video — voiceover, animated captions,
            one-click publish to Instagram & TikTok. Start free, no credit card.
          </div>
        </div>
        {cards}
        {fineprint}
        <div style={{ textAlign: "center", fontSize: 13.5, color: "var(--app-muted2)" }}>
          Questions? <a href="mailto:support@banterclips.com" style={{ color: "var(--app-muted)" }}>support@banterclips.com</a>
          {" · "}
          <a href="/privacy" style={{ color: "var(--app-muted)" }}>Privacy</a>
          {" · "}
          <a href="/terms" style={{ color: "var(--app-muted)" }}>Terms</a>
          {" · "}
          <a href="https://www.google.com/preferences/source?q=banterclips.com" target="_blank" rel="noopener" style={{ color: "var(--app-muted)" }}>★ Prefer us on Google</a>
        </div>
      </div>
    </div>
  );
}

function PlanCard({ name, price, tagline, features, popular, cta, current, onCta }) {
  return (
    <div className="card" style={{ padding: "clamp(20px, 5vw, 30px)", position: "relative", border: popular ? "1.5px solid var(--app-cyan)" : undefined, display: "flex", flexDirection: "column", gap: 14 }}>
      {popular && (
        <span style={{ position: "absolute", top: -12, left: 26, background: "var(--app-grad)", color: "#06121a", fontSize: 10, fontWeight: 800, padding: "4px 12px", borderRadius: 999, letterSpacing: ".05em" }}>
          MOST POPULAR
        </span>
      )}
      <div style={{ fontWeight: 700, fontSize: 20, color: "var(--app-text)" }}>{name}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span style={{ fontWeight: 800, fontSize: 38, color: "var(--app-text)" }}>{price}</span>
        <span style={{ fontSize: 14, color: "var(--app-muted)" }}>/mo</span>
      </div>
      <div style={{ fontSize: 13, color: "var(--app-muted)" }}>{tagline}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: "6px 0" }}>
        {features.map(([ok, f]) => (
          <div key={f} style={{ display: "flex", gap: 10, fontSize: 13.5, fontWeight: 500, color: ok ? "var(--app-text)" : "var(--app-muted)" }}>
            <span style={{ color: ok ? "var(--app-green)" : "var(--app-muted2)", fontWeight: 700 }}>{ok ? "✓" : "—"}</span>
            {f}
          </div>
        ))}
      </div>
      {popular && !current ? (
        <button className="grad-btn" style={{ padding: 14, fontSize: 15 }} onClick={onCta}>
          {cta}
        </button>
      ) : (
        <button
          className="ghost-btn"
          onClick={onCta}
          style={{ padding: 14, fontSize: 15, color: current ? "var(--app-green)" : onCta ? "var(--app-text)" : "var(--app-muted)", cursor: onCta ? "pointer" : "default" }}
        >
          {cta}
        </button>
      )}
    </div>
  );
}
