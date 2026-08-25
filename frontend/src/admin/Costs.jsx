import { useState } from "react";
import { api } from "../lib/api.js";
import {
  Badge, BarRow, Card, ChipRow, HBar, Kpi, LoadingOrError, PageHead, T,
  fmtMoney, fmtPct, useFetch,
} from "./ui.jsx";

const SOURCE_LABELS = {
  failure: { label: "FAILED RUN", color: T.error },
  fallback: { label: "FALLBACK", color: T.amber },
  review: { label: "QUALITY CHECK", color: T.cyan },
};

export default function AdminCosts() {
  const [days, setDays] = useState(7);
  const { data, error, loading, reload } = useFetch(() => api.adminCosts(days), [days]);

  if (loading || error) {
    return (
      <>
        <PageHead title="AI Costs & Quality" sub="Unit economics of the generation engine, plus the quality metrics that explain the failures." />
        <LoadingOrError loading={loading} error={error} reload={reload} />
      </>
    );
  }

  const q = data.quality;
  const balance = data.provider_balance;
  const dayMax = Math.max(0.01, ...data.by_day.map((d) => d.cost));
  const breakdownTotal = data.breakdown.video_scenes + data.breakdown.other || 1;

  return (
    <>
      <PageHead
        title="AI Costs & Quality"
        sub="Unit economics of the generation engine, plus the quality metrics that explain the failures."
        right={<ChipRow value={days} onChange={setDays} options={[{ value: 7, label: "7 Days" }, { value: 30, label: "30 Days" }, { value: 90, label: "90 Days" }]} />}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
        <Kpi label="TOTAL SPEND" value={fmtMoney(data.total)} note={`today ${fmtMoney(data.today)}`} />
        <Kpi label="COST / VIDEO" value={fmtMoney(data.cost_per_video)} note="clips with real cost" />
        <Kpi label="COST / ACTIVE USER" value={fmtMoney(data.cost_per_active_user)} note="blended over the period" />
        <Kpi label="FAILED-GEN COST" value={fmtMoney(data.failed_generation_cost)} note={`${fmtPct(data.failed_cost_pct)} of spend — eaten as COGS`} tone={data.failed_cost_pct > 10 ? "warn" : undefined} />
        <Kpi
          label="PROVIDER BALANCE"
          value={balance ? fmtMoney(balance.balance_usd) : "—"}
          note={balance ? `OpenRouter · used ${fmtMoney(balance.total_usage)} lifetime` : "no OpenRouter key configured"}
          tone={balance && balance.balance_usd < 20 ? "bad" : undefined}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)", gap: 16 }} className="admin-two-col">
        <Card title="Spend by day" sub="last 14 days · $/day from clips.cost_usd">
          {data.by_day.length === 0 && <div style={{ fontSize: 12.5, color: T.muted2 }}>No spend recorded yet.</div>}
          <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 150 }}>
            {data.by_day.map((d, i) => (
              <div key={d.day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, minWidth: 0 }}>
                <span style={{ fontSize: 9.5, color: T.muted2 }}>{d.cost ? `$${d.cost}` : ""}</span>
                <div style={{ width: "100%", maxWidth: 46, height: Math.max(3, (d.cost / dayMax) * 110), borderRadius: 6, background: i === data.by_day.length - 1 ? T.cyan : "rgba(34,211,238,.4)" }} />
                <span style={{ fontSize: 9, color: T.muted2, whiteSpace: "nowrap" }}>{d.day}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Spend breakdown" sub="from per-scene provenance costs">
          <BarRow label="Video scenes" pct={(data.breakdown.video_scenes / breakdownTotal) * 100} value={fmtMoney(data.breakdown.video_scenes)} color={T.cyan} />
          <BarRow label="Images · script · voice" pct={(data.breakdown.other / breakdownTotal) * 100} value={fmtMoney(data.breakdown.other)} color={T.green} />
          <div style={{ fontSize: 11, color: T.muted2, marginTop: 14 }}>
            Failed generations cost {fmtMoney(data.failed_generation_cost)} this period — retried free for the user, absorbed by us.
          </div>
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
        <Kpi label="GENERATION SUCCESS" value={fmtPct(q.success_rate_pct)} note="ready vs failed, period" tone={q.success_rate_pct !== null && q.success_rate_pct < 85 ? "warn" : "good"} />
        <Kpi label="SCENES REVIEWED" value={q.scenes_reviewed} note={`${q.scenes_flagged} flagged by review`} />
        <Kpi label="AVG SCENE ATTEMPTS" value={q.avg_scene_attempts ?? "—"} note="1.0 = first try clean" />
        <Kpi label="USER RETRIES" value={q.retries} note="generation_retried events" />
      </div>

      <Card title="What went wrong" sub="every problem from recent generations, most common first">
        {q.failure_reasons.length === 0 && <div style={{ fontSize: 12.5, color: T.muted2 }}>Nothing flagged in this period. 🎉</div>}
        {q.failure_reasons.map((r) => {
          const src = SOURCE_LABELS[r.source] || SOURCE_LABELS.fallback;
          return (
            <div key={r.reason} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
              <span style={{ width: 110, flexShrink: 0 }}>
                <Badge color={src.color}>{src.label}</Badge>
              </span>
              <span style={{ width: "clamp(120px, 34vw, 260px)", fontSize: 12.5, color: T.muted, flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={r.reason}>
                {r.reason}
              </span>
              <HBar pct={r.pct} color={src.color} />
              <span style={{ width: 44, textAlign: "right", fontSize: 12.5, fontWeight: 600, color: T.text, flexShrink: 0 }}>×{r.count}</span>
            </div>
          );
        })}
        <div style={{ fontSize: 11, color: T.muted2, marginTop: 12 }}>
          <b style={{ color: T.error }}>Failed run</b> — the whole video failed · {" "}
          <b style={{ color: T.amber }}>Quality fallback</b> — video delivered, but a scene degraded (e.g. still image instead of animation) · {" "}
          <b style={{ color: T.cyan }}>Quality check</b> — the automatic reviewer rejected a scene and it was regenerated
        </div>
      </Card>
    </>
  );
}
