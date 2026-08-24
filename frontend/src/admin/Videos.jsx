import { useState } from "react";
import { api } from "../lib/api.js";
import {
  Badge, Card, ChipRow, Dialog, LoadingOrError, PageHead, T, statusBadge,
  fmtMoney, fmtNum, timeAgo, useFetch,
} from "./ui.jsx";

const FILTERS = [
  { value: "", label: "All" },
  { value: "status:failed", label: "Failed", danger: true },
  { value: "status:flagged", label: "Flagged", danger: true },
  { value: "status:processing", label: "Processing" },
  { value: "status:published", label: "Published" },
  { value: "sport:NBA", label: "NBA" },
  { value: "sport:NFL", label: "NFL" },
  { value: "sport:Soccer", label: "Soccer" },
  { value: "sport:MLB", label: "MLB" },
];

export default function AdminVideos() {
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState(null);
  const [kind, value] = filter.split(":");
  const { data, error, loading, reload } = useFetch(
    () => api.adminVideos({ page, status: kind === "status" ? value : "", sport: kind === "sport" ? value : "" }),
    [filter, page]
  );

  return (
    <>
      <PageHead
        title="All Videos"
        sub={data ? `${fmtNum(data.total)} videos · failed & flagged first — quality triage lives here.` : "…"}
      />
      <ChipRow options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />
      <LoadingOrError loading={loading} error={error} reload={reload} />

      {data && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: 14 }}>
            {data.videos.length === 0 && <div style={{ color: T.muted2, fontSize: 13 }}>No videos match this filter.</div>}
            {data.videos.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => setOpenId(v.id)}
                className="card"
                style={{ textAlign: "left", padding: 10, borderRadius: 14, cursor: "pointer", borderColor: v.status === "failed" ? "rgba(240,84,108,.5)" : v.warnings > 0 ? "rgba(225,158,60,.5)" : undefined }}
              >
                <div style={{ height: 110, borderRadius: 10, background: v.thumb_gradient || "linear-gradient(140deg, #0f2436, #131a2b)", position: "relative", marginBottom: 10 }}>
                  <span style={{ position: "absolute", top: 8, left: 8 }}>{statusBadge(v.published ? "published" : v.status)}</span>
                  {v.warnings > 0 && (
                    <span style={{ position: "absolute", top: 8, right: 8 }}>
                      <Badge color={T.amber}>⚑ {v.warnings}</Badge>
                    </span>
                  )}
                  <span style={{ position: "absolute", bottom: 8, left: 8, fontSize: 10, fontWeight: 700, color: "rgba(244,246,251,.85)" }}>
                    {v.duration_target}s · {v.resolution}
                  </span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v.take}</div>
                <div style={{ fontSize: 10.5, color: T.muted2, margin: "4px 0" }}>
                  {v.sport} · {v.tone} · {v.user_email}
                </div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: v.status === "failed" ? T.error : T.muted }}>
                  {v.cost_usd ? fmtMoney(v.cost_usd) : v.is_simulated ? "simulated" : "$0.00"} · {timeAgo(v.created_at)}
                </div>
              </button>
            ))}
          </div>
          <div style={{ display: "flex", fontSize: 11.5, color: T.muted2 }}>
            Page {page} · {data.total} total
            <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              {page > 1 && <button className="ghost-btn" style={{ padding: "5px 12px", fontSize: 12 }} onClick={() => setPage(page - 1)}>← Prev</button>}
              {page * data.page_size < data.total && <button className="ghost-btn" style={{ padding: "5px 12px", fontSize: 12 }} onClick={() => setPage(page + 1)}>Next →</button>}
            </span>
          </div>
        </>
      )}

      {openId && <VideoDrawer id={openId} onClose={() => setOpenId(null)} onChanged={reload} />}
    </>
  );
}

