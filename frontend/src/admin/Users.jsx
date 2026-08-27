import { useState } from "react";
import { api } from "../lib/api.js";
import {
  Badge, Card, ChipRow, Dialog, LoadingOrError, PageHead, T, Table,
  fmtMoney, fmtNum, timeAgo, useFetch,
} from "./ui.jsx";

const FILTERS = [
  { value: "", label: "All" },
  { value: "plan:free", label: "Free" },
  { value: "plan:creator", label: "Creator" },
  { value: "status:active", label: "Active" },
  { value: "status:churned", label: "Churned" },
  { value: "status:blocked", label: "Blocked", danger: true },
];

export default function AdminUsers() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState(null);

  const [kind, value] = filter.split(":");
  const params = { q, page, plan: kind === "plan" ? value : "", status: kind === "status" ? value : "" };
  const { data, error, loading, reload } = useFetch(() => api.adminUsers(params), [q, filter, page]);
  const retention = useFetch(() => api.adminRetention(5), []);

  return (
    <>
      <PageHead
        title="Users"
        sub={data ? `${fmtNum(data.total)} accounts — the detail behind the dashboard's user widgets.` : "…"}
        right={
          <input
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1); }}
            placeholder="Search email…"
            style={{ padding: "8px 12px", fontSize: 13, borderRadius: 9, border: `1px solid ${T.border}`, background: T.panel, color: T.text, width: 200 }}
          />
        }
      />
      <ChipRow options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />

      <Card>
        <LoadingOrError loading={loading} error={error} reload={reload} />
        {data && (
          <>
            <Table
              onRowClick={(row) => setOpenId(row.id)}
              columns={[
                { key: "email", label: "USER", maxWidth: 260,
                  render: (r) => <span style={{ color: T.text, fontWeight: 600 }}>{r.email}</span> },
                { key: "plan", label: "PLAN",
                  render: (r) => <span style={{ color: r.plan === "creator" ? T.cyan : T.muted }}>{r.plan}</span> },
                { key: "created_at", label: "SIGNUP", render: (r) => new Date(r.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) },
                { key: "last_active", label: "LAST ACTIVE", render: (r) => timeAgo(r.last_active) },
                { key: "videos", label: "VIDEOS", align: "right" },
                { key: "cost_usd", label: "AI COST", align: "right", render: (r) => fmtMoney(r.cost_usd) },
                { key: "status", label: "STATUS", render: (r) =>
                  r.is_blocked ? <Badge color={T.error}>BLOCKED</Badge>
                  : r.churned ? <Badge color={T.amber}>CHURNING</Badge>
                  : <Badge color={T.green}>ACTIVE</Badge> },
              ]}
              rows={data.users}
            />
            <div style={{ display: "flex", alignItems: "center", marginTop: 12, fontSize: 11.5, color: T.muted2 }}>
              Showing {(page - 1) * data.page_size + 1}–{Math.min(page * data.page_size, data.total)} of {data.total} · sorted by last active
              <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                {page > 1 && <button className="ghost-btn" style={{ padding: "5px 12px", fontSize: 12 }} onClick={() => setPage(page - 1)}>← Prev</button>}
                {page * data.page_size < data.total && <button className="ghost-btn" style={{ padding: "5px 12px", fontSize: 12 }} onClick={() => setPage(page + 1)}>Next →</button>}
              </span>
            </div>
          </>
        )}
      </Card>

      <Card title="Retention cohorts" sub="weekly signup cohorts · % active in a 7-day window at each offset (events table)">
        <LoadingOrError loading={retention.loading} error={retention.error} reload={retention.reload} />
        {retention.data && (
          <Table
            columns={[
              { key: "cohort", label: "COHORT", render: (r) => <span style={{ color: T.text, fontWeight: 600 }}>{r.cohort}</span> },
              { key: "size", label: "SIZE", align: "right" },
              ...["d1", "d7", "d14", "d30"].map((k) => ({
                key: k, label: k.toUpperCase(), align: "right",
                render: (r) => (r[k] === null ? <span style={{ color: T.muted2 }}>—</span> : `${r[k]}%`),
              })),
            ]}
            rows={retention.data.cohorts}
          />
        )}
      </Card>

      {openId && <UserDrawer id={openId} onClose={() => setOpenId(null)} onChanged={reload} />}
    </>
  );
}

