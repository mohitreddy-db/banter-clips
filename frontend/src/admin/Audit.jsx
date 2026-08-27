import { useState } from "react";
import { api } from "../lib/api.js";
import { Card, LoadingOrError, PageHead, T, Table, timeAgo, useFetch } from "./ui.jsx";

const ACTION_COLOR = (a) =>
  a.includes("delete") || a.includes("block_") || a.includes("pause") || a.includes("cancel") ? T.error
  : a.includes("grant") || a.includes("resume") || a.includes("unblock") ? T.green
  : a.includes("set_") ? T.amber
  : T.cyan;

export default function AdminAudit() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const { data, error, loading, reload } = useFetch(
    () => api.adminAudit({ page, action, admin_email: adminEmail }),
    [page, action, adminEmail]
  );

  const select = { padding: "8px 12px", fontSize: 12.5, borderRadius: 9, border: `1px solid ${T.border}`, background: T.panel, color: T.text };

  return (
    <>
      <PageHead
        title="Audit Log"
        sub="Every mutating admin action, append-only — rows can never be edited or deleted from the console."
        right={
          data && (
            <>
              <select value={adminEmail} onChange={(e) => { setAdminEmail(e.target.value); setPage(1); }} style={select}>
                <option value="">All admins</option>
                {data.admins.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
              <select value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} style={select}>
                <option value="">All actions</option>
                {data.actions.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </>
          )
        }
      />
      <Card>
        <LoadingOrError loading={loading} error={error} reload={reload} />
        {data && (
          <>
            <Table
              columns={[
                { key: "at", label: "WHEN", render: (r) => timeAgo(r.at) },
                { key: "admin", label: "WHO", render: (r) => <span style={{ color: T.text, fontWeight: 600 }}>{r.admin}</span> },
                { key: "action", label: "ACTION", render: (r) => <span style={{ color: ACTION_COLOR(r.action), fontWeight: 700 }}>{r.action.toUpperCase()}</span> },
                { key: "target", label: "TARGET", maxWidth: 260 },
                { key: "reason", label: "REASON", maxWidth: 300, render: (r) => (r.reason ? `“${r.reason}”` : <span style={{ color: T.muted2 }}>—</span>) },
              ]}
              rows={data.entries}
              empty="No admin actions logged yet — they appear as you use the console's mutating controls."
            />
            <div style={{ display: "flex", marginTop: 12, fontSize: 11.5, color: T.muted2 }}>
              {data.total} total
              <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                {page > 1 && <button className="ghost-btn" style={{ padding: "5px 12px", fontSize: 12 }} onClick={() => setPage(page - 1)}>← Prev</button>}
                {page * data.page_size < data.total && <button className="ghost-btn" style={{ padding: "5px 12px", fontSize: 12 }} onClick={() => setPage(page + 1)}>Next →</button>}
              </span>
            </div>
          </>
        )}
      </Card>
    </>
  );
}
