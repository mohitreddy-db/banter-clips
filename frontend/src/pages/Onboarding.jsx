import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useApp } from "../state/AppContext.jsx";
import { api } from "../lib/api.js";
import { SPORTS, suggestionsFor } from "../lib/sports.js";

import { useSeo } from "../lib/seo.js";
// One vocabulary with the create page and the backend (lib/sports.js).
// Nothing is locked any more: every sport here generates.
const ROLES = [
  ["Sports Fan", "🙌"], ["Creator", "🎬"], ["Podcaster", "🎙"], ["Media Company", "📺"], ["Fantasy Creator", "📊"],
];
const PLATFORMS = [
  { name: "Instagram", key: "instagram", sub: "Publishes as Reels · beta launch platform", connectable: true, tile: "linear-gradient(140deg,#7b2ff7,#f0546c)", glyph: "ig" },
  { name: "TikTok", key: "tiktok", sub: "Direct post · beta", connectable: true, tile: "linear-gradient(140deg,#25f4ee,#0b0b0f 55%,#fe2c55)", glyph: "note" },
  { name: "YouTube", key: "youtube", sub: "Upload directly as Shorts · beta", connectable: true, tile: "#1a1114", glyph: "yt" },
  { name: "X", key: "x", sub: "Video post with caption", connectable: false, tile: "#0f1524", glyph: "x" },
];

const FREE_FEATURES = ["Welcome credits — your first video on us", "One-click publish to Instagram, TikTok & YouTube", "All five tones, Funny to Roast", "Watermark on every clip"];
const CREATOR_FEATURES = ["150 credits every month", "Full HD 1080p quality", "30-second videos", "500-character prompts", "Download in HD — no watermark", "Publish without the watermark", "Priority render queue"];

function Glyph({ kind }) {
  const common = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none" };
  if (kind === "ig")
    return (
      <svg {...common} stroke="#fff" strokeWidth="1.8">
        <rect x="4" y="4" width="16" height="16" rx="5" />
        <circle cx="12" cy="12" r="3.6" />
        <circle cx="16.8" cy="7.2" r="0.9" fill="#fff" />
      </svg>
    );
  if (kind === "note")
    return (
      <svg {...common} stroke="#fff" strokeWidth="2" strokeLinecap="round">
        <path d="M14 4v9.5a3.5 3.5 0 1 1-3.5-3.5" />
        <path d="M14 4c.5 2.5 2 4 4.5 4.4" />
      </svg>
    );
  if (kind === "yt")
    return (
      <svg {...common}>
        <rect x="3" y="6" width="18" height="12" rx="3" fill="#e0281e" />
        <path d="M10 9.5L15 12l-5 2.5z" fill="#fff" />
      </svg>
    );
  return (
    <svg {...common} stroke="#fff" strokeWidth="2.4" strokeLinecap="round">
      <path d="M5 5l14 14M19 5L5 19" />
    </svg>
  );
}

const TOTAL = 5;

export default function Onboarding() {
  useSeo({
    title: "Get started — BanterClips",
    description: "Set up your BanterClips account and make your first sports video.",
    path: "/onboarding",
    noindex: true,
  });

  const { booted, signedIn } = useApp();
  // Selections initialize from the saved profile, so don't mount the flow
  // until the session (and profile) have loaded — critical when returning
  // from the Instagram OAuth redirect.
  if (!booted) {
    return (
      <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "grid", placeItems: "center" }}>
        <span style={{ width: 30, height: 30, borderRadius: "50%", border: "3px solid #12303d", borderTopColor: "#22d3ee", animation: "spin 1s linear infinite" }} />
      </div>
    );
  }
  if (!signedIn) return <Navigate to="/signin" replace />;
  return <OnboardingFlow />;
}

