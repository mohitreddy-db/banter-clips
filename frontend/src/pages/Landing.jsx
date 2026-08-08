import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

/* Faithful port of the client's landing page (slim MVP prototype).
   Layout, copy, colors and animations preserved; only the pricing
   preview reflects the real two-plan model (client non-negotiable #1). */

const FULL_TAKE = "Lakers won't make the playoffs.";

const logos = ["HOOPSDAILY", "THE PODCAST", "GRIDIRON+", "FOOTYWORLD", "COURTSIDE"];

const features = [
  { title: "AI Video Generator", desc: "Type an opinion, get a finished 9:16 sports video in seconds.", glyph: "▶", c1: "#7c3aed", c2: "#2563eb", span: "span 1" },
  { title: "AI Voiceovers", desc: "Expressive commentator voices tuned for hype and banter.", glyph: "◍", c1: "#0891b2", c2: "#0ea5e9", span: "span 1" },
  { title: "Animated Captions", desc: "TikTok-style word-pop captions, auto-timed to the voice.", glyph: "A", c1: "#16a34a", c2: "#65a30d", span: "span 1" },
  { title: "One-Click Publishing", desc: "Push straight to your socials the moment your clip is ready.", glyph: "↗", c1: "#db2777", c2: "#f43f5e", span: "span 1" },
  { title: "Tone Control", desc: "Funny, savage or all hype — you pick the energy, the AI matches it.", glyph: "⚡", c1: "#ea580c", c2: "#f59e0b", span: "span 2" },
];

const steps = [
  { n: "1", title: "Type your take", desc: "Drop any sports opinion, prediction or hot take.", col: "1", arrow: true, acol: "2" },
  { n: "2", title: "AI builds it", desc: "Script, voice, captions and visuals — automatic.", col: "3", arrow: true, acol: "4" },
  { n: "3", title: "Publish or download", desc: "Publish free in one click, or go Creator to download in HD.", col: "5", arrow: false },
];

const examples = [
  { sport: "NBA", cap: "🔥 LeBron IS the GOAT · Side A", c1: "#2563eb", c2: "#0ea5e9" },
  { sport: "NBA", cap: "🔥 Jordan 6-0, case closed · Side B", c1: "#dc2626", c2: "#ea580c" },
  { sport: "NBA", cap: "LeBron's still top 5, period.", c1: "#7c3aed", c2: "#db2777" },
  { sport: "NFL", cap: "Chiefs are the team of the decade.", c1: "#059669", c2: "#0891b2" },
  { sport: "Soccer", cap: "Messi ended the GOAT debate.", c1: "#16a34a", c2: "#65a30d" },
  { sport: "F1", cap: "Verstappen is unbeatable in 2026.", c1: "#dc2626", c2: "#ea580c" },
];

const testimonials = [
  { quote: "I went from 2 videos a week to 2 a day. My whole content pipeline is just BanterClips now.", name: "Marcus D.", role: "Sports YouTuber · 340K", c1: "#7c3aed", c2: "#2563eb" },
  { quote: "The commentator voices are unreal. My debate clips hit 1M views in a weekend.", name: "Tasha R.", role: "TikTok creator · 1.2M", c1: "#db2777", c2: "#f43f5e" },
  { quote: "We staff a whole social desk with this. Remixing trending takes is a cheat code.", name: "Leo P.", role: "Sports media producer", c1: "#0891b2", c2: "#0ea5e9" },
];

const plansMini = [
  { name: "Free", price: "$0", per: "/mo", tag: "5 videos · publish-only · watermarked", cta: "Start free", popular: false },
  { name: "Creator", price: "$9.99", per: "/mo", tag: "30 videos · HD download · no watermark", cta: "Go Creator", popular: true },
];

function Logo({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34">
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="oklch(0.66 0.19 253)" />
          <stop offset="1" stopColor="oklch(0.80 0.16 152)" />
        </linearGradient>
      </defs>
      <rect width="34" height="34" rx="9" fill="url(#lg)" />
      <path d="M13 10.5 L25 17 L13 23.5 Z" fill="#fff" />
    </svg>
  );
}

