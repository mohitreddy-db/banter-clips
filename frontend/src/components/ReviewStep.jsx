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

export default function ReviewStep({ brief, busy, onBack, onNext, onReask }) {
  // question id -> chosen value; seeded from each question's default.
  const [answers, setAnswers] = useState({});
  const [customFor, setCustomFor] = useState({}); // question id -> free text

  useEffect(() => {
    const seeded = {};
    for (const q of brief.questions || []) if (q.default) seeded[q.id] = q.default;
    setAnswers(seeded);
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
    return out;
  };

  const questions = brief.questions || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* what we understood */}
      <div className="card" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 12 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>
          YOUR TAKE, SHARPENED
        </span>
        <div style={{ fontSize: 18, fontWeight: 600, color: "var(--app-text)", lineHeight: 1.45 }}>
          “{brief.take}”
        </div>
        {brief.original_take && brief.original_take !== brief.take && (
          <div style={{ fontSize: 13, color: "var(--app-muted2)" }}>
            you wrote: “{brief.original_take}”
          </div>
        )}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, paddingTop: 4 }}>
          {[brief.sport, brief.tone, `${brief.seconds}s`, brief.style_id].map((tag) => (
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
        {brief.cast_ids?.length > 0 && (
          <div style={{ fontSize: 13, color: "var(--app-muted)" }}>
            Casting <b style={{ color: "var(--app-text)" }}>{brief.cast_ids.join(", ")}</b>
            {brief.team_ids?.length > 0 && <> · {brief.team_ids.join(", ")} colours and venues</>}
          </div>
        )}
      </div>

      {/* the gaps */}
      {questions.length > 0 && (
        <div className="card" style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 24 }}>
          <div>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: "var(--app-muted)" }}>
              A FEW CHOICES
            </span>
            <div style={{ fontSize: 13, color: "var(--app-muted2)", paddingTop: 6 }}>
              Defaults are already selected — change anything you care about, or just hit Next.
            </div>
          </div>

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

          {onReask && (
            <button
              type="button"
              onClick={() => onReask(resolved())}
              disabled={busy}
              style={{
                alignSelf: "flex-start", background: "none", border: "none",
                color: "var(--app-cyan)", fontSize: 13, fontWeight: 600, cursor: "pointer", padding: 0,
              }}
            >
              ↻ Re-check with these answers
            </button>
          )}
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
          {busy ? "Starting…" : "Next → Generate"}
        </button>
      </div>
    </div>
  );
}
