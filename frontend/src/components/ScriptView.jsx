/**
 * The script, human-readable: cast, world, and every shot with its
 * dialogue. Rendered inside the approval step and the "Show script" dialog.
 * `script` is the plan JSON the backend stores on the clip.
 */

const label = { fontSize: 10.5, fontWeight: 700, letterSpacing: 0.8, color: "var(--app-muted2)" };

export default function ScriptView({ script }) {
  if (!script) return null;
  const cast = script.cast || [];
  const scenes = script.scenes || [];
  const byId = Object.fromEntries(cast.map((m) => [m.id, m]));
  const ctx = script._context || null;
  const world = scenes[0]?.venue;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div>
        <div style={{ fontWeight: 800, fontSize: 17, color: "var(--app-text)", lineHeight: 1.3 }}>
          “{script.title}”
        </div>
        <div style={{ fontSize: 12, color: "var(--app-muted)", marginTop: 4 }}>
          {scenes.length} shots · {Math.round(scenes.reduce((t, s) => t + (s.seconds || 0), 0))}s
          {script.style ? ` · ${script.style}` : ""}
        </div>
      </div>

      {ctx && (ctx.storylines?.length || ctx.recent?.length) ? (
        <div className="panel" style={{ padding: "10px 12px", borderRadius: 10, fontSize: 12, color: "var(--app-muted)", lineHeight: 1.5 }}>
          <span style={label}>BUILT ON TODAY'S REAL CONTEXT</span>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {[...(ctx.recent || []), ...(ctx.storylines || [])].slice(0, 4).map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {world && (
        <div style={{ fontSize: 12.5, color: "var(--app-muted)", lineHeight: 1.5 }}>
          <span style={label}>LOCATION (every shot)&nbsp;&nbsp;</span>
          {world}
        </div>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {cast.map((m) => (
          <span key={m.id} title={`${m.look} — wearing ${m.wardrobe}`}
                style={{ fontSize: 11.5, fontWeight: 600, padding: "4px 10px", borderRadius: 999, border: "1px solid var(--app-border)", color: "var(--app-text)" }}>
            {m.name}
          </span>
        ))}
      </div>

      {scenes.map((s, i) => {
        const speaker = byId[s.speaker_id];
        return (
          <div key={i} className="panel" style={{ padding: "12px 14px", borderRadius: 12, display: "flex", flexDirection: "column", gap: 7 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, fontWeight: 800, color: "var(--app-cyan)" }}>
                SHOT {i + 1}
              </span>
              <span style={{ fontSize: 11, color: "var(--app-muted2)" }}>
                {s.seconds}s · {s.beat}{s.shot_size ? ` · ${s.shot_size}` : ""}
                {s.camera_move ? ` · ${s.camera_move}` : ""}
              </span>
            </div>
            <div style={{ fontSize: 13.5, color: "var(--app-text)", lineHeight: 1.5 }}>{s.action}</div>
            {s.beats && (
              <div style={{ fontSize: 12, color: "var(--app-muted)", lineHeight: 1.45 }}>
                <span style={label}>TIMING&nbsp;&nbsp;</span>{s.beats}
              </div>
            )}
            {s.expression && (
              <div style={{ fontSize: 12, color: "var(--app-muted)", lineHeight: 1.45 }}>
                <span style={label}>EXPRESSION&nbsp;&nbsp;</span>{s.expression}
              </div>
            )}
            {s.line ? (
              <div style={{ borderLeft: "3px solid var(--app-cyan)", padding: "6px 10px", background: "rgba(34,211,238,.06)", borderRadius: "0 8px 8px 0" }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--app-cyan)" }}>
                  {(speaker?.name || s.speaker_id || "VOICE").toUpperCase()}
                  {s.delivery ? <span style={{ color: "var(--app-muted2)", fontWeight: 600 }}> · {s.delivery}</span> : null}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.45, marginTop: 2 }}>
                  “{s.line}”
                </div>
              </div>
            ) : (
              <div style={{ fontSize: 11.5, color: "var(--app-muted2)", fontStyle: "italic" }}>
                — silent reaction shot —
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** "Show script" dialog wrapper — full page on phones, wide on desktop. */
export function ScriptDialog({ script, onClose }) {
  return (
    <div
      onClick={onClose}
      className="admin-dialog-overlay"
      style={{ position: "fixed", inset: 0, zIndex: 130, background: "rgba(4,6,12,.74)", backdropFilter: "blur(6px)", display: "grid", placeItems: "center", padding: "clamp(12px, 3vw, 28px)", animation: "fadeUp .18s ease both" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card app-font admin-dialog"
        style={{ maxWidth: 640, padding: "clamp(16px, 4vw, 26px)", borderRadius: "clamp(14px, 3vw, 20px)" }}
      >
        <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
          <span style={{ fontWeight: 800, fontSize: 16, color: "var(--app-text)" }}>📝 Script</span>
          <button onClick={onClose} aria-label="Close"
                  style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--app-muted)", fontSize: 24, cursor: "pointer", lineHeight: 1, padding: "2px 8px" }}>
            ×
          </button>
        </div>
        <ScriptView script={script} />
      </div>
    </div>
  );
}
