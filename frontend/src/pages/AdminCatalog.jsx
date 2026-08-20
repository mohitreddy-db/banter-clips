import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api, API_BASE, getToken } from "../lib/api.js";

/**
 * Admin · character catalog.
 *
 * Browse view is a compact tile grid (still + name); everything else lives
 * in a dialog opened per character. Edits write the DB layer, which
 * overrides the curated JSON by id and applies to the next generation.
 */

const SPORTS = ["NBA", "NFL", "Soccer", "MLB"];

const imgUrl = (u) => (u.startsWith("http") ? u : `${API_BASE}${u}?token=${getToken()}`);

const badgeStyle = (source) => ({
  fontSize: 10, fontWeight: 800, letterSpacing: ".06em", padding: "3px 8px",
  borderRadius: 999, textTransform: "uppercase",
  background: source === "curated" ? "rgba(34,211,238,.12)"
    : source === "admin" ? "rgba(52,226,122,.12)" : "rgba(240,173,78,.14)",
  color: source === "curated" ? "var(--app-cyan)"
    : source === "admin" ? "var(--app-green)" : "#f0ad4e",
});

function NoImage({ small = false }) {
  return (
    <div
      style={{
        width: "100%", height: "100%", display: "grid", placeItems: "center",
        background: "linear-gradient(160deg, var(--app-panel), var(--app-surface))",
        color: "var(--app-muted2)",
      }}
    >
      <div style={{ textAlign: "center", display: "grid", gap: 4, justifyItems: "center" }}>
        <svg width={small ? 26 : 38} height={small ? 26 : 38} viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          <circle cx="12" cy="9" r="3.4" />
          <path d="M5 20c.8-3.4 3.6-5 7-5s6.2 1.6 7 5" />
        </svg>
        {!small && <span style={{ fontSize: 10.5, fontWeight: 600, letterSpacing: ".04em" }}>NO IMAGE</span>}
      </div>
    </div>
  );
}

/** Small clickable tile: still + name. */
function Tile({ char, onClick }) {
  const src = char.reference_urls[0];
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex", flexDirection: "column", gap: 7, padding: 0,
        background: "none", border: "none", cursor: "pointer", textAlign: "center",
        opacity: char.active ? 1 : 0.45,
      }}
    >
      <div style={{ position: "relative", width: "100%", aspectRatio: "3/4", borderRadius: 12, overflow: "hidden", border: "1px solid var(--app-border)", background: "var(--app-panel)" }}>
        {src ? (
          <img src={imgUrl(src)} alt="" loading="lazy"
               style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
        ) : (
          <NoImage />
        )}
        {!char.active && (
          <span style={{ position: "absolute", top: 6, right: 6, fontSize: 8.5, fontWeight: 800, padding: "2px 6px", borderRadius: 999, background: "rgba(240,84,108,.85)", color: "#fff" }}>
            OFF
          </span>
        )}
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.25, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
        {char.name}
      </span>
    </button>
  );
}

function Field({ label, value, onChange, rows = 0 }) {
  const common = {
    width: "100%", boxSizing: "border-box", padding: "10px 12px", fontSize: 14,
    color: "var(--app-text)", background: "var(--app-panel)",
    border: "1px solid var(--app-border)", borderRadius: 10,
  };
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.8, color: "var(--app-muted2)" }}>
        {label}
      </span>
      {rows ? (
        <textarea rows={rows} value={value} onChange={(e) => onChange(e.target.value)} style={{ ...common, resize: "vertical" }} />
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} style={common} />
      )}
    </label>
  );
}

/** Full-detail dialog. On phones it becomes a full-height sheet. */
function Dialog({ children, onClose }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 120, background: "rgba(4,6,12,.74)",
        backdropFilter: "blur(6px)", display: "grid", placeItems: "center",
        padding: "clamp(0px, 3vw, 24px)", animation: "fadeUp .18s ease both",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card app-font"
        style={{
          width: "100%", maxWidth: 540, maxHeight: "min(92dvh, 860px)",
          overflowY: "auto", padding: "clamp(16px, 4vw, 26px)",
          borderRadius: "clamp(14px, 3vw, 20px)", boxSizing: "border-box",
        }}
      >
        {children}
      </div>
    </div>
  );
}

