import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";
import {
  AlertStrip, BarRow, Card, ChipRow, Kpi, HBar, LoadingOrError, PageHead, T,
  fmtMoney, fmtNum, fmtPct, timeAgo, useFetch,
} from "./ui.jsx";

/** Overview — every KPI card is a summary; its tab holds the detail. */
export default function AdminDashboard() {
  const [days, setDays] = useState(7);
  const { data, error, loading, reload } = useFetch(() => api.adminOverview(days), [days]);

  if (loading || error) {
    return (
      <>
        <PageHead title="Overview" sub="Real-time operating picture — every widget drills into its own tab." />
        <LoadingOrError loading={loading} error={error} reload={reload} />
      </>
    );
  }

  const { users, videos, revenue, ai_cost, caps, worker, funnel, alerts } = data;
  const balance = data.provider_balance;
  const funnelMax = Math.max(1, ...funnel.map((f) => f.count));
  const toneMax = Math.max(1, ...data.tone_publish.map((t) => t.rate_pct));

  return (
    <>
      <PageHead
        title="Overview"
        sub="Real-time operating picture — every widget drills into its own tab."
        right={
          <ChipRow
            value={days}
            onChange={setDays}
            options={[
              { value: 1, label: "Today" },
              { value: 7, label: "7 Days" },
              { value: 30, label: "30 Days" },
            ]}
          />
        }
      />

      <AlertStrip alerts={alerts} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 14 }}>
        <Link to="/admin/users" style={{ textDecoration: "none" }}>
          <Kpi label="TOTAL USERS" value={fmtNum(users.total)} note={`+${users.new} this period`} tone="good" />
        </Link>
        <Link to="/admin/users" style={{ textDecoration: "none" }}>
          <Kpi label="ACTIVE USERS" value={fmtNum(users.active)} note="with activity this period" />
        </Link>
        <Link to="/admin/videos" style={{ textDecoration: "none" }}>
          <Kpi label="VIDEOS GENERATED" value={fmtNum(videos.total)} note={`${videos.period} this period`} tone="good" />
        </Link>
        <Link to="/admin/publishing" style={{ textDecoration: "none" }}>
          <Kpi label="PUBLISHED CLIPS" value={fmtNum(videos.published_clips)} note={`${fmtPct(videos.publish_rate_pct)} of ready`} />
        </Link>
        <Link to="/admin/revenue" style={{ textDecoration: "none" }}>
          <Kpi label="MRR" value={fmtMoney(revenue.mrr)} note={`${revenue.paying_users} paying · ${fmtPct(revenue.conversion_pct)} conv`} tone="good" />
        </Link>
        <Link to="/admin/costs" style={{ textDecoration: "none" }}>
          <Kpi label="AI COST (PERIOD)" value={fmtMoney(ai_cost.period)} note={`today ${fmtMoney(ai_cost.today)} · ${fmtMoney(ai_cost.cost_per_video)} / video`} />
        </Link>
        <Link to="/admin/revenue" style={{ textDecoration: "none" }}>
          <Kpi label="GROSS MARGIN" value={fmtPct(data.margin_pct)} note="MRR vs 30d AI cost" tone={data.margin_pct !== null && data.margin_pct < 30 ? "warn" : "good"} />
        </Link>
        <Link to="/admin/costs" style={{ textDecoration: "none" }}>
          <Kpi
            label="PROVIDER BALANCE"
            value={balance ? fmtMoney(balance.balance_usd) : "—"}
            note={balance ? "OpenRouter credits left" : "no OpenRouter key configured"}
            tone={balance && balance.balance_usd < 20 ? "bad" : undefined}
          />
        </Link>
        <Link to="/admin/jobs" style={{ textDecoration: "none" }}>
          <Kpi
            label="DAILY SPEND CAP"
            value={caps.daily_cap ? `${fmtMoney(caps.spent_24h)} / ${fmtMoney(caps.daily_cap)}` : "off"}
            note={caps.paused ? "GENERATION PAUSED" : "not tripped"}
            tone={caps.paused ? "bad" : undefined}
          />
        </Link>
        <Link to="/admin/jobs" style={{ textDecoration: "none" }}>
          <Kpi
            label="WORKER"
            value={worker.alive ? "alive" : "down"}
            note={worker.last_beat ? `heartbeat ${timeAgo(worker.last_beat)}` : "no heartbeat yet"}
            tone={worker.alive ? "good" : "bad"}
          />
        </Link>
        <Link to="/admin/credits" style={{ textDecoration: "none" }}>
          <Kpi
            label="CREDITS"
            value={data.credits ? data.credits.outstanding.toLocaleString() : "—"}
            note={data.credits ? `outstanding · ${data.credits.consumed_30d.toLocaleString()} consumed 30d` : "loading"}
          />
        </Link>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)", gap: 16 }} className="admin-two-col">
        <Card title="Activation & conversion funnel" sub="signup → paid · all time (events + clips + publishes + plans)">
          {funnel.map((f, i) => (
            <div key={f.label} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <span style={{ width: 90, fontSize: 12.5, color: T.muted, flexShrink: 0 }}>{f.label}</span>
              <HBar pct={(f.count / funnelMax) * 100} color={i === funnel.length - 1 ? T.green : T.cyan} height={20} />
              <span style={{ width: 90, fontSize: 12.5, fontWeight: 600, color: T.text, textAlign: "right", flexShrink: 0 }}>
                {fmtNum(f.count)}
                {i > 0 && funnel[i - 1].count > 0 && (
                  <span style={{ color: T.muted2, fontWeight: 500 }}> · {Math.round((f.count / funnel[i - 1].count) * 100)}%</span>
                )}
              </span>
            </div>
          ))}
        </Card>

        <Card title="Top performing takes" sub="ready clips, ranked by publishes">
          {data.top_takes.length === 0 && <div style={{ fontSize: 12.5, color: T.muted2 }}>No ready clips yet.</div>}
          {data.top_takes.map((t, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{i + 1}. {t.take}</div>
              <div style={{ fontSize: 11, color: T.muted2, marginTop: 2 }}>
                {t.sport} · {t.tone} · {t.publishes} publish{t.publishes === 1 ? "" : "es"}
              </div>
            </div>
          ))}
          <Link to="/admin/videos" style={{ fontSize: 12, fontWeight: 600, color: T.cyan, textDecoration: "none" }}>
            Full ranking in All Videos →
          </Link>
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        <Card title="Top sports" sub="share of all generated videos">
          {data.top_sports.map((s, i) => (
            <BarRow key={s.sport} label={s.sport} pct={s.pct} value={`${s.pct}%`}
                    color={[T.cyan, T.green, T.purple, T.amber][i % 4]} />
          ))}
        </Card>
        <Card title="Tone → publish rate" sub="which tones actually get posted">
          {data.tone_publish.map((t) => (
            <BarRow key={t.tone} label={`${t.tone} (${t.ready} ready)`} pct={(t.rate_pct / toneMax) * 100}
                    value={fmtPct(t.rate_pct)} color={t.tone === "Savage" ? T.error : T.cyan} />
          ))}
        </Card>
      </div>
    </>
  );
}
