import { useEffect, useState } from "react";

/**
 * The step between typing a take and spending money on it.
 *
 * Shows what the enhancer made of the take, then asks only about the gaps it
 * found — each as selectable options plus a free-text "Something else" escape
 * hatch. Every question carries a default, so Next is always available and a
 * user who ignores all of it still gets a sensible video.
 */

const CUSTOM = "__custom__";

function Chip({ selected, onClick, children, title }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        padding: "10px 14px",
        borderRadius: 12,
        cursor: "pointer",
        textAlign: "left",
        fontSize: 13.5,
        fontWeight: selected ? 700 : 500,
        color: selected ? "var(--app-text)" : "var(--app-muted)",
        background: selected ? "rgba(34,211,238,.12)" : "transparent",
        border: `1px solid ${selected ? "var(--app-cyan)" : "var(--app-border)"}`,
      }}
    >
      {children}
    </button>
  );
}

function TakeCard({ selected, onClick, label, text, badge }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex", flexDirection: "column", gap: 7, width: "100%",
        padding: "14px 16px", borderRadius: 14, cursor: "pointer", textAlign: "left",
        background: selected ? "rgba(34,211,238,.10)" : "transparent",
        border: `1px solid ${selected ? "var(--app-cyan)" : "var(--app-border)"}`,
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            width: 15, height: 15, borderRadius: "50%", flexShrink: 0,
            border: `2px solid ${selected ? "var(--app-cyan)" : "var(--app-border)"}`,
            background: selected
              ? "radial-gradient(circle, var(--app-cyan) 0 42%, transparent 43%)"
              : "transparent",
          }}
        />
        <span style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: 0.8, color: selected ? "var(--app-cyan)" : "var(--app-muted)" }}>
          {label}
        </span>
        {badge && (
          <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.6, color: "var(--app-muted2)", border: "1px solid var(--app-border)", borderRadius: 999, padding: "2px 7px" }}>
            {badge}
          </span>
        )}
      </span>
      <span style={{ fontSize: 15.5, fontWeight: selected ? 600 : 500, color: selected ? "var(--app-text)" : "var(--app-muted)", lineHeight: 1.45 }}>
        “{text}”
      </span>
    </button>
  );
}