function OnboardingFlow() {
  const nav = useNavigate();
  const { profile, savePreferences, instagram, tiktok, youtube, connectSocial, plan, upgrade, startCheckout } = useApp();
  const accounts = { instagram, tiktok, youtube };
  // Returning from the Instagram OAuth redirect (?ig=connected|denied|error):
  // resume at the connect step instead of restarting the flow.
  const [searchParams] = useSearchParams();
  const igReturn = searchParams.get("ig");
  const ttReturn = searchParams.get("tt");
  const ytReturn = searchParams.get("yt");
  const oauthReturn = igReturn || ttReturn || ytReturn;
  const [step, setStep] = useState(oauthReturn ? 4 : 1);
  const [igNotice] = useState(
    oauthReturn && oauthReturn !== "connected"
      ? `${igReturn ? "Instagram" : ttReturn ? "TikTok" : "YouTube"} connect ${oauthReturn === "denied" ? "was cancelled" : "failed"} — you can try again or skip.`
      : ""
  );
  const [sports, setSports] = useState(profile.sports || []);
  const [teams, setTeams] = useState(profile.teams?.length ? profile.teams : []);
  const [players, setPlayers] = useState(profile.players?.length ? profile.players : []);
  const [teamInput, setTeamInput] = useState("");
  const [playerInput, setPlayerInput] = useState("");
  const [role, setRole] = useState(profile.role || "");
  const [connecting, setConnecting] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [finishing, setFinishing] = useState(false);

  const finish = async (pickedCreator = false) => {
    setFinishing(true);
    try {
      // Save first — a Stripe redirect must not lose onboarding completion.
      await savePreferences({
        sports,
        teams,
        players,
        role: role || null,
        onboarding_completed: true,
      });
      if (pickedCreator && plan !== "creator") {
        setUpgrading(true);
        const url = await startCheckout();
        if (url) {
          window.location.href = url; // Stripe Checkout; returns to /account
          return;
        }
        await upgrade(); // dev fallback
        setUpgrading(false);
      }
    } catch {
      /* onboarding must never block creation — go to the studio regardless */
    }
    nav("/studio");
  };

  // Persist each step as it's completed, so selections survive the full-page
  // Instagram OAuth redirect (and refreshes). onboarding_completed only at the end.
  const saveStep = () => {
    const partial =
      step === 1 ? { sports } : step === 2 ? { teams, players } : step === 3 ? { role: role || null } : null;
    if (partial) savePreferences(partial).catch(() => {});
  };

  const next = () => {
    if (step === TOTAL) return finish(false);
    saveStep();
    setStep(step + 1);
  };
  const back = () => setStep(Math.max(1, step - 1));
  const skipStep = () => {
    api.track("onboarding_step_skipped", { step });
    next();
  };

  const toggleSport = (s) =>
    setSports((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const addTag = (val, list, setList, setInput) => {
    const v = val.trim();
    if (v && !list.includes(v)) setList([...list, v]);
    setInput("");
  };

  const doConnect = async (platform) => {
    setConnecting(platform);
    try {
      await connectSocial(platform);
    } catch {
      /* surfaced by the button returning to Connect state */
    }
    setConnecting(false);
  };

  const optional = step === 4 || step === 5;
  const stepLabel = `STEP ${step} OF ${TOTAL}${optional ? " · OPTIONAL" : ""}`;
  const titles = {
    1: "What sports are you into?",
    2: "Favorite teams & players",
    3: "How will you use BanterClips?",
    4: "Connect your accounts",
    5: "Pick your plan",
  };
  const subs = {
    1: "Pick as many as you like — we'll pre-select your Studio and tailor example takes.",
    2: "Optional — helps us suggest take ideas you'll actually want to post.",
    3: "",
    4: "Publish everywhere in one click. You can always do this later.",
    5: "Start free and publish today — or unlock downloads from day one. Change anytime.",
  };

  return (
    <div className="app-font" style={{ minHeight: "100vh", background: "var(--app-bg)", display: "grid", placeItems: "center", padding: "clamp(14px, 4vw, 24px)" }}>
      <div style={{ width: "100%", maxWidth: 680, display: "flex", flexDirection: "column", gap: 18 }}>
        {/* progress */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1.4, color: "var(--app-muted)" }}>{stepLabel}</div>
          <div style={{ flex: 1, height: 4, borderRadius: 99, background: "var(--app-panel)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${(step / TOTAL) * 100}%`, background: "var(--app-grad)", transition: "width .25s" }} />
          </div>
        </div>
        <h1 style={{ fontWeight: 800, fontSize: "clamp(24px, 6vw, 32px)", color: "var(--app-text)", margin: 0 }}>{titles[step]}</h1>
        {subs[step] && <div style={{ fontSize: 15, color: "var(--app-muted)", marginTop: -6 }}>{subs[step]}</div>}

        {step === 1 && (
          <div className="ob-sports" style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
            {SPORTS.map(({ key: s, icon }) => {
              const on = sports.includes(s);
              return (
                <button
                  key={s}
                  onClick={() => toggleSport(s)}
                  style={{
                    display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
                    padding: "18px 8px 16px", borderRadius: 14, cursor: "pointer",
                    background: on ? "#12303d" : "var(--app-surface)",
                    border: `1.5px solid ${on ? "var(--app-cyan)" : "var(--app-border)"}`,
                    color: "var(--app-text)",
                    fontWeight: 600, fontSize: 13, transition: "all .15s",
                  }}
                >
                  <span style={{ fontSize: 26 }}>{icon}</span>
                  {s}
                </button>
              );
            })}
          </div>
        )}

        {step === 2 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
            <TagField label="FAVORITE TEAMS" placeholder="Search teams — Lakers, Chiefs, Real Madrid…" input={teamInput} setInput={setTeamInput} tags={teams} onAdd={() => addTag(teamInput, teams, setTeams, setTeamInput)} onRemove={(t) => setTeams(teams.filter((x) => x !== t))}
              suggestions={suggestionsFor(sports, "teams", 10).filter((t) => !teams.includes(t))}
              onPick={(t) => setTeams([...teams, t])} />
            <TagField label="FAVORITE PLAYERS" placeholder="Search players — LeBron, Mahomes, Messi…" input={playerInput} setInput={setPlayerInput} tags={players} onAdd={() => addTag(playerInput, players, setPlayers, setPlayerInput)} onRemove={(t) => setPlayers(players.filter((x) => x !== t))}
              suggestions={suggestionsFor(sports, "players", 10).filter((p) => !players.includes(p))}
              onPick={(p) => setPlayers([...players, p])} />
          </div>
        )}

        {step === 3 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {ROLES.map(([r, emoji]) => {
              const on = role === r;
              return (
                <button
                  key={r}
                  onClick={() => setRole(r)}
                  style={{
                    display: "flex", alignItems: "center", gap: 14, padding: "15px 18px",
                    borderRadius: 14, cursor: "pointer", textAlign: "left",
                    background: on ? "#12303d" : "var(--app-surface)",
                    border: `1.5px solid ${on ? "var(--app-cyan)" : "var(--app-border)"}`,
                    color: "var(--app-text)", fontWeight: 600, fontSize: 15, transition: "all .15s",
                  }}
                >
                  <span style={{ fontSize: 20 }}>{emoji}</span>
                  {r}
                </button>
              );
            })}
          </div>
        )}

        {step === 4 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {igNotice && (
              <div style={{ fontSize: 13, color: "var(--app-error)", background: "rgba(240,84,108,.1)", borderRadius: 10, padding: "10px 14px" }}>
                {igNotice}
              </div>
            )}
            {PLATFORMS.map((p) => (
              <div key={p.name} className="card" style={{ display: "flex", alignItems: "center", gap: 14, padding: "13px 16px", borderRadius: 14 }}>
                <div style={{ width: 38, height: 38, borderRadius: 10, background: p.tile, display: "grid", placeItems: "center", border: p.glyph === "note" || p.glyph === "x" ? "1px solid var(--app-border)" : "none" }}>
                  <Glyph kind={p.glyph} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 15, color: "var(--app-text)" }}>{p.name}</div>
                  <div style={{ fontSize: 12, color: "var(--app-muted)" }}>{p.sub}</div>
                </div>
                {p.connectable ? (
                  accounts[p.key] ? (
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--app-green)" }}>● Connected</span>
                  ) : (
                    <button className="grad-btn" style={{ padding: "9px 20px", fontSize: 14, borderRadius: 10, opacity: connecting ? 0.7 : 1 }} disabled={!!connecting} onClick={() => doConnect(p.key)}>
                      {connecting === p.key ? "Connecting…" : "Connect"}
                    </button>
                  )
                ) : (
                  <span className="panel" style={{ padding: "6px 12px", borderRadius: 999, fontSize: 11, color: "var(--app-muted)", background: "#161e30" }}>Coming soon</span>
                )}
              </div>
            ))}
          </div>
        )}

        {step === 5 && (
          <div className="ob-plans" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <PlanTile
              name="Free"
              price="$0"
              features={FREE_FEATURES}
              cta={plan === "creator" ? "Included in Creator" : "Start free"}
              onPick={() => finish(false)}
              busy={finishing && !upgrading}
            />
            <PlanTile
              name="Creator"
              price="$19"
              features={CREATOR_FEATURES}
              popular
              cta={plan === "creator" ? "✓ Your plan" : upgrading ? "Upgrading…" : "Go Creator"}
              onPick={() => finish(true)}
              busy={upgrading}
            />
          </div>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: "clamp(8px, 2.5vw, 16px)", paddingTop: 14 }}>
          {step > 1 ? (
            <button className="ghost-btn" style={{ padding: "12px clamp(12px, 3vw, 20px)", fontSize: 14 }} onClick={back}>← Back</button>
          ) : (
            <span />
          )}
          <div style={{ flex: 1 }} />
          <button onClick={skipStep} style={{ background: "none", border: "none", color: "var(--app-muted)", fontWeight: 600, fontSize: 13, cursor: "pointer" }}>
            {step === TOTAL ? "Skip — stay on Free" : "Skip for now"}
          </button>
          {step < TOTAL && (
            <button className="grad-btn" style={{ padding: "12px 24px", fontSize: 14 }} onClick={next}>
              Continue →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function PlanTile({ name, price, features, popular, cta, onPick, busy }) {
  return (
    <div className="card" style={{ padding: 24, position: "relative", border: popular ? "1.5px solid var(--app-cyan)" : undefined, display: "flex", flexDirection: "column", gap: 12 }}>
      {popular && (
        <span style={{ position: "absolute", top: -11, left: 20, background: "var(--app-grad)", color: "#06121a", fontSize: 10, fontWeight: 800, padding: "3px 11px", borderRadius: 999, letterSpacing: ".05em" }}>
          MOST POPULAR
        </span>
      )}
      <div style={{ fontWeight: 700, fontSize: 18, color: "var(--app-text)" }}>{name}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
        <span style={{ fontWeight: 800, fontSize: 30, color: "var(--app-text)" }}>{price}</span>
        <span style={{ fontSize: 13, color: "var(--app-muted)" }}>/mo</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
        {features.map((f) => (
          <div key={f} style={{ display: "flex", gap: 9, fontSize: 13, fontWeight: 500, color: "var(--app-text)" }}>
            <span style={{ color: "var(--app-green)", fontWeight: 700 }}>✓</span> {f}
          </div>
        ))}
      </div>
      <button className={popular ? "grad-btn" : "ghost-btn"} style={{ padding: 12, fontSize: 14, opacity: busy ? 0.7 : 1, color: popular ? undefined : "var(--app-text)" }} disabled={busy} onClick={onPick}>
        {busy ? "One sec…" : cta}
      </button>
    </div>
  );
}

/**
 * `suggestions` are drawn from the sports the user just picked, so this step
 * opens with something to tap instead of an empty search box — a blank field
 * is the question people skip. Typing still works for anything not listed.
 */
function TagField({ label, placeholder, input, setInput, tags, onAdd, onRemove, suggestions = [], onPick }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <label style={{ fontSize: 12, fontWeight: 600, letterSpacing: 1, color: "var(--app-muted)" }}>{label}</label>
      <div className="panel" style={{ display: "flex", alignItems: "center", gap: 10, padding: "13px 14px" }}>
        <span style={{ opacity: 0.6 }}>🔎</span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onAdd()}
          placeholder={placeholder}
          style={{ flex: 1, minWidth: 0, background: "none", border: "none", color: "var(--app-text)", fontSize: 16 }}
        />
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {tags.map((t) => (
          <span key={t} onClick={() => onRemove(t)} style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 999, background: "#12303d", border: "1px solid rgba(34,211,238,.5)", color: "var(--app-text)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
            {t} <span style={{ color: "var(--app-muted)" }}>×</span>
          </span>
        ))}
      </div>
      {suggestions.length > 0 && (
        <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onPick?.(s)}
              style={{ padding: "6px 12px", borderRadius: 999, background: "transparent", border: "1px dashed var(--app-border)", color: "var(--app-muted)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
            >
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
