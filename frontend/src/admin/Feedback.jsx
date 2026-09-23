import { useState } from "react";
import { api } from "../lib/api.js";
import { Badge, Card, ChipRow, Kpi, LoadingOrError, PageHead, T, timeAgo, useFetch } from "./ui.jsx";

/**
 * Feedback inbox — everything left on the public /feedback page, newest
 * first. Triage is a status (new → seen → resolved) plus a private note;
 * both land in the audit log.
 */

const CATEGORY = {
  bug: { icon: "🐛", color: T.error },
  idea: { icon: "💡", color: T.cyan },
  praise: { icon: "🎉", color: T.green },
  other: { icon: "💬", color: T.muted },
};
const STATUS_COLOR = { new: T.amber, seen: T.cyan, resolved: T.green };

function Entry({ f, onChange }) {
  const [note, setNote] = useState(f.admin_note || "");
  const [busy, setBusy] = useState(false);
  const cat = CATEGORY[f.category] || CATEGORY.other;

  const update = async (body) => {
    setBusy(true);
    try {
      const res = await api.adminFeedbackUpdate(f.id, body);
      onChange({ ...f, status: res.status, admin_note: res.admin_note });
    } catch (e) {
      alert(e.message);
    }
    setBusy(false);
  };

  return (
    <div style={{ padding: "14px 16px", borderBottom: `1px solid ${T.border}`, display: "flex", flexDirection: "column", gap: 10, opacity: f.status === "resolved" ? 0.7 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontSize: 12.5 }}>
        <Badge color={cat.color}>{cat.icon} {f.category}</Badge>
        <Badge color={STATUS_COLOR[f.status] || T.muted}>{f.status}</Badge>
        {f.rating && <span title={`${f.rating} of 5`}>{"⭐".repeat(f.rating)}</span>}
        <span style={{ color: T.muted }}>
          {f.name || (f.user_id ? "signed-in user" : "anonymous")}
          {f.email ? ` · ${f.email}` : ""}
        </span>
        <span style={{ marginLeft: "auto", color: T.muted2 }} title={f.at}>{timeAgo(f.at)}{f.page ? ` · ${f.page}` : ""}</span>
      </div>
      <div style={{ fontSize: 14, color: T.text, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{f.message}</div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => note !== (f.admin_note || "") && update({ admin_note: note })}
          placeholder="private note…"
          style={{ flex: 1, minWidth: 180, padding: "7px 10px", fontSize: 12.5, color: T.text, background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8 }}
        />
        {["new", "seen", "resolved"].filter((s) => s !== f.status).map((s) => (
          <button key={s} disabled={busy} onClick={() => update({ status: s })}
                  style={{ padding: "7px 12px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", color: s === "resolved" ? "#04121a" : T.text, background: s === "resolved" ? T.green : T.panel, border: `1px solid ${T.border}` }}>
            {s === "resolved" ? "✓ Resolve" : `Mark ${s}`}
          </button>
        ))}
      </div>
      {f.user_agent && <div style={{ fontSize: 10.5, color: T.muted2 }}>{f.user_agent}</div>}
    </div>
  );
}

export default function AdminFeedback() {
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useFetch(
    () => api.adminFeedback({ status, category, page }), [status, category, page],
  );
  // Triage edits show immediately without refetching (which would drop the
  // note input's focus); a reload replaces them with the server's truth.
  const [patched, setPatched] = useState({});
  const patch = (updated) => setPatched((p) => ({ ...p, [updated.id]: updated }));
  const entries = (data?.entries || []).map((e) => ({ ...e, ...(patched[e.id] || {}) }));

  return (
    <>
      <PageHead title="Feedback" sub="Everything left on the public feedback page — bugs, ideas, praise." right={<button className="ghost-btn" style={{ padding: "7px 12px", fontSize: 12 }} onClick={reload}>↻ Refresh</button>} />
      <LoadingOrError loading={loading && !data} error={error} reload={reload} />
      {data && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            <Kpi label="New" value={data.counts.new} tone={data.counts.new ? "amber" : undefined} />
            <Kpi label="Seen" value={data.counts.seen} />
            <Kpi label="Resolved" value={data.counts.resolved} />
            <Kpi label="Avg rating" value={data.avg_rating ? `${data.avg_rating} / 5` : "—"} note="where given" />
          </div>
          <Card
            title={`${data.total} note${data.total === 1 ? "" : "s"}`}
            right={
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <ChipRow options={[{ value: "", label: "all" }, { value: "new", label: "new" }, { value: "seen", label: "seen" }, { value: "resolved", label: "resolved" }]} value={status} onChange={(v) => { setStatus(v); setPage(1); }} />
                <ChipRow options={[{ value: "", label: "any type" }, { value: "bug", label: "🐛 bug" }, { value: "idea", label: "💡 idea" }, { value: "praise", label: "🎉 praise" }, { value: "other", label: "💬 other" }]} value={category} onChange={(v) => { setCategory(v); setPage(1); }} />
              </div>
            }
          >
            {entries.length === 0 && <div style={{ padding: 18, color: T.muted2 }}>Nothing here yet.</div>}
            {entries.map((f) => <Entry key={f.id} f={f} onChange={patch} />)}
            {data.total > data.page_size && (
              <div style={{ display: "flex", gap: 8, padding: 12, justifyContent: "flex-end", fontSize: 12.5 }}>
                <button className="ghost-btn" disabled={page <= 1} onClick={() => setPage(page - 1)} style={{ padding: "6px 12px" }}>← Newer</button>
                <span style={{ alignSelf: "center", color: T.muted }}>page {page} of {Math.ceil(data.total / data.page_size)}</span>
                <button className="ghost-btn" disabled={page * data.page_size >= data.total} onClick={() => setPage(page + 1)} style={{ padding: "6px 12px" }}>Older →</button>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  );
}