function UserDrawer({ id, onClose, onChanged }) {
  const { data: u, error, loading, reload } = useFetch(() => api.adminUserDetail(id), [id]);
  const [reason, setReason] = useState("");
  const [confirmEmail, setConfirmEmail] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");

  const run = async (name, fn) => {
    setBusy(name);
    setActionError("");
    try {
      await fn();
      onChanged();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <Dialog onClose={() => !busy && onClose()}>
      <LoadingOrError loading={loading} error={error} reload={reload} />
      {u && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: "min(520px, 82vw)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ width: 40, height: 40, borderRadius: "50%", background: T.purple, display: "grid", placeItems: "center", fontWeight: 700, color: "#fff" }}>
              {u.email[0].toUpperCase()}
            </span>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: T.text }}>{u.email}</div>
              <div style={{ fontSize: 11.5, color: T.muted2 }}>
                {u.plan} · joined {new Date(u.created_at).toLocaleDateString()} ·{" "}
                {u.stripe_url ? (
                  <a href={u.stripe_url} target="_blank" rel="noreferrer" style={{ color: T.cyan, textDecoration: "none" }}>
                    Stripe ↗
                  </a>
                ) : "no Stripe customer"}
              </div>
            </div>
            <button onClick={onClose} aria-label="Close" style={{ marginLeft: "auto", background: "none", border: "none", color: T.muted, fontSize: 22, cursor: "pointer" }}>×</button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, fontSize: 12 }}>
            {[["VIDEOS", u.videos], ["PUBLISHED", u.published], ["AI COST", fmtMoney(u.cost_usd)], ["LAST LOGIN", timeAgo(u.last_login_at)]].map(([l, v]) => (
              <div key={l} className="panel" style={{ padding: "10px 12px" }}>
                <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: ".08em", color: T.muted2 }}>{l}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text, marginTop: 4 }}>{v}</div>
              </div>
            ))}
          </div>

          <div>
            <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em", color: T.muted2, marginBottom: 6 }}>RECENT CLIPS</div>
            {u.recent_clips.length === 0 && <div style={{ fontSize: 12.5, color: T.muted2 }}>None yet.</div>}
            {u.recent_clips.map((c) => (
              <div key={c.id} style={{ fontSize: 12.5, color: T.muted, marginBottom: 4 }}>
                “{c.take.slice(0, 48)}” · {c.status} · {fmtMoney(c.cost_usd)} · {timeAgo(c.created_at)}
              </div>
            ))}
          </div>

          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (required for actions — feeds the audit log)"
            style={{ padding: "9px 12px", fontSize: 13, borderRadius: 9, border: `1px solid ${T.border}`, background: T.panel, color: T.text }}
          />
          {actionError && <div style={{ fontSize: 12.5, color: T.error }}>{actionError}</div>}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              className="ghost-btn"
              style={{ padding: "9px 14px", fontSize: 12.5, color: u.is_blocked ? T.green : T.error }}
              disabled={!!busy || !reason.trim()}
              onClick={() => run("block", () => api.adminBlockUser(u.id, !u.is_blocked, reason).then(reload))}
            >
              {busy === "block" ? "…" : u.is_blocked ? "Unblock user" : "Block user"}
            </button>
            <button
              className="ghost-btn"
              style={{ padding: "9px 14px", fontSize: 12.5, color: T.error, borderColor: "rgba(240,84,108,.6)" }}
              disabled={!!busy}
              onClick={() => setDeleting((d) => !d)}
            >
              Delete user…
            </button>
          </div>

          {deleting && (
            <div className="panel" style={{ padding: 14, border: `1px solid rgba(240,84,108,.5)` }}>
              <div style={{ fontSize: 12.5, color: T.muted, marginBottom: 8 }}>
                Full erasure: clips, media, publishes, socials, events. Cancels any live Stripe subscription. Type the user's email to confirm.
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  value={confirmEmail}
                  onChange={(e) => setConfirmEmail(e.target.value)}
                  placeholder={u.email}
                  style={{ flex: 1, padding: "9px 12px", fontSize: 13, borderRadius: 9, border: `1px solid ${T.border}`, background: "var(--app-surface)", color: T.text }}
                />
                <button
                  className="ghost-btn"
                  style={{ padding: "9px 14px", fontSize: 12.5, color: "#fff", background: T.error, border: "none" }}
                  disabled={!!busy || confirmEmail.trim().toLowerCase() !== u.email.toLowerCase() || !reason.trim()}
                  onClick={() => run("delete", () => api.adminDeleteUser(u.id, confirmEmail, reason).then(onClose))}
                >
                  {busy === "delete" ? "Deleting…" : "Delete forever"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </Dialog>
  );
}