function CharacterDialog({ char, onSaved, onClose }) {
  const [form, setForm] = useState({
    name: char.name, look: char.look, default_wardrobe: char.default_wardrobe,
    voice_style: char.voice_style, aliases: char.aliases.join(", "),
  });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const dirty =
    form.name !== char.name || form.look !== char.look ||
    form.default_wardrobe !== char.default_wardrobe ||
    form.voice_style !== char.voice_style ||
    form.aliases !== char.aliases.join(", ");

  const run = async (kind, fn) => {
    setBusy(kind);
    setError("");
    try {
      onSaved(await fn());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const save = () => run("save", () => api.adminUpdateCharacter(char.id, {
    name: form.name, look: form.look, default_wardrobe: form.default_wardrobe,
    voice_style: form.voice_style,
    aliases: form.aliases.split(",").map((a) => a.trim()).filter(Boolean),
  }));
  const toggle = () => run("toggle", () => api.adminUpdateCharacter(char.id, { active: !char.active }));
  const regen = () => {
    if (!window.confirm(`Generate fresh reference stills for ${char.name}? Costs ~$0.10 of real image credit.`)) return;
    run("regen", () => api.adminRegenerateRefs(char.id));
  };

  return (
    <Dialog onClose={() => !busy && onClose()}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 800, fontSize: 19, color: "var(--app-text)" }}>{char.name}</span>
          <span style={badgeStyle(char.source)}>{char.source}</span>
          {!char.active && <span style={{ fontSize: 11, color: "var(--app-error)", fontWeight: 700 }}>INACTIVE</span>}
          <button onClick={onClose} aria-label="Close"
                  style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--app-muted)", fontSize: 22, cursor: "pointer", lineHeight: 1, padding: "2px 6px" }}>
            ×
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: -10 }}>
          <code style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>{char.id}</code>
          <span style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>· {char.sport}</span>
        </div>

        {/* stills */}
        <div style={{ display: "flex", gap: 10 }}>
          {(char.reference_urls.length ? char.reference_urls : [null]).map((u, i) => (
            <div key={i} style={{ width: 104, aspectRatio: "9/16", borderRadius: 10, overflow: "hidden", border: "1px solid var(--app-border)", flexShrink: 0 }}>
              {u ? (
                <img src={imgUrl(u)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
              ) : (
                <NoImage />
              )}
            </div>
          ))}
        </div>

        <Field label="NAME" value={form.name} onChange={set("name")} />
        <Field label="LOOK — physical appearance" value={form.look} onChange={set("look")} rows={3} />
        <Field label="WARDROBE — kit, colours, number" value={form.default_wardrobe} onChange={set("default_wardrobe")} rows={2} />
        <Field label="VOICE STYLE" value={form.voice_style} onChange={set("voice_style")} />
        <Field label="ALIASES — comma-separated" value={form.aliases} onChange={set("aliases")} />

        {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="grad-btn" style={{ padding: "12px 20px", fontSize: 14, opacity: dirty ? 1 : 0.5, flex: "1 1 auto" }}
                  disabled={!dirty || !!busy} onClick={save}>
            {busy === "save" ? "Saving…" : "Save changes"}
          </button>
          <button className="ghost-btn" style={{ padding: "12px 16px", fontSize: 13.5, flex: "1 1 auto" }} disabled={!!busy} onClick={regen}>
            {busy === "regen" ? "Generating…" : "↻ New stills ($0.10)"}
          </button>
        </div>
        <button
          className="ghost-btn"
          style={{ padding: "11px 16px", fontSize: 13.5, color: char.active ? "var(--app-error)" : "var(--app-green)" }}
          disabled={!!busy}
          onClick={toggle}
        >
          {busy === "toggle" ? "…" : char.active ? "Deactivate — hide from generation" : "Activate"}
        </button>
      </div>
    </Dialog>
  );
}