const WAVE_DELAYS = [0, 0.1, 0.2, 0.3, 0.15, 0.25, 0.05, 0.35];

export default function Landing() {
  const nav = useNavigate();
  const [typed, setTyped] = useState("");
  const [phase, setPhase] = useState(0);
  const timers = useRef([]);

  useEffect(() => {
    let alive = true;
    const push = (t) => timers.current.push(t);
    const cycle = () => {
      if (!alive) return;
      setPhase(0);
      setTyped("");
      let i = 0;
      const type = () => {
        if (!alive) return;
        if (i <= FULL_TAKE.length) {
          setTyped(FULL_TAKE.slice(0, i));
          i++;
          push(setTimeout(type, 58));
        } else {
          push(setTimeout(() => setPhase(1), 500));
          push(setTimeout(() => setPhase(2), 1700));
          push(setTimeout(() => setPhase(3), 3000));
          push(setTimeout(() => setPhase(4), 4300));
          push(setTimeout(cycle, 9200));
        }
      };
      push(setTimeout(type, 850));
    };
    cycle();
    return () => {
      alive = false;
      timers.current.forEach(clearTimeout);
    };
  }, []);

  const go = (r) => () => {
    if (r === "/signin") api.track("landing_cta_clicked");
    nav(r);
  };
  const op = (n) => (phase >= n ? 1 : 0.28);

  return (
    <div>
      {/* top nav */}
      <div style={{ position: "sticky", top: 0, zIndex: 40, backdropFilter: "blur(14px)", background: "oklch(0.14 0.01 260 / 0.7)", borderBottom: "1px solid var(--border)" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "16px 28px", display: "flex", alignItems: "center", gap: 32 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
            <Logo />
            <span style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 19, letterSpacing: "-.02em" }}>BanterClips</span>
          </div>
          <div className="land-nav-links" style={{ display: "flex", gap: 26, marginLeft: 8, fontSize: 14.5, color: "var(--muted)", fontWeight: 500 }}>
            <a href="#features" style={{ cursor: "pointer", color: "inherit" }}>Features</a>
            <a href="#how" style={{ cursor: "pointer", color: "inherit" }}>How it works</a>
            <a href="#examples" style={{ cursor: "pointer", color: "inherit" }}>Examples</a>
            <a href="#pricing" style={{ cursor: "pointer", color: "inherit" }}>Pricing</a>
          </div>
          <div className="land-nav-signin" style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
            <span onClick={go("/signin")} style={{ cursor: "pointer", fontSize: 14.5, fontWeight: 600, color: "var(--muted)" }}>Sign in</span>
            <button onClick={go("/signin")} style={{ background: "var(--grad)", color: "#fff", border: "none", padding: "11px 20px", borderRadius: 11, fontWeight: 700, fontSize: 14.5, cursor: "pointer" }}>
              Start Creating Free
            </button>
          </div>
        </div>
      </div>

      {/* hero */}
      <div style={{ position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(900px 500px at 15% -5%,oklch(0.66 0.19 253 / 0.16),transparent 60%),radial-gradient(760px 460px at 92% 8%,oklch(0.80 0.16 152 / 0.12),transparent 60%)", pointerEvents: "none" }} />
        <div className="hero-grid" style={{ position: "relative", maxWidth: 1200, margin: "0 auto", padding: "70px 28px 40px", display: "grid", gridTemplateColumns: "1.05fr 0.95fr", gap: 52, alignItems: "center" }}>
          <div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "var(--bg3)", border: "1px solid var(--border)", padding: "7px 14px", borderRadius: 100, fontSize: 13, fontWeight: 600, color: "var(--muted)", marginBottom: 26 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--accent2)", boxShadow: "0 0 10px var(--accent2)" }} /> AI sports video studio
            </div>
            <h1 className="hero-h1" style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 54, lineHeight: 1.03, letterSpacing: "-.03em", margin: "0 0 22px", textWrap: "balance" }}>
              Turn Any Sports Opinion Into A <span style={{ background: "var(--grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>Viral Video</span> In Seconds.
            </h1>
            <p style={{ fontSize: 18.5, lineHeight: 1.55, color: "var(--muted)", margin: "0 0 32px", maxWidth: 520 }}>
              Create AI-powered sports banter, predictions, reactions and debates — ready for TikTok, Instagram Reels and YouTube Shorts.
            </p>
            <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
              <button onClick={go("/signin")} style={{ background: "var(--grad)", color: "#fff", border: "none", padding: "16px 28px", borderRadius: 13, fontWeight: 700, fontSize: 16, cursor: "pointer", animation: "glow 3.6s ease-in-out infinite" }}>
                Start Creating Free →
              </button>
              <button onClick={go("/signin")} style={{ background: "var(--bg3)", color: "var(--text)", border: "1px solid var(--border2)", padding: "16px 24px", borderRadius: 13, fontWeight: 600, fontSize: 16, cursor: "pointer", display: "flex", alignItems: "center", gap: 9 }}>
                <span style={{ width: 22, height: 22, borderRadius: "50%", background: "var(--elev)", display: "grid", placeItems: "center" }}>
                  <span style={{ borderLeft: "7px solid var(--text)", borderTop: "4px solid transparent", borderBottom: "4px solid transparent", marginLeft: 2 }} />
                </span>
                Watch Demo
              </button>
            </div>
            <div style={{ display: "flex", gap: 26, marginTop: 36, color: "var(--muted2)", fontSize: 13, fontWeight: 600 }}>
              <span>No credit card</span><span>·</span><span>First video free</span><span>·</span><span>Export in 9:16</span>
            </div>
          </div>

          {/* interactive demo */}
          <div style={{ animation: "floaty 7s ease-in-out infinite" }}>
            <div style={{ background: "linear-gradient(180deg,var(--bg2),var(--bg))", border: "1px solid var(--border2)", borderRadius: 22, padding: 18, boxShadow: "0 40px 80px -30px #000" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "2px 4px 14px" }}>
                <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#ff5f57" }} />
                <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#febc2e" }} />
                <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#28c840" }} />
                <span style={{ marginLeft: 10, fontSize: 12, color: "var(--muted2)", fontWeight: 600 }}>BanterClips Studio</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 168px", gap: 16 }}>
                <div>
                  <div style={{ fontSize: 11, color: "var(--muted2)", fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 8 }}>Your sports take</div>
                  <div style={{ background: "var(--bg3)", border: "1px solid var(--border)", borderRadius: 12, padding: 14, fontSize: 15, fontWeight: 600, minHeight: 58, lineHeight: 1.4 }}>
                    {typed}
                    <span style={{ display: "inline-block", width: 2, height: 17, background: "var(--accent)", verticalAlign: -3, marginLeft: 1, animation: "blink 1s step-end infinite" }} />
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 16 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 11, fontSize: 13.5, fontWeight: 600, opacity: op(1), transition: "opacity .4s" }}>
                      <span style={{ width: 20, height: 20, borderRadius: 6, background: "var(--accentSoft)", color: "var(--accent)", display: "grid", placeItems: "center", fontSize: 12 }}>✓</span> Viral script written
                    </div>
                    <div style={{ opacity: op(2), transition: "opacity .4s" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 11, fontSize: 13.5, fontWeight: 600 }}>
                        <span style={{ width: 20, height: 20, borderRadius: 6, background: "var(--accentSoft)", color: "var(--accent)", display: "grid", placeItems: "center", fontSize: 12 }}>✓</span> Commentator voice
                      </div>
                      <div style={{ display: "flex", gap: 3, alignItems: "flex-end", height: 22, margin: "8px 0 0 31px" }}>
                        {WAVE_DELAYS.map((d, i) => (
                          <span key={i} style={{ width: 3, height: "100%", background: i % 2 ? "var(--accent)" : "var(--accent2)", borderRadius: 2, transformOrigin: "bottom", animation: `wave .7s ease-in-out ${d}s infinite` }} />
                        ))}
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 11, fontSize: 13.5, fontWeight: 600, opacity: op(3), transition: "opacity .4s" }}>
                      <span style={{ width: 20, height: 20, borderRadius: 6, background: "var(--accentSoft)", color: "var(--accent)", display: "grid", placeItems: "center", fontSize: 12 }}>✓</span> Animated captions
                    </div>
                  </div>
                </div>
                {/* phone preview */}
                <div style={{ position: "relative", borderRadius: 18, overflow: "hidden", aspectRatio: "9/16", background: "linear-gradient(160deg,#7c3aed,#db2777)", border: "1px solid #ffffff18" }}>
                  <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 30% 20%,#ffffff22,transparent 55%)" }} />
                  {phase < 4 ? (
                    <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center", padding: 14 }}>
                      <div style={{ opacity: 0.9 }}>
                        <div style={{ width: 44, height: 44, borderRadius: "50%", border: "2px solid #fff5", borderTopColor: "#fff", margin: "0 auto 12px", animation: "spin 1s linear infinite" }} />
                        <div style={{ fontSize: 12, fontWeight: 700, color: "#fff", opacity: 0.85 }}>Rendering…</div>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div style={{ position: "absolute", left: 12, right: 12, bottom: 64, textAlign: "center" }}>
                        <span style={{ display: "inline", background: "#000000c2", color: "#fff", fontFamily: "var(--display)", fontWeight: 700, fontSize: 20, lineHeight: 1.5, padding: "3px 6px", boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone", animation: "pop .4s ease both" }}>
                        NO WAY the Lakers <span style={{ color: "oklch(0.85 0.17 152)" }}>MISS</span> the playoffs 😤
                        </span>
                      </div>
                      <div style={{ position: "absolute", left: 12, right: 12, bottom: 44, height: 4, background: "#ffffff35", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ height: "100%", background: "#fff", animation: "prog 4.6s linear infinite" }} />
                      </div>
                      <div style={{ position: "absolute", top: 12, left: 12, background: "#00000055", backdropFilter: "blur(4px)", color: "#fff", fontSize: 10, fontWeight: 800, padding: "4px 8px", borderRadius: 6, letterSpacing: ".04em" }}>NBA · HOT TAKE</div>
                    </>
                  )}
                </div>
              </div>
              {/* demo gate */}
              <div style={{ marginTop: 14, background: "var(--bg3)", border: "1px solid var(--border)", borderRadius: 12, padding: "12px 14px", display: "flex", alignItems: "center", gap: 12, opacity: phase >= 4 ? 1 : 0, transition: "opacity .5s" }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>Your demo video is ready 🎬</div>
                  <div style={{ fontSize: 11.5, color: "var(--muted2)", marginTop: 2 }}>Sign up free to publish it in one click.</div>
                </div>
                <button onClick={go("/signin")} style={{ position: "relative", background: "var(--grad)", color: "#fff", border: "none", padding: "9px 15px", borderRadius: 9, fontWeight: 700, fontSize: 12.5, cursor: "pointer" }}>Unlock</button>
              </div>
            </div>
          </div>
        </div>

        {/* trusted by */}
        <div style={{ maxWidth: 1100, margin: "8px auto 0", padding: "22px 28px 56px", textAlign: "center" }}>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".14em", textTransform: "uppercase", color: "var(--muted2)", marginBottom: 20 }}>
            Trusted by sports creators, podcasters, YouTubers &amp; media teams
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 44, flexWrap: "wrap", opacity: 0.55 }}>
            {logos.map((l) => (
              <span key={l} style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 19, letterSpacing: "-.01em" }}>{l}</span>
            ))}
          </div>
        </div>
      </div>

      {/* features */}
      <div id="features" style={{ maxWidth: 1200, margin: "0 auto", padding: "46px 28px 20px" }}>
        <div style={{ textAlign: "center", maxWidth: 640, margin: "0 auto 44px" }}>
          <div style={{ color: "var(--accent)", fontWeight: 700, fontSize: 13, letterSpacing: ".1em", textTransform: "uppercase", marginBottom: 12 }}>Everything, automated</div>
          <h2 style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 38, letterSpacing: "-.02em", margin: 0, lineHeight: 1.1 }}>One opinion in. A finished video out.</h2>
        </div>
        <div className="feat-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 18 }}>
          {features.map((f) => (
            <div key={f.title} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 18, padding: 24, gridColumn: f.span }}>
              <div style={{ height: 120, borderRadius: 12, background: `linear-gradient(150deg,${f.c1},${f.c2})`, position: "relative", overflow: "hidden", marginBottom: 18, display: "grid", placeItems: "center" }}>
                <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 70% 20%,#ffffff26,transparent 55%)" }} />
                <span style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 30, color: "#fff", opacity: 0.92, textShadow: "0 2px 12px #0004" }}>{f.glyph}</span>
              </div>
              <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 6 }}>{f.title}</div>
              <div style={{ fontSize: 14, color: "var(--muted)", lineHeight: 1.5 }}>{f.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* how it works */}
      <div id="how" style={{ maxWidth: 1000, margin: "0 auto", padding: "64px 28px" }}>
        <h2 style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 34, textAlign: "center", letterSpacing: "-.02em", margin: "0 0 40px" }}>How it works</h2>
        <div className="step-grid" style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr auto 1fr", alignItems: "center", gap: 14 }}>
          {steps.map((s) => (
            <StepCell key={s.n} s={s} />
          ))}
        </div>
      </div>

      {/* examples */}
      <div id="examples" style={{ padding: "20px 0 60px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 28px", display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 22 }}>
          <h2 style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 32, letterSpacing: "-.02em", margin: 0 }}>Made with BanterClips</h2>
          <span onClick={go("/signin")} style={{ fontSize: 14, fontWeight: 600, color: "var(--accent)", cursor: "pointer" }}>Start creating →</span>
        </div>
        <div style={{ display: "flex", gap: 16, overflowX: "auto", padding: "6px 28px 20px", scrollSnapType: "x mandatory" }}>
          {examples.map((c, i) => (
            <div key={i} style={{ flex: "0 0 172px", scrollSnapAlign: "start", position: "relative", borderRadius: 16, overflow: "hidden", aspectRatio: "9/16", background: `linear-gradient(160deg,${c.c1},${c.c2})`, cursor: "pointer" }}>
              <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 30% 15%,#ffffff26,transparent 55%)" }} />
              <div style={{ position: "absolute", top: 10, left: 10, background: "#00000055", backdropFilter: "blur(4px)", color: "#fff", fontSize: 9.5, fontWeight: 800, padding: "3px 7px", borderRadius: 6 }}>{c.sport}</div>
              <div style={{ position: "absolute", left: 10, right: 10, bottom: 34, color: "#fff", fontFamily: "var(--display)", fontWeight: 700, fontSize: 15, lineHeight: 1.25, textShadow: "0 2px 10px #0006" }}>{c.cap}</div>
              <div style={{ position: "absolute", left: 10, right: 10, bottom: 14, height: 3, background: "#ffffff33", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ height: "100%", width: "32%", background: "#fff" }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* testimonials */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 28px 60px" }}>
        <div className="testi-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 18 }}>
          {testimonials.map((t) => (
            <div key={t.name} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 18, padding: 26 }}>
              <div style={{ fontSize: 15.5, lineHeight: 1.55, fontWeight: 500, marginBottom: 20 }}>“{t.quote}”</div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 40, height: 40, borderRadius: "50%", background: `linear-gradient(140deg,${t.c1},${t.c2})` }} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{t.name}</div>
                  <div style={{ fontSize: 12.5, color: "var(--muted2)" }}>{t.role}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* pricing preview — two-plan model */}
      <div id="pricing" style={{ maxWidth: 1200, margin: "0 auto", padding: "30px 28px 20px", textAlign: "center" }}>
        <h2 style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 34, letterSpacing: "-.02em", margin: "0 0 8px" }}>Simple, creator-friendly pricing</h2>
        <p style={{ color: "var(--muted)", fontSize: 16, margin: "0 0 34px" }}>Publish free. Upgrade to download without the watermark.</p>
        <div className="plan-grid" style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,340px))", justifyContent: "center", gap: 16, textAlign: "left" }}>
          {plansMini.map((p) => (
            <div key={p.name} style={{ background: "var(--card)", border: `1px solid ${p.popular ? "var(--accent)" : "var(--border)"}`, borderRadius: 18, padding: 24, position: "relative" }}>
              {p.popular && (
                <div style={{ position: "absolute", top: -11, left: 24, background: "var(--grad)", color: "#fff", fontSize: 10.5, fontWeight: 800, padding: "4px 10px", borderRadius: 100, letterSpacing: ".04em" }}>POPULAR</div>
              )}
              <div style={{ fontWeight: 700, fontSize: 16 }}>{p.name}</div>
              <div style={{ margin: "12px 0 4px" }}>
                <span style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 32 }}>{p.price}</span>
                <span style={{ color: "var(--muted2)", fontSize: 13 }}>{p.per}</span>
              </div>
              <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>{p.tag}</div>
              <button onClick={go("/signin")} style={{ width: "100%", background: p.popular ? "var(--grad)" : "var(--bg3)", color: p.popular ? "#fff" : "var(--text)", border: "1px solid var(--border2)", padding: 11, borderRadius: 10, fontWeight: 700, fontSize: 13.5, cursor: "pointer" }}>
                {p.cta}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* final cta */}
      <div style={{ maxWidth: 1100, margin: "70px auto", padding: "0 28px" }}>
        <div style={{ position: "relative", overflow: "hidden", borderRadius: 26, background: "var(--grad)", padding: "60px 40px", textAlign: "center" }}>
          <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 80% 10%,#ffffff2e,transparent 50%)" }} />
          <h2 style={{ position: "relative", fontFamily: "var(--display)", fontWeight: 700, fontSize: 42, letterSpacing: "-.02em", margin: "0 0 22px", color: "#fff", lineHeight: 1.08 }}>
            Ready to make sports content 10x faster?
          </h2>
          <button onClick={go("/signin")} style={{ position: "relative", background: "#0b0d13", color: "#fff", border: "none", padding: "17px 34px", borderRadius: 14, fontWeight: 700, fontSize: 17, cursor: "pointer" }}>Start Free →</button>
          <div style={{ position: "relative", marginTop: 16, color: "#ffffffcc", fontSize: 13.5, fontWeight: 600 }}>Every sports opinion deserves a viral video.</div>
        </div>
      </div>

      {/* footer */}
      <div style={{ borderTop: "1px solid var(--border)", padding: "34px 28px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16, color: "var(--muted2)", fontSize: 13 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--muted)" }}>
            <Logo size={22} />
            <span style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 15, color: "var(--text)" }}>BanterClips</span>
          </div>
          <div>© 2026 BanterClips · Every sports opinion deserves a viral video. · All videos are AI-generated parody.</div>
        </div>
      </div>
    </div>
  );
}

function StepCell({ s }) {
  return (
    <>
      <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 16, padding: "26px 22px", textAlign: "center", gridColumn: s.col }}>
        <div style={{ width: 44, height: 44, borderRadius: 12, background: "var(--accentSoft)", color: "var(--accent)", fontFamily: "var(--display)", fontWeight: 700, fontSize: 20, display: "grid", placeItems: "center", margin: "0 auto 16px" }}>{s.n}</div>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 6 }}>{s.title}</div>
        <div style={{ fontSize: 13.5, color: "var(--muted)", lineHeight: 1.5 }}>{s.desc}</div>
      </div>
      {s.arrow && <div style={{ gridColumn: s.acol, color: "var(--muted2)", fontSize: 26, textAlign: "center" }}>→</div>}
    </>
  );
}
