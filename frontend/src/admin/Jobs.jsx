import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import {
  Card, HBar, Kpi, LoadingOrError, PageHead, T, Table, statusBadge,
  fmtMoney, timeAgo, useFetch,
} from "./ui.jsx";

export default function AdminJobs() {
  const { data, error, loading, reload } = useFetch(() => api.adminJobs(), []);
  // The live view refreshes itself — this is the page you watch during an incident.
  useEffect(() => {
    const t = setInterval(reload, 15000);
    return () => clearInterval(t);
  }, [reload]);

  return (
    <>
      <PageHead
        title="Generation Jobs"
        sub={
          data ? (
            <span style={{ color: data.worker.alive ? T.green : T.error }}>
              ● worker {data.worker.alive ? `alive — heartbeat ${timeAgo(data.worker.last_beat)}` : "DOWN — no recent heartbeat"}
              {data.worker.name && ` · ${data.worker.name}`}
            </span>
          ) : "…"
        }
      />
      <LoadingOrError loading={loading} error={error} reload={reload} />
      {data && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
            <Kpi label="RUNNING" value={data.depth.running} tone={data.depth.running ? "good" : undefined} />
            <Kpi label="QUEUED" value={data.depth.queued} />
            <Kpi label="FAILED (24H)" value={data.failed_24h} tone={data.failed_24h ? "warn" : undefined} />
            <Kpi label="SUCCESS (24H)" value={data.success_rate_24h === null ? "—" : `${data.success_rate_24h}%`} />
            <Kpi label="AVG GEN TIME" value={data.avg_generation_seconds ? `${Math.round(data.avg_generation_seconds / 60)}m ${Math.round(data.avg_generation_seconds % 60)}s` : "—"} />
            <Kpi label="SPEND TODAY" value={fmtMoney(data.spend_today)} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.8fr) minmax(280px, 1fr)", gap: 16 }} className="admin-two-col">
            <Card title="Queue" sub="latest 20 · running & queued first — retries are free, failed runs never charge the user">
              <Table
                columns={[
                  { key: "short_id", label: "JOB", render: (r) => <span style={{ color: T.muted2 }}>#{r.short_id}</span> },
                  { key: "take", label: "TAKE / USER", maxWidth: 280, render: (r) => (
                    <span>
                      <span style={{ color: T.text, fontWeight: 600 }}>{r.take.slice(0, 40)}</span>
                      <span style={{ color: T.muted2 }}> · {r.user_email}</span>
                    </span>
                  ) },
                  { key: "status", label: "STATUS", render: (r) => (
                    <span>
                      {statusBadge(r.status)}
                      {r.status === "running" && r.current_step && (
                        <span style={{ display: "block", fontSize: 10.5, color: T.cyan, marginTop: 3 }}>{r.current_step}</span>
                      )}
                      {r.error && <span style={{ display: "block", fontSize: 10.5, color: T.error, marginTop: 3 }}>{r.error.slice(0, 60)}</span>}
                    </span>
                  ) },
                  { key: "attempts", label: "TRY", align: "right" },
                  { key: "cost_usd", label: "COST", align: "right", render: (r) => fmtMoney(r.cost_usd, "—") },
                  { key: "created_at", label: "AGE", render: (r) => timeAgo(r.created_at) },
                  { key: "act", label: "", render: (r) => (
                    <span style={{ display: "flex", gap: 6 }}>
                      {r.status === "failed" && (
                        <button className="ghost-btn" style={{ padding: "4px 10px", fontSize: 11 }}
                                onClick={() => api.adminJobRetry(r.id, "admin retry").then(reload).catch(() => {})}>↻</button>
                      )}
                      {r.status === "queued" && (
                        <button className="ghost-btn" style={{ padding: "4px 10px", fontSize: 11, color: T.error }}
                                onClick={() => api.adminJobCancel(r.id, "admin cancel").then(reload).catch(() => {})}>✕</button>
                      )}
                    </span>
                  ) },
                ]}
                rows={data.jobs}
                empty="No jobs yet — the queue fills as users generate."
              />
            </Card>

            <SpendControls />
          </div>
        </>
      )}
    </>
  );
}

function SpendControls() {
  const { data, error, loading, reload } = useFetch(() => api.adminSpendSettings(), []);
  const [dailyCap, setDailyCap] = useState("");
  const [jobCap, setJobCap] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (data) {
      setDailyCap(String(data.daily_cap));
      setJobCap(String(data.job_cap));
    }
  }, [data]);

  const save = async (extra = {}) => {
    setBusy(true); setMsg("");
    try {
      await api.adminSaveSpendSettings({
        daily_cap: Number(dailyCap), job_cap: Number(jobCap), reason, ...extra,
      });
      setMsg("Saved — takes effect on the next job.");
      setReason("");
      reload();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  const label = { fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em", color: T.muted2, marginBottom: 5 };
  const input = { width: "100%", boxSizing: "border-box", padding: "9px 12px", fontSize: 13.5, borderRadius: 9, border: `1px solid ${T.border}`, background: T.panel, color: T.text };

  return (
    <Card title="Spend controls" sub="DB-backed runtime settings — audited, no .env editing">
      <LoadingOrError loading={loading} error={error} reload={reload} />
      {data && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <div style={label}>DAILY CAP (MAX_DAILY_SPEND_USD)</div>
            <input value={dailyCap} onChange={(e) => setDailyCap(e.target.value)} type="number" min="0" style={input} />
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
              <HBar pct={data.daily_cap > 0 ? (data.spent_24h / data.daily_cap) * 100 : 0}
                    color={data.spent_24h >= 0.8 * data.daily_cap ? T.error : T.cyan} height={7} />
              <span style={{ fontSize: 11, color: T.muted2, flexShrink: 0 }}>
                {fmtMoney(data.spent_24h)} used (24h)
              </span>
            </div>
          </div>
          <div>
            <div style={label}>PER-JOB CAP (MAX_JOB_COST_USD)</div>
            <input value={jobCap} onChange={(e) => setJobCap(e.target.value)} type="number" min="0" style={input} />
          </div>
          <div>
            <div style={label}>REASON — required, feeds the audit log</div>
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. raising for launch week" style={input} />
          </div>
          <button className="grad-btn" style={{ padding: "10px 16px", fontSize: 13 }} disabled={busy || !reason.trim()} onClick={() => save()}>
            {busy ? "Saving…" : "Save caps"}
          </button>

          <div className="panel" style={{ padding: 14, border: "1px solid rgba(240,84,108,.4)", borderRadius: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: ".08em", color: T.error, marginBottom: 6 }}>⚠ KILL SWITCH</div>
            <div style={{ fontSize: 12, color: T.muted, marginBottom: 10 }}>
              {data.paused
                ? "Generation is PAUSED — every new job is refused."
                : "Pause all generation immediately. New jobs are refused until resumed; the mechanism from the balance incident."}
            </div>
            <button
              className="ghost-btn"
              style={{ padding: "9px 14px", fontSize: 12.5, width: "100%",
                       color: data.paused ? T.green : "#fff",
                       background: data.paused ? "transparent" : T.error,
                       borderColor: data.paused ? T.green : T.error }}
              disabled={busy || !reason.trim()}
              title={!reason.trim() ? "Enter a reason first" : undefined}
              onClick={() => save({ paused: !data.paused })}
            >
              {data.paused ? "Resume generation" : "Pause all generation"}
            </button>
          </div>
          {msg && <div style={{ fontSize: 12, color: msg.startsWith("Saved") ? T.green : T.error }}>{msg}</div>}
        </div>
      )}
    </Card>
  );
}
