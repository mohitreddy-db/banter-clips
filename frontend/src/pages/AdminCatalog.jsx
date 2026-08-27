import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api, API_BASE, getToken } from "../lib/api.js";

import { useSeo } from "../lib/seo.js";
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

/** Full-detail dialog: big centred dialog on desktop, full page on phones
    (see .admin-dialog in index.css). */
function Dialog({ children, onClose }) {
  return (
    <div
      onClick={onClose}
      className="admin-dialog-overlay"
      style={{
        position: "fixed", inset: 0, zIndex: 120, background: "rgba(4,6,12,.74)",
        backdropFilter: "blur(6px)", display: "grid", placeItems: "center",
        padding: "clamp(12px, 3vw, 28px)", animation: "fadeUp .18s ease both",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card app-font admin-dialog"
        style={{ padding: "clamp(16px, 4vw, 28px)", borderRadius: "clamp(14px, 3vw, 20px)" }}
      >
        {children}
      </div>
    </div>
  );
}

/** One selectable still in the history grid. */
function StillTile({ still, selected, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      title={still.notes || undefined}
      style={{
        position: "relative", padding: 0, background: "none", cursor: "pointer",
        border: `2px solid ${selected ? "var(--app-cyan)" : "var(--app-border)"}`,
        borderRadius: 10, overflow: "hidden", aspectRatio: "9/16",
      }}
    >
      <img src={imgUrl(still.url)} alt="" loading="lazy"
           style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
      <span style={{ position: "absolute", top: 5, left: 5, fontSize: 8.5, fontWeight: 800, padding: "2px 6px", borderRadius: 999, background: "rgba(4,6,12,.7)", color: "var(--app-muted)" }}>
        {still.kind.toUpperCase()}
      </span>
      {selected && (
        <span style={{ position: "absolute", top: 5, right: 5, width: 18, height: 18, borderRadius: "50%", background: "var(--app-cyan)", color: "#04121a", display: "grid", placeItems: "center", fontSize: 11, fontWeight: 900 }}>
          ✓
        </span>
      )}
    </button>
  );
}

function CharacterDialog({ char, onSaved, onClose }) {
  const [form, setForm] = useState({
    name: char.name, look: char.look, default_wardrobe: char.default_wardrobe,
    voice_style: char.voice_style, aliases: char.aliases.join(", "),
  });
  const [stills, setStills] = useState(null);
  const [selection, setSelection] = useState(new Set());
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const dirty =
    form.name !== char.name || form.look !== char.look ||
    form.default_wardrobe !== char.default_wardrobe ||
    form.voice_style !== char.voice_style ||
    form.aliases !== char.aliases.join(", ");

  useEffect(() => {
    api.adminStills(char.id)
      .then((rows) => {
        setStills(rows);
        setSelection(new Set(rows.filter((s) => s.active).map((s) => s.id)));
      })
      .catch(() => setStills([]));
  }, [char.id]);

  const activeIds = new Set((stills || []).filter((s) => s.active).map((s) => s.id));
  const selectionChanged =
    stills && (selection.size !== activeIds.size || [...selection].some((id) => !activeIds.has(id)));

  const run = async (kind, fn) => {
    setBusy(kind);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const save = () => run("save", async () => onSaved(await api.adminUpdateCharacter(char.id, {
    name: form.name, look: form.look, default_wardrobe: form.default_wardrobe,
    voice_style: form.voice_style,
    aliases: form.aliases.split(",").map((a) => a.trim()).filter(Boolean),
  })));
  const toggle = () => run("toggle", async () =>
    onSaved(await api.adminUpdateCharacter(char.id, { active: !char.active })));

  const generate = () => {
    if (!window.confirm(`Generate 4 new stills for ${char.name} (face, full body, jersey detail, footwear detail)? Costs ~$0.20 of image credit. They appear below as candidates — approve to use them.`)) return;
    run("regen", async () => {
      const fresh = await api.adminGenerateStills(char.id, notes.trim());
      setStills((s) => [...fresh, ...(s || [])]);
      setNotes("");
    });
  };

  const approve = () => run("approve", async () => {
    const updated = await api.adminApproveStills(char.id, [...selection]);
    onSaved(updated);
    setStills((rows) => rows.map((r) => ({ ...r, active: selection.has(r.id) })));
  });

  const research = () => run("research", async () => {
    const r = await api.adminResearch(char.id);
    if (!r.found) {
      setError("Research couldn't identify this person — fill the fields manually.");
      return;
    }
    setForm((f) => ({
      ...f,
      look: r.look || f.look,
      default_wardrobe: r.default_wardrobe || f.default_wardrobe,
      voice_style: r.voice_style || f.voice_style,
    }));
  });

  const toggleStill = (id) =>
    setSelection((sel) => {
      const next = new Set(sel);
      if (next.has(id)) next.delete(id);
      else if (next.size < 4) next.add(id);
      return next;
    });

  return (
    <Dialog onClose={() => !busy && onClose()}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 800, fontSize: "clamp(17px, 4.5vw, 20px)", color: "var(--app-text)" }}>{char.name}</span>
          <span style={badgeStyle(char.source)}>{char.source}</span>
          {!char.active && <span style={{ fontSize: 11, color: "var(--app-error)", fontWeight: 700 }}>INACTIVE</span>}
          <button onClick={onClose} aria-label="Close"
                  style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--app-muted)", fontSize: 24, cursor: "pointer", lineHeight: 1, padding: "2px 8px" }}>
            ×
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: -12 }}>
          <code style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>{char.id}</code>
          <span style={{ fontSize: 11.5, color: "var(--app-muted2)" }}>· {char.sport}</span>
        </div>

        <div className="admin-dialog-grid" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {/* ── left: stills, history, generation ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.8, color: "var(--app-muted2)" }}>
                STILLS — select up to 4, then approve
              </span>
              {stills === null ? (
                <div style={{ fontSize: 12.5, color: "var(--app-muted2)" }}>loading history…</div>
              ) : stills.length === 0 ? (
                <div style={{ width: 96, aspectRatio: "9/16", borderRadius: 10, overflow: "hidden", border: "1px solid var(--app-border)" }}>
                  <NoImage />
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(84px, 1fr))", gap: 8 }}>
                  {stills.map((s) => (
                    <StillTile key={s.id} still={s} selected={selection.has(s.id)} onToggle={() => toggleStill(s.id)} />
                  ))}
                </div>
              )}
              {selectionChanged && (
                <button className="grad-btn" style={{ padding: "11px 16px", fontSize: 13.5 }}
                        disabled={!!busy || selection.size === 0} onClick={approve}>
                  {busy === "approve" ? "Applying…" : `✓ Approve selection (${selection.size})`}
                </button>
              )}
            </div>

            <div className="panel" style={{ padding: "12px 14px", borderRadius: 12, display: "flex", flexDirection: "column", gap: 8 }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.8, color: "var(--app-muted2)" }}>
                GENERATE NEW STILLS
              </span>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Direction for the shoot — era, exact kit, colours, hair… e.g. “2005 Barcelona home kit, long curly hair, gold Nike Mercurial boots”"
                style={{ width: "100%", boxSizing: "border-box", padding: "9px 11px", fontSize: 13, color: "var(--app-text)", background: "var(--app-surface)", border: "1px solid var(--app-border)", borderRadius: 9, resize: "vertical" }}
              />
              <button className="ghost-btn" style={{ padding: "10px 14px", fontSize: 13 }} disabled={!!busy} onClick={generate}>
                {busy === "regen" ? "Generating…" : "📸 Generate 4 stills ($0.20)"}
              </button>
            </div>
          </div>

          {/* ── right: identity fields ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <button className="ghost-btn" style={{ padding: "10px 14px", fontSize: 13, alignSelf: "flex-start" }}
                    disabled={!!busy} onClick={research}
                    title="One web search fills look, exact kit colours/crest/number and voice from real data">
              {busy === "research" ? "Researching…" : "✨ Auto-fill real details (web research)"}
            </button>
            <Field label="NAME" value={form.name} onChange={set("name")} />
            <Field label="LOOK — physical appearance" value={form.look} onChange={set("look")} rows={3} />
            <Field label="WARDROBE — exact kit: colours, design, crest, number" value={form.default_wardrobe} onChange={set("default_wardrobe")} rows={3} />
            <Field label="VOICE STYLE" value={form.voice_style} onChange={set("voice_style")} />
            <Field label="ALIASES — comma-separated" value={form.aliases} onChange={set("aliases")} />

            {error && <div style={{ fontSize: 13, color: "var(--app-error)" }}>{error}</div>}

            <button className="grad-btn" style={{ padding: "12px 20px", fontSize: 14, opacity: dirty ? 1 : 0.5 }}
                    disabled={!dirty || !!busy} onClick={save}>
              {busy === "save" ? "Saving…" : "Save changes"}
            </button>
            <button
              className="ghost-btn"
              style={{ padding: "11px 16px", fontSize: 13.5, color: char.active ? "var(--app-error)" : "var(--app-green)" }}
              disabled={!!busy}
              onClick={toggle}
            >
              {busy === "toggle" ? "…" : char.active ? "Deactivate — hide from generation" : "Activate"}
            </button>
          </div>
        </div>
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
  useSeo({
    title: "Catalog admin — BanterClips",
    description: "Internal catalog administration.",
    path: "/admin",
    noindex: true,
  });

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
