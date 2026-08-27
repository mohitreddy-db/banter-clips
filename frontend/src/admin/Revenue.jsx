import { api } from "../lib/api.js";
import {
  BarRow, Card, Kpi, LoadingOrError, PageHead, T, Table,
  fmtMoney, fmtNum, fmtPct, timeAgo, useFetch,
} from "./ui.jsx";

const EVENT_LABELS = {
  upgrade_completed: ["Upgraded to Creator", T.green],
  upgrade_started: ["Started checkout", T.cyan],
  plan_cancelled: ["Cancelled plan", T.error],
  plan_downgraded: ["Downgraded to Free", T.amber],
  duplicate_subscription_cancelled: ["Duplicate sub cancelled", T.muted],
};

export default function AdminRevenue() {
  const { data, error, loading, reload } = useFetch(() => api.adminRevenue(), []);

  if (loading || error) {
    return (
      <>
        <PageHead title="Revenue" sub="Recurring revenue and billing activity — Stripe stays the money source of truth." />
        <LoadingOrError loading={loading} error={error} reload={reload} />
      </>
    );
  }

  const totalUsers = data.paying_users + data.free_users || 1;
  return (
    <>
      <PageHead
        title="Revenue"
        sub="Recurring revenue and billing activity — Stripe stays the money source of truth."
        right={
          <a href={data.stripe_dashboard_url} target="_blank" rel="noreferrer" className="ghost-btn" style={{ padding: "8px 14px", fontSize: 12.5, textDecoration: "none" }}>
            ↗ Open Stripe
          </a>
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
        <Kpi label="MRR" value={fmtMoney(data.mrr)} note={`${data.paying_users} × $${data.creator_price} Creator`} tone="good" />
        <Kpi label="PAYING USERS" value={fmtNum(data.paying_users)} note={`${fmtPct(data.conversion_pct)} of all accounts`} />
        <Kpi label="CANCELLING" value={fmtNum(data.cancel_pending)} note="cancel at period end" tone={data.cancel_pending ? "warn" : undefined} />
        <Kpi label="GROSS PROFIT (30D)" value={fmtMoney(data.gross_profit_30d)} note={`MRR − AI cost ${fmtMoney(data.ai_cost_30d)}`} tone={data.gross_profit_30d >= 0 ? "good" : "bad"} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.4fr)", gap: 16 }} className="admin-two-col">
        <Card title="Plan split" sub="live plan column on users — synced from Stripe webhooks">
          <BarRow label={`Creator — $${data.creator_price}/mo`} pct={(data.paying_users / totalUsers) * 100} value={fmtNum(data.paying_users)} color={T.green} />
          <BarRow label="Free" pct={(data.free_users / totalUsers) * 100} value={fmtNum(data.free_users)} color={T.cyan} />
          <div style={{ fontSize: 11, color: T.muted2, marginTop: 12 }}>
            Out-of-credits users will see "Top up", never "Upgrade" — PRICING.md rule 2. Transactions detail and refunds live in Stripe.
          </div>
        </Card>

        <Card title="Billing activity" sub="latest plan events (events table)">
          {data.activity.length === 0 && <div style={{ fontSize: 12.5, color: T.muted2 }}>No billing events yet.</div>}
          {data.activity.map((a, i) => {
            const [label, color] = EVENT_LABELS[a.name] || [a.name, T.muted];
            return (
              <div key={i} style={{ display: "flex", gap: 10, alignItems: "baseline", marginBottom: 8, fontSize: 12.5 }}>
                <span style={{ color, fontWeight: 600, width: 180, flexShrink: 0 }}>{label}</span>
                <span style={{ color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.email || "—"}</span>
                <span style={{ marginLeft: "auto", color: T.muted2, flexShrink: 0 }}>{timeAgo(a.at)}</span>
              </div>
            );
          })}
        </Card>
      </div>

      <Card title="Stripe webhook log" sub="stripe_events — processed webhooks (idempotency record); open Stripe for the money detail">
        <Table
          columns={[
            { key: "id", label: "EVENT", render: (r) => <span style={{ color: T.muted2 }}>{r.id}</span> },
            { key: "type", label: "TYPE", render: (r) => <span style={{ color: T.text }}>{r.type}</span> },
            { key: "at", label: "WHEN", render: (r) => timeAgo(r.at) },
          ]}
          rows={data.stripe_events}
          empty="No webhooks received yet (dev environments often use the mock upgrade)."
        />
      </Card>
    </>
  );
}
