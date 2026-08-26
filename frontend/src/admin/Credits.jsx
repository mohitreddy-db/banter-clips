import { useState } from "react";
import { api } from "../lib/api.js";
import { Badge, Card, Kpi, LoadingOrError, PageHead, T, Table, timeAgo, useFetch } from "./ui.jsx";

/**
 * Credits — the live credit system (PRICING.md / services/credits.py):
 * outstanding + 30d KPIs, the price config editor, manual grants, and the
 * recent ledger. Every mutation lands in the audit log.
 */

const KIND_COLORS = {
  grant_signup: T.green, grant_monthly: T.green, grant_admin: T.cyan,
  topup: T.cyan, video_charge: T.amber, video_refund: T.muted,
  enhance_charge: T.amber,
};

function GrantBox({ onDone }) {
  const [email, setEmail] = useState("");
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const grant = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.adminGrantCredits(email.trim(), parseInt(delta, 10), reason.trim());
      setMsg({ ok: true, text: `${res.email} → ${res.balance.toLocaleString()} credits` });
      setEmail(""); setDelta(""); setReason("");
      onDone();
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    }
    setBusy(false);
  };

  const input = { width: "100%", boxSizing: "border-box", padding: "9px 11px", fontSize: 13, color: T.text, background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8 };
  const valid = email.includes("@") && parseInt(delta, 10) && reason.trim().length >= 3;
  return (
    <Card title="Grant / deduct credits" sub="reason required — lands in the ledger and the audit log">
      <div style={{ display: "grid", gap: 10 }}>
        <input style={input} placeholder="user email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input style={input} placeholder="credits (negative to deduct) — e.g. 150" value={delta}
               onChange={(e) => setDelta(e.target.value.replace(/[^-0-9]/g, ""))} />
        <input style={input} placeholder="reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <button
          onClick={grant}
          disabled={!valid || busy}
          style={{ padding: "10px 14px", borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: valid ? "pointer" : "not-allowed", color: "#04121a", background: valid ? T.cyan : T.border, border: "none", opacity: busy ? 0.6 : 1 }}
        >
          {busy ? "Applying…" : "Apply"}
        </button>
        {msg && <div style={{ fontSize: 12.5, color: msg.ok ? T.green : T.error }}>{msg.text}</div>}
      </div>
    </Card>
  );
}

function PricesEditor({ prices, onSaved }) {
  const [form, setForm] = useState({
    r720: prices.per_second["720p"], r1080: prices.per_second["1080p"],
    enhance: prices.enhance_take, signup: prices.signup_grant, monthly: prices.monthly_grant,
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api.adminSaveCreditSettings({
        per_second: { "720p": +form.r720, "1080p": +form.r1080 },
        enhance_take: +form.enhance, signup_grant: +form.signup, monthly_grant: +form.monthly,
      });
      setMsg({ ok: true, text: "Saved — applies to the next generation, no release needed." });
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    }
    setBusy(false);
  };

  const row = (label, key, note) => (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ flex: 1, fontSize: 12.5, color: T.muted }}>{label}</span>
      <input
        value={form[key]}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value.replace(/[^0-9]/g, "") }))}
        style={{ width: 76, textAlign: "right", padding: "7px 9px", fontSize: 13, fontWeight: 700, color: T.text, background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8 }}
      />
      <span style={{ width: 74, fontSize: 11, color: T.muted2 }}>{note}</span>
    </div>
  );

  const sample = (s, key) => +form[key] * s;
  return (
    <Card title="Price config" sub="credits are the unit everywhere — video price = rate × seconds">
      <div style={{ display: "grid", gap: 10 }}>
        {row("Standard (720p), per second", "r720", `15s = ${sample(15, "r720")}`)}
        {row("HD (1080p), per second", "r1080", `15s = ${sample(15, "r1080")}`)}
        {row("Enhance take, per press", "enhance", "")}
        {row("Signup grant (one-time)", "signup", "")}
        {row("Creator monthly grant", "monthly", "")}
        <button onClick={save} disabled={busy}
                style={{ padding: "10px 14px", borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: "pointer", color: "#04121a", background: T.cyan, border: "none", opacity: busy ? 0.6 : 1 }}>
          {busy ? "Saving…" : "Save prices"}
        </button>
        {msg && <div style={{ fontSize: 12.5, color: msg.ok ? T.green : T.error }}>{msg.text}</div>}
      </div>
    </Card>
  );
}

export default function AdminCredits() {
  const { data, error, loading, reload } = useFetch(() => api.adminCredits(), []);

  return (
    <>
      <PageHead title="Credits" sub="One wallet per user · reserve on start, refund on failure · top up, never upgrade" />
      <LoadingOrError loading={loading} error={error} reload={reload} />
      {data?.enabled && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            <Kpi label="OUTSTANDING" value={data.outstanding.toLocaleString()} note="credits users hold" />
            <Kpi label="GRANTED · 30D" value={data.last_30d.granted.toLocaleString()} note="signup + monthly + admin" tone="good" />
            <Kpi label="PURCHASED · 30D" value={data.last_30d.purchased.toLocaleString()} note="top-up packs"  />
            <Kpi label="CONSUMED · 30D" value={data.last_30d.consumed.toLocaleString()} note="net of refunds" tone="warn" />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
            <PricesEditor prices={data.prices} onSaved={reload} />
            <GrantBox onDone={reload} />
            <Card title="Top-up packs" sub="Stripe one-time payments — pack changes are code-side">
              <Table
                columns={[
                  { key: "key", label: "PACK" },
                  { key: "credits", label: "CREDITS", render: (r) => r.credits.toLocaleString() },
                  { key: "usd", label: "PRICE", render: (r) => `$${r.usd}` },
                  { key: "rate", label: "$/CREDIT", render: (r) => `$${(r.usd / r.credits).toFixed(3)}` },
                ]}
                rows={data.prices.packs}
              />
            </Card>
          </div>

          <Card title="Recent ledger" sub="latest 60 movements, all users">
            <Table
              columns={[
                { key: "created_at", label: "WHEN", render: (r) => timeAgo(r.created_at) },
                { key: "email", label: "USER" },
                { key: "kind", label: "KIND", render: (r) => <Badge color={KIND_COLORS[r.kind] || T.muted}>{r.kind.replace("_", " ")}</Badge> },
                { key: "delta", label: "Δ", render: (r) => (
                  <span style={{ fontWeight: 700, color: r.delta >= 0 ? T.green : T.amber }}>
                    {r.delta >= 0 ? "+" : ""}{r.delta.toLocaleString()}
                  </span>
                ) },
                { key: "balance_after", label: "BALANCE", render: (r) => r.balance_after.toLocaleString() },
                { key: "note", label: "NOTE", render: (r) => <span style={{ color: T.muted2 }}>{r.note || ""}</span> },
              ]}
              rows={data.ledger}
              empty="No credit movements yet."
            />
          </Card>
        </>
      )}
    </>
  );
}
