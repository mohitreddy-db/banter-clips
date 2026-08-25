import { useEffect, useState } from "react";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import { UpgradeModal } from "../components/Modals.jsx";

import { useSeo } from "../lib/seo.js";
const FREE = [
  [true, "5 successful videos / month"],
  [true, "One-click publish to Instagram"],
  [true, "Funny · Savage · Hype tones"],
  [true, "Free retries — failures never count"],
  [false, "720p HD only"],
  [false, "Publishes with BanterClips watermark"],
  [false, "No downloads"],
];
const CREATOR = [
  [true, "30 successful videos / month"],
  [true, "Full HD 1080p quality"],
  [true, "Download in HD — no watermark"],
  [true, "Publish without the watermark"],
  [true, "Priority render queue"],
  [true, "First access to new platforms"],
  [true, "Everything in Free"],
];

export default function Pricing() {
  useSeo({
    title: "Plans & pricing — BanterClips",
    description: "Compare the Free and Creator plans.",
    // noindex despite being a pricing page: this route lives behind the auth
    // gate (AppShell), so a crawler only ever reaches a redirect to /signin.
    // The public pricing story is the #pricing section on the landing page.
    path: "/pricing",
    noindex: true,
  });

  const { plan } = useApp();
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const isCreator = plan === "creator";

  useEffect(() => {
    api.track("pricing_viewed");
  }, []);

  return (
    <div style={{ maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: 28, paddingTop: 8 }}>
      <div style={{ textAlign: "center" }}>
        <h2 style={{ fontSize: "clamp(24px, 6vw, 30px)", fontWeight: 800, color: "var(--app-text)", margin: "0 0 8px" }}>Pick your plan</h2>
        <div style={{ fontSize: 15, color: "var(--app-muted)" }}>
          Publish free — every share promotes you. Upgrade to download without the watermark.
        </div>
      </div>
      <div className="price-cards" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <PlanCard
          name="Free"
          price="$0"
          tagline="Your clips, published everywhere."
          features={FREE}
          cta={isCreator ? "Included in Creator" : "Current plan"}
          current={!isCreator}
        />
        <PlanCard
          name="Creator"
          price="$9.99"
          tagline="For creators posting every week."
          features={CREATOR}
          popular
          cta={isCreator ? "✓ Your plan" : "Upgrade to Creator"}
          current={isCreator}
          onCta={() => !isCreator && setUpgradeOpen(true)}
        />
      </div>
      <div style={{ fontSize: 12.5, color: "var(--app-muted2)", textAlign: "center", lineHeight: 1.6 }}>
        Prices are introductory and may change after beta. The AI-parody disclosure stays on every video on every plan.
        Only successful videos count toward your allowance. Cancel anytime — your videos are never deleted.
      </div>
      {upgradeOpen && <UpgradeModal onClose={() => setUpgradeOpen(false)} />}
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
        <button className="ghost-btn" style={{ padding: 14, fontSize: 15, color: current ? "var(--app-green)" : "var(--app-muted)", cursor: "default" }}>
          {cta}
        </button>
      )}
    </div>
  );
}
