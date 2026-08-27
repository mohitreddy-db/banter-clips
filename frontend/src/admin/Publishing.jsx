import { api } from "../lib/api.js";
import {
  Badge, Card, Kpi, LoadingOrError, PageHead, T, Table, statusBadge,
  fmtNum, fmtPct, timeAgo, useFetch,
} from "./ui.jsx";

export default function AdminPublishing() {
  const { data, error, loading, reload } = useFetch(() => api.adminPublishing(), []);

  if (loading || error) {
    return (
      <>
        <PageHead title="Social Publishing" sub="Distribution health across connected platforms." />
        <LoadingOrError loading={loading} error={error} reload={reload} />
      </>
    );
  }

  const ig = data.platforms[0];
  return (
    <>
      <PageHead title="Social Publishing" sub="Distribution health — Instagram is live; more platforms land with the roadmap." />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
        <Kpi label="POSTS (24H)" value={fmtNum(data.posts_today)} />
        <Kpi label="PUBLISHED (7D)" value={fmtNum(data.published_7d)} tone="good" />
        <Kpi label="FAILED (7D)" value={fmtNum(data.failed_7d)} tone={data.failed_7d ? "warn" : undefined} />
        <Kpi label="SUCCESS RATE (7D)" value={fmtPct(data.success_rate_7d)} />
        <Kpi label="IN FLIGHT" value={fmtNum(data.in_flight)} note="queued or uploading" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(280px, 1fr) minmax(0, 1.8fr)", gap: 16 }} className="admin-two-col">
        <Card title="Platforms" sub="OAuth + API health per platform">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 13.5, fontWeight: 700, color: T.text }}>{ig.label}</span>
            <Badge color={T.green}>● LIVE</Badge>
          </div>
          <div style={{ fontSize: 12.5, color: T.muted, lineHeight: 2 }}>
            Connected accounts <b style={{ color: T.text }}>{ig.connected_accounts}</b><br />
            Tokens expiring &lt; 7 days <b style={{ color: ig.expiring_tokens ? T.amber : T.text }}>{ig.expiring_tokens}</b><br />
            Revoked accounts <b style={{ color: ig.revoked_accounts ? T.error : T.text }}>{ig.revoked_accounts}</b>
          </div>
          <div style={{ borderTop: `1px solid ${T.border}`, margin: "14px 0" }} />
          {data.coming_soon.map((p) => (
            <div key={p} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: T.muted2 }}>{p}</span>
              <Badge color={T.muted2}>COMING SOON</Badge>
            </div>
          ))}
          <div style={{ fontSize: 11, color: T.muted2, marginTop: 8 }}>
            Expired tokens surface below as "failed — OAuth" and auto-refresh inside the 15-day window.
          </div>
        </Card>

        <Card title="Publish queue" sub="latest 12 · container → poll → publish → permalink">
          <Table
            columns={[
              { key: "take", label: "VIDEO", maxWidth: 240, render: (r) => <span style={{ color: T.text, fontWeight: 600 }}>{r.take}</span> },
              { key: "handle", label: "ACCOUNT", render: (r) => (r.handle ? `@${r.handle}` : "—") },
              { key: "status", label: "STATUS", render: (r) => (
                <span>
                  {statusBadge(r.status)}
                  {r.error && <span style={{ display: "block", fontSize: 10.5, color: T.error, marginTop: 3 }}>{r.error.slice(0, 50)}</span>}
                </span>
              ) },
              { key: "created_at", label: "WHEN", render: (r) => timeAgo(r.created_at) },
              { key: "link", label: "", render: (r) =>
                r.external_url ? <a href={r.external_url} target="_blank" rel="noreferrer" style={{ color: T.cyan, textDecoration: "none" }}>view ↗</a> : null },
              { key: "act", label: "", render: (r) =>
                r.status === "failed" ? (
                  <button className="ghost-btn" style={{ padding: "4px 10px", fontSize: 11 }}
                          onClick={() => api.adminPublishRetry(r.id, "admin retry").then(reload).catch(() => {})}>
                    ↻ Retry
                  </button>
                ) : null },
            ]}
            rows={data.queue}
            empty="No publishes yet."
          />
        </Card>
      </div>
    </>
  );
}