function AddDialog({ onCreated, onClose }) {
  const [draft, setDraft] = useState({ name: "", sport: "Soccer", look: "", default_wardrobe: "", voice_style: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (v) => setDraft((d) => ({ ...d, [k]: v }));

  const create = async () => {
    setBusy(true);
    setError("");
    try {
      onCreated(await api.adminCreateCharacter(draft));
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <Dialog onClose={() => !busy && onClose()}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <span style={{ fontWeight: 800, fontSize: 19, color: "var(--app-text)" }}>New character</span>
          <button onClick={onClose} aria-label="Close"
                  style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--app-muted)", fontSize: 22, cursor: "pointer", lineHeight: 1, padding: "2px 6px" }}>
            ×
          </button>
        </div>
        <Field label="NAME" value={draft.name} onChange={set("name")} />
        <label style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.8, color: "var(--app-muted2)" }}>SPORT</span>
          <select value={draft.sport} onChange={(e) => set("sport")(e.target.value)}
                  style={{ padding: "10px 12px", fontSize: 14, color: "var(--app-text)", background: "var(--app-panel)", border: "1px solid var(--app-border)", borderRadius: 10 }}>
            {SPORTS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <Field label="LOOK — physical appearance" value={draft.look} onChange={set("look")} rows={2} />
        <Field label="WARDROBE — kit, colours, number" value={draft.default_wardrobe} onChange={set("default_wardrobe")} rows={2} />
        <Field label="VOICE STYLE" value={draft.voice_style} onChange={set("voice_style")} />
        {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}
        <button className="grad-btn" style={{ padding: "13px 20px", fontSize: 14.5 }}
                disabled={busy || draft.name.trim().length < 2} onClick={create}>
          {busy ? "Creating…" : "Create character"}
        </button>
      </div>
    </Dialog>
  );
}

export default function AdminCatalog() {
  const { user, booted } = useApp();
  const [chars, setChars] = useState(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!user?.is_admin) return;
    api.adminCatalog().then(setChars).catch((e) => setError(e.message));
  }, [user]);

  const grouped = useMemo(() => {
    const by = {};
    (chars || []).forEach((c) => (by[c.sport] = [...(by[c.sport] || []), c]));
    return by;
  }, [chars]);

  if (booted && user && !user.is_admin) return <Navigate to="/studio" replace />;
  if (!user?.is_admin) return null;

  const open = chars?.find((c) => c.id === openId) || null;
  const replace = (updated) =>
    setChars((cs) => cs.map((c) => (c.id === updated.id ? updated : c)));

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto", display: "flex", flexDirection: "column", gap: 22 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <h2 style={{ fontSize: "clamp(20px, 5vw, 24px)", fontWeight: 800, color: "var(--app-text)", margin: 0 }}>
          Character catalog
        </h2>
        <button className="grad-btn" style={{ marginLeft: "auto", padding: "10px 16px", fontSize: 13 }} onClick={() => setAdding(true)}>
          + Add
        </button>
      </div>
      <div style={{ fontSize: 12.5, color: "var(--app-muted)", marginTop: -14 }}>
        {chars ? `${chars.length} characters · tap one to edit · changes apply to the next generation` : "loading…"}
      </div>

      {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}

      {Object.entries(grouped).map(([sport, list]) => (
        <div key={sport} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: 1.2, color: "var(--app-muted)" }}>{sport}</span>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(clamp(88px, 24vw, 120px), 1fr))", gap: "clamp(8px, 2.5vw, 14px)" }}>
            {list.map((c) => <Tile key={c.id} char={c} onClick={() => setOpenId(c.id)} />)}
          </div>
        </div>
      ))}

      {open && <CharacterDialog char={open} onSaved={replace} onClose={() => setOpenId(null)} />}
      {adding && (
        <AddDialog
          onCreated={(made) => { setChars((cs) => [...cs, made]); setAdding(false); setOpenId(made.id); }}
          onClose={() => setAdding(false)}
        />
      )}
    </div>
  );
}