function VideoDrawer({ id, onClose, onChanged }) {
  const { data: v, error, loading, reload } = useFetch(() => api.adminVideoDetail(id), [id]);
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const run = async (name, fn) => {
    setBusy(name); setActionError("");
    try { await fn(); onChanged(); } catch (e) { setActionError(e.message); } finally { setBusy(""); }
  };

  const prov = v?.provenance || {};
  return (
    <Dialog onClose={() => !busy && onClose()} wide>
      <LoadingOrError loading={loading} error={error} reload={reload} />
      {v && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: "min(680px, 84vw)", maxHeight: "78vh", overflowY: "auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontSize: 16, fontWeight: 800, color: T.text }}>“{v.take}”</span>
            {statusBadge(v.status)}
            <button onClick={onClose} aria-label="Close" style={{ marginLeft: "auto", background: "none", border: "none", color: T.muted, fontSize: 22, cursor: "pointer" }}>×</button>
          </div>
          <div style={{ fontSize: 11.5, color: T.muted2, marginTop: -8 }}>
            {v.sport} · {v.tone} · {v.duration_target}s target ({v.duration_seconds ?? "—"}s actual) · {v.resolution} ·{" "}
            {v.user_email} · {timeAgo(v.created_at)} · {v.watermarked ? "watermarked" : "clean"} ·{" "}
            cost <b style={{ color: T.text }}>{fmtMoney(v.cost_usd)}</b>
            {v.is_simulated && " · SIMULATED"}
          </div>

          {v.video_url && (
            <video src={v.video_url.startsWith("http") ? v.video_url : undefined} controls
                   style={{ maxHeight: 260, borderRadius: 12, background: "#000", display: v.video_url.startsWith("http") ? "block" : "none" }} />
          )}
          {v.error && <div className="panel" style={{ padding: 12, fontSize: 12.5, color: T.error }}>Error: {v.error}</div>}

          {(prov.warnings || []).length > 0 && (
            <div className="panel" style={{ padding: 12, border: "1px solid rgba(225,158,60,.5)" }}>
              <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em", color: T.amber, marginBottom: 6 }}>PIPELINE WARNINGS</div>
              {prov.warnings.map((w, i) => <div key={i} style={{ fontSize: 12, color: T.muted }}>• {w}</div>)}
            </div>
          )}

          {(prov.scenes || []).length > 0 && (
            <div>
              <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em", color: T.muted2, marginBottom: 6 }}>
                PROVENANCE — PER-SCENE COSTS & REVIEW VERDICTS
              </div>
              {prov.scenes.map((s) => (
                <div key={s.index} className="panel" style={{ padding: "10px 12px", marginBottom: 6, fontSize: 12, color: T.muted }}>
                  <b style={{ color: T.text }}>Scene {s.index + 1}</b> · {s.attempts} attempt{s.attempts === 1 ? "" : "s"} · {fmtMoney(s.cost_usd)}
                  {(s.hard || []).map((h, i) => <div key={`h${i}`} style={{ color: T.error }}>✕ {h}</div>)}
                  {(s.soft || []).map((h, i) => <div key={`s${i}`} style={{ color: T.amber }}>△ {h}</div>)}
                  {s.notes && <div style={{ color: T.muted2 }}>{s.notes}</div>}
                </div>
              ))}
              {prov.models && (
                <div style={{ fontSize: 11, color: T.muted2 }}>
                  models: {Object.entries(prov.models).map(([k, val]) => `${k}=${val}`).join(" · ")}
                </div>
              )}
            </div>
          )}

          <div>
            <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em", color: T.muted2, marginBottom: 6 }}>PUBLISH HISTORY</div>
            {v.publishes.length === 0 && <div style={{ fontSize: 12.5, color: T.muted2 }}>Never published.</div>}
            {v.publishes.map((p) => (
              <div key={p.id} style={{ fontSize: 12.5, color: T.muted, marginBottom: 4 }}>
                {statusBadge(p.status)} @{p.handle || "?"} · {timeAgo(p.created_at)}
                {p.external_url && <> · <a href={p.external_url} target="_blank" rel="noreferrer" style={{ color: T.cyan }}>view ↗</a></>}
                {p.error && <span style={{ color: T.error }}> · {p.error}</span>}
              </div>
            ))}
          </div>

          {actionError && <div style={{ fontSize: 12.5, color: T.error }}>{actionError}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            {v.status === "failed" && (
              <button className="grad-btn" style={{ padding: "9px 16px", fontSize: 12.5 }} disabled={!!busy}
                      onClick={() => run("retry", () => api.adminVideoRetry(v.id, "admin retry").then(reload))}>
                {busy === "retry" ? "Retrying…" : "↻ Retry generation"}
              </button>
            )}
            {!confirmDelete ? (
              <button className="ghost-btn" style={{ padding: "9px 16px", fontSize: 12.5, color: T.error }} disabled={!!busy}
                      onClick={() => setConfirmDelete(true)}>
                Delete clip…
              </button>
            ) : (
              <button className="ghost-btn" style={{ padding: "9px 16px", fontSize: 12.5, color: "#fff", background: T.error, border: "none" }} disabled={!!busy}
                      onClick={() => run("delete", () => api.adminVideoDelete(v.id, "removed by operator").then(onClose))}>
                {busy === "delete" ? "Deleting…" : "Confirm delete (removes files)"}
              </button>
            )}
          </div>
        </div>
      )}
    </Dialog>
  );
}