export default function ReviewStep({ brief, busy, onBack, onNext }) {
  // question id -> chosen value; seeded from each question's default.
  const [answers, setAnswers] = useState({});
  const [customFor, setCustomFor] = useState({}); // question id -> free text
  // Their words win by default. Sharpening is an offer, not a correction.
  const [useOriginal, setUseOriginal] = useState(true);

  const hasSuggestion =
    Boolean(brief.original_take) && brief.original_take.trim() !== brief.take.trim();

  useEffect(() => {
    const seeded = {};
    for (const q of brief.questions || []) if (q.default) seeded[q.id] = q.default;
    setAnswers(seeded);
    setUseOriginal(true);
  }, [brief]);

  const pick = (qid, value) => {
    setAnswers((a) => ({ ...a, [qid]: value }));
    if (value !== CUSTOM) setCustomFor((c) => ({ ...c, [qid]: undefined }));
  };

  const resolved = () => {
    const out = {};
    for (const [qid, value] of Object.entries(answers)) {
      const text = value === CUSTOM ? (customFor[qid] || "").trim() : value;
      if (text) out[qid] = text;
    }
    // Take precedence, most explicit first: something the user actually typed
    // into the "say more" box, then their card choice, then the suggestion.
    // The box is seeded with the suggestion, so only a real edit counts.
    const typed = (out.take || "").trim();
    if (typed && typed !== brief.take.trim()) out.take = typed;
    else out.take = hasSuggestion && useOriginal ? brief.original_take : brief.take;
    return out;
  };

  const questions = brief.questions || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* The take. When we have a sharpened version it is OFFERED, never
          imposed — the user's own words stay selected unless they switch. */}
      <div className="card" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
        {hasSuggestion ? (
          <>
            <div style={{ fontSize: 13.5, color: "var(--app-muted)" }}>Which wording should we run with?</div>
            <div style={{ display: "grid", gap: 10 }}>
              <TakeCard
                selected={useOriginal}
                onClick={() => setUseOriginal(true)}
                label="Your take"
                text={brief.original_take}
              />
              <TakeCard
                selected={!useOriginal}
                onClick={() => setUseOriginal(false)}
                label="✨ Sharpened"
                badge="suggested"
                text={brief.take}
              />
            </div>
          </>
        ) : (
          <div style={{ fontSize: 19, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.45 }}>
            “{brief.take}”
          </div>
        )}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, paddingTop: 2 }}>
          {[brief.sport, brief.tone, `${brief.seconds}s`, brief.style_label || brief.style_id]
            .filter(Boolean)
            .map((tag) => (
              <span
                key={tag}
                style={{
                  padding: "5px 11px", borderRadius: 999, fontSize: 12, fontWeight: 600,
                  color: "var(--app-muted)", border: "1px solid var(--app-border)",
                }}
              >
                {tag}
              </span>
            ))}
        </div>
        {(brief.cast_names?.length > 0 || brief.team_names?.length > 0) && (
          <div style={{ fontSize: 13.5, color: "var(--app-muted)" }}>
            Starring{" "}
            <b style={{ color: "var(--app-text)" }}>
              {(brief.cast_names?.length ? brief.cast_names : brief.team_names).join(" and ")}
            </b>
          </div>
        )}
      </div>

      {/* the gaps */}
      {questions.length > 0 && (
        <div className="card" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 26 }}>
          {questions.map((q) => {
            const chosen = answers[q.id];
            return (
              <div key={q.id} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: "var(--app-text)" }}>{q.prompt}</div>
                <div style={{ fontSize: 12.5, color: "var(--app-muted2)", marginTop: -4 }}>{q.why}</div>

                {q.kind === "text" ? (
                  <textarea
                    value={chosen ?? ""}
                    onChange={(e) => pick(q.id, e.target.value)}
                    rows={2}
                    placeholder="Type your answer…"
                    style={{
                      width: "100%", padding: 12, borderRadius: 12, resize: "vertical",
                      background: "var(--app-bg2)", color: "var(--app-text)",
                      border: "1px solid var(--app-border)", fontSize: 14, fontFamily: "inherit",
                    }}
                  />
                ) : (
                  <>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 9 }}>
                      {q.options.map((o) => (
                        <Chip key={o.value} selected={chosen === o.value} onClick={() => pick(q.id, o.value)} title={o.detail}>
                          <div>{o.label}</div>
                          {o.detail && (
                            <div style={{ fontSize: 11.5, fontWeight: 400, color: "var(--app-muted2)", paddingTop: 3 }}>
                              {o.detail}
                            </div>
                          )}
                        </Chip>
                      ))}
                      <Chip selected={chosen === CUSTOM} onClick={() => pick(q.id, CUSTOM)}>
                        <div>✏️ Something else</div>
                        <div style={{ fontSize: 11.5, fontWeight: 400, color: "var(--app-muted2)", paddingTop: 3 }}>
                          Describe it yourself
                        </div>
                      </Chip>
                    </div>
                    {chosen === CUSTOM && (
                      <input
                        autoFocus
                        value={customFor[q.id] || ""}
                        onChange={(e) => setCustomFor((c) => ({ ...c, [q.id]: e.target.value }))}
                        placeholder="Type what you want instead…"
                        style={{
                          width: "100%", padding: 12, borderRadius: 12,
                          background: "var(--app-bg2)", color: "var(--app-text)",
                          border: "1px solid var(--app-cyan)", fontSize: 14,
                        }}
                      />
                    )}
                  </>
                )}
              </div>
            );
          })}

        </div>
      )}

      <div style={{ display: "flex", gap: 12 }}>
        <button
          type="button"
          onClick={onBack}
          disabled={busy}
          style={{
            padding: "16px 22px", borderRadius: 16, fontSize: 15, fontWeight: 600, cursor: "pointer",
            background: "transparent", color: "var(--app-muted)", border: "1px solid var(--app-border)",
          }}
        >
          ← Edit take
        </button>
        <button
          className="grad-btn"
          style={{ flex: 1, padding: 18, fontSize: 17, borderRadius: 16 }}
          disabled={busy}
          onClick={() => onNext(resolved())}
        >
          {busy ? "Starting…" : "🪄 Make it"}
        </button>
      </div>
    </div>
  );
}
