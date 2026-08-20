import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api, API_BASE, getToken } from "../lib/api.js";

/**
 * Admin · character catalog.
 *
 * The merged view of both catalog layers — curated JSON (ships in git) and
 * DB rows (runtime discoveries + admin edits, which override curated ids).
 * Every save writes the DB layer, so edits take effect on the next
 * generation without a deploy.
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

function Field({ label, value, onChange, rows = 0 }) {
  const common = {
    width: "100%", boxSizing: "border-box", padding: "9px 11px", fontSize: 13,
    color: "var(--app-text)", background: "var(--app-panel)",
    border: "1px solid var(--app-border)", borderRadius: 9,
  };
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
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

function CharacterCard({ char, onSaved }) {
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
    <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, opacity: char.active ? 1 : 0.55 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 700, fontSize: 15.5, color: "var(--app-text)" }}>{char.name}</span>
        <code style={{ fontSize: 11, color: "var(--app-muted2)" }}>{char.id}</code>
        <span style={badgeStyle(char.source)}>{char.source}</span>
        {!char.active && <span style={{ fontSize: 11, color: "var(--app-error)", fontWeight: 700 }}>INACTIVE</span>}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        {char.reference_urls.length ? (
          char.reference_urls.map((u, i) => (
            <img key={i} src={imgUrl(u)} alt="" loading="lazy"
                 style={{ width: 72, height: 128, objectFit: "cover", borderRadius: 8, border: "1px solid var(--app-border)" }} />
          ))
        ) : (
          <div style={{ width: 72, height: 128, borderRadius: 8, border: "1px dashed var(--app-border)", display: "grid", placeItems: "center", fontSize: 10.5, color: "var(--app-muted2)", textAlign: "center", padding: 4 }}>
            no reference stills
          </div>
        )}
      </div>

      <Field label="NAME" value={form.name} onChange={set("name")} />
      <Field label="LOOK" value={form.look} onChange={set("look")} rows={3} />
      <Field label="WARDROBE" value={form.default_wardrobe} onChange={set("default_wardrobe")} rows={2} />
      <Field label="VOICE" value={form.voice_style} onChange={set("voice_style")} />
      <Field label="ALIASES (comma-separated)" value={form.aliases} onChange={set("aliases")} />

      {error && <div style={{ fontSize: 12.5, color: "var(--app-error)" }}>{error}</div>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className="grad-btn" style={{ padding: "9px 16px", fontSize: 13, opacity: dirty ? 1 : 0.5 }} disabled={!dirty || !!busy} onClick={save}>
          {busy === "save" ? "Saving…" : "Save"}
        </button>
        <button className="ghost-btn" style={{ padding: "9px 14px", fontSize: 13 }} disabled={!!busy} onClick={regen}>
          {busy === "regen" ? "Generating…" : "↻ Regenerate stills ($0.10)"}
        </button>
        <button className="ghost-btn" style={{ padding: "9px 14px", fontSize: 13, marginLeft: "auto", color: char.active ? "var(--app-error)" : "var(--app-green)" }} disabled={!!busy} onClick={toggle}>
          {busy === "toggle" ? "…" : char.active ? "Deactivate" : "Activate"}
        </button>
      </div>
    </div>
  );
}

export default function AdminCatalog() {
  const { user, booted } = useApp();
  const [chars, setChars] = useState(null);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ name: "", sport: "Soccer", look: "", default_wardrobe: "", voice_style: "" });

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

  const replace = (updated) =>
    setChars((cs) => cs.map((c) => (c.id === updated.id ? updated : c)));

  const create = async () => {
    try {
      setError("");
      const made = await api.adminCreateCharacter(draft);
      setChars((cs) => [...cs, made]);
      setAdding(false);
      setDraft({ name: "", sport: "Soccer", look: "", default_wardrobe: "", voice_style: "" });
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h2 style={{ fontSize: 24, fontWeight: 800, color: "var(--app-text)", margin: 0 }}>Character catalog</h2>
        <span style={{ fontSize: 12.5, color: "var(--app-muted)" }}>
          {chars ? `${chars.length} characters · edits apply to the next generation` : "loading…"}
        </span>
        <button className="grad-btn" style={{ marginLeft: "auto", padding: "9px 16px", fontSize: 13 }} onClick={() => setAdding((a) => !a)}>
          {adding ? "Cancel" : "+ Add character"}
        </button>
      </div>

      {adding && (
        <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10 }}>
            <Field label="NAME" value={draft.name} onChange={(v) => setDraft((d) => ({ ...d, name: v }))} />
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.8, color: "var(--app-muted2)" }}>SPORT</span>
              <select value={draft.sport} onChange={(e) => setDraft((d) => ({ ...d, sport: e.target.value }))}
                      style={{ padding: "9px 11px", fontSize: 13, color: "var(--app-text)", background: "var(--app-panel)", border: "1px solid var(--app-border)", borderRadius: 9 }}>
                {SPORTS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </label>
          </div>
          <Field label="LOOK (physical appearance)" value={draft.look} onChange={(v) => setDraft((d) => ({ ...d, look: v }))} rows={2} />
          <Field label="WARDROBE (kit, colours, number)" value={draft.default_wardrobe} onChange={(v) => setDraft((d) => ({ ...d, default_wardrobe: v }))} rows={2} />
          <Field label="VOICE STYLE" value={draft.voice_style} onChange={(v) => setDraft((d) => ({ ...d, voice_style: v }))} />
          <button className="grad-btn" style={{ padding: "10px 18px", fontSize: 13.5, alignSelf: "flex-start" }} disabled={draft.name.trim().length < 2} onClick={create}>
            Create
          </button>
        </div>
      )}

      {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}

      {Object.entries(grouped).map(([sport, list]) => (
        <div key={sport} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <span style={{ fontSize: 12, fontWeight: 800, letterSpacing: 1.2, color: "var(--app-muted)" }}>{sport}</span>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(320px,1fr))", gap: 14 }}>
            {list.map((c) => <CharacterCard key={c.id} char={c} onSaved={replace} />)}
          </div>
        </div>
      ))}
    </div>
  );
}
