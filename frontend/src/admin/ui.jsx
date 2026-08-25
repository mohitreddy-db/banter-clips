import { useCallback, useEffect, useState } from "react";

/**
 * Shared building blocks for the admin console (Figma frames 15–23).
 * Same conventions as the rest of the app: inline styles + the --app-*
 * variables, no component or chart library — bars are plain divs.
 */

export const T = {
  text: "var(--app-text)",
  muted: "var(--app-muted)",
  muted2: "var(--app-muted2)",
  cyan: "var(--app-cyan)",
  green: "var(--app-green)",
  error: "var(--app-error)",
  amber: "#e19e3c",
  purple: "#7b2ff7",
  surface: "var(--app-surface)",
  panel: "var(--app-panel)",
  border: "var(--app-border)",
};

export const fmtMoney = (v, dash = "—") =>
  v === null || v === undefined ? dash : `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export const fmtNum = (v, dash = "—") =>
  v === null || v === undefined ? dash : Number(v).toLocaleString();
export const fmtPct = (v, dash = "—") => (v === null || v === undefined ? dash : `${v}%`);

export function timeAgo(iso) {
  if (!iso) return "—";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function useFetch(fn, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    setError("");
    fn()
      .then(setData)
      .catch((e) => setError(e.message || "Request failed"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload };
}

export function Card({ title, sub, right, children, style }) {
  return (
    <div className="card" style={{ padding: 20, borderRadius: 16, ...style }}>
      {(title || right) && (
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: sub ? 2 : 14 }}>
          {title && <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{title}</span>}
          <span style={{ marginLeft: "auto" }}>{right}</span>
        </div>
      )}
      {sub && <div style={{ fontSize: 11, color: T.muted2, marginBottom: 14 }}>{sub}</div>}
      {children}
    </div>
  );
}

export function Kpi({ label, value, note, tone }) {
  const noteColor = tone === "bad" ? T.error : tone === "warn" ? T.amber : tone === "good" ? T.green : T.muted;
  const valueColor = tone === "bad" ? T.error : tone === "good" ? T.green : T.text;
  return (
    <div className="card" style={{ padding: "14px 16px", borderRadius: 14, borderColor: tone === "bad" ? "rgba(240,84,108,.5)" : undefined }}>
      <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em", color: tone === "bad" ? "rgba(240,84,108,.8)" : T.muted2 }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 800, color: valueColor, margin: "6px 0 4px" }}>{value}</div>
      {note && <div style={{ fontSize: 10.5, fontWeight: 600, color: noteColor }}>{note}</div>}
    </div>
  );
}

export function HBar({ pct, color = T.cyan, height = 10, track = true, style }) {
  return (
    <div style={{ flex: 1, height, borderRadius: 99, background: track ? "var(--app-panel)" : "transparent", overflow: "hidden", ...style }}>
      <div style={{ width: `${Math.min(100, Math.max(0, pct))}%`, height: "100%", borderRadius: 99, background: color }} />
    </div>
  );
}

export function BarRow({ label, pct, value, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
      <span style={{ width: "clamp(90px, 26vw, 150px)", fontSize: 12.5, color: T.muted, flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={label}>
        {label}
      </span>
      <HBar pct={pct} color={color} />
      <span style={{ width: "clamp(44px, 12vw, 70px)", textAlign: "right", fontSize: 12.5, fontWeight: 600, color: T.text, flexShrink: 0 }}>{value}</span>
    </div>
  );
}

export function Badge({ children, color = T.muted, bg }) {
  return (
    <span style={{ fontSize: 9.5, fontWeight: 800, letterSpacing: ".05em", padding: "3px 8px", borderRadius: 999, color, background: bg || "var(--app-panel)", whiteSpace: "nowrap" }}>
      {children}
    </span>
  );
}

export function statusBadge(status) {
  const map = {
    ready: [T.green, "READY"],
    published: [T.green, "PUBLISHED"],
    done: [T.green, "DONE"],
    failed: [T.error, "FAILED"],
    queued: [T.muted, "QUEUED"],
    uploading: [T.cyan, "UPLOADING"],
    running: [T.cyan, "RUNNING"],
    script_ready: [T.amber, "SCRIPT REVIEW"],
    connected: [T.green, "CONNECTED"],
    revoked: [T.error, "REVOKED"],
  };
  const [color, label] = map[status] || [T.cyan, (status || "").replace(/_/g, " ").toUpperCase()];
  return <Badge color={color}>{label}</Badge>;
}

export function AlertStrip({ alerts }) {
  if (!alerts?.length) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {alerts.map((a, i) => {
        const c = a.level === "error" ? T.error : T.amber;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", borderRadius: 10, border: `1px solid ${c}55`, background: `${a.level === "error" ? "rgba(240,84,108,.09)" : "rgba(225,158,60,.09)"}` }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
              {a.level === "error" ? "⚠" : "↗"} {a.message}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Minimal data table matching the console look. columns: [{key,label,width,align,render}] */
export function Table({ columns, rows, empty = "Nothing here yet.", onRowClick }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ textAlign: c.align || "left", padding: "8px 10px", fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em", color: T.muted2, borderBottom: `1px solid ${T.border}`, whiteSpace: "nowrap" }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={columns.length} style={{ padding: 18, color: T.muted2 }}>{empty}</td></tr>
          )}
          {rows.map((row, i) => (
            <tr
              key={row.id || i}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              style={{ cursor: onRowClick ? "pointer" : "default" }}
              onMouseEnter={(e) => onRowClick && (e.currentTarget.style.background = "rgba(34,211,238,.05)")}
              onMouseLeave={(e) => onRowClick && (e.currentTarget.style.background = "transparent")}
            >
              {columns.map((c) => (
                <td key={c.key} style={{ padding: "9px 10px", textAlign: c.align || "left", color: T.muted, borderBottom: `1px solid ${T.border}55`, maxWidth: c.maxWidth, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {c.render ? c.render(row) : row[c.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ChipRow({ options, value, onChange }) {
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            style={{
              padding: "7px 13px", borderRadius: 9, fontSize: 12, fontWeight: on ? 600 : 500,
              cursor: "pointer", border: `1px solid ${on ? T.cyan : T.border}`,
              background: on ? "rgba(34,211,238,.12)" : "var(--app-panel)",
              color: on ? T.text : o.danger ? T.error : T.muted,
            }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** Same overlay pattern as the catalog page: centred dialog, full page on phones. */
export function Dialog({ children, onClose, wide }) {
  return (
    <div
      onClick={onClose}
      className="admin-dialog-overlay"
      style={{ position: "fixed", inset: 0, zIndex: 120, background: "rgba(4,6,12,.74)", backdropFilter: "blur(6px)", display: "grid", placeItems: "center", padding: "clamp(12px, 3vw, 28px)", animation: "fadeUp .18s ease both" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card app-font admin-dialog"
        style={{ padding: "clamp(16px, 4vw, 28px)", borderRadius: "clamp(14px, 3vw, 20px)", maxWidth: wide ? 900 : undefined }}
      >
        {children}
      </div>
    </div>
  );
}

export function PageHead({ title, sub, right }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
      <div>
        <h2 style={{ margin: 0, fontSize: "clamp(19px, 4vw, 22px)", fontWeight: 800, color: T.text }}>{title}</h2>
        {sub && <div style={{ marginTop: 4, fontSize: 12.5, color: T.muted }}>{sub}</div>}
      </div>
      <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>{right}</div>
    </div>
  );
}

export function LoadingOrError({ loading, error, reload }) {
  if (loading) return <div style={{ padding: 30, color: T.muted2, fontSize: 13 }}>Loading…</div>;
  if (error)
    return (
      <div style={{ padding: 30, fontSize: 13, color: T.error }}>
        {error}{" "}
        <button className="ghost-btn" style={{ marginLeft: 10, padding: "6px 12px", fontSize: 12 }} onClick={reload}>
          Retry
        </button>
      </div>
    );
  return null;
}
