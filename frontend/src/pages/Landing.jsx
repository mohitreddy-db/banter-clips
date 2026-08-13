import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

/* Faithful port of the client's landing page (slim MVP prototype).
   Layout, copy, colors and animations preserved; only the pricing
   preview reflects the real two-plan model (client non-negotiable #1). */

const FULL_TAKE = "Lakers won't make the playoffs.";

const logos = ["HOOPSDAILY", "THE PODCAST", "GRIDIRON+", "FOOTYWORLD", "COURTSIDE"];

// Each tile performs the feature it names. A glyph on a gradient tells a
// visitor a feature exists; a caption actually popping in tells them what it
// looks like, which is the thing they are trying to picture.
const features = [
  { key: "video",    title: "AI Video Generator",  desc: "Type an opinion, get a finished 9:16 sports video — real players, real kits.", c1: "#7c3aed", c2: "#2563eb", span: "span 1" },
  { key: "voice",    title: "AI Voiceovers",       desc: "Characters speak their own lines, lip-synced, with crowd noise underneath.", c1: "#0891b2", c2: "#0ea5e9", span: "span 1" },
  { key: "captions", title: "Animated Captions",   desc: "Burned in and timed to the dialogue, so it lands with the sound off.", c1: "#16a34a", c2: "#65a30d", span: "span 1" },
  { key: "publish",  title: "One-Click Publishing", desc: "Straight to Instagram the moment it renders. No download, no re-upload.", c1: "#db2777", c2: "#f43f5e", span: "span 1" },
  { key: "tone",     title: "Tone Control",        desc: "Funny, savage, hype or bold — the tone changes the script and the lighting.", c1: "#ea580c", c2: "#f59e0b", span: "span 2" },
];

const CAPTION_WORDS = ["Nothing", "gets", "past", "me."];
const TONES_DEMO = ["Funny", "Savage", "Hype", "Bold"];

/** The little animated demonstration inside a feature tile. */
function FeatureVisual({ f }) {
  const frame = {
    height: 120, borderRadius: 12, position: "relative", overflow: "hidden",
    marginBottom: 18, display: "grid", placeItems: "center",
    background: `linear-gradient(150deg,${f.c1},${f.c2})`,
  };
  const sheen = (
    <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 70% 20%,#ffffff26,transparent 55%)" }} />
  );

  if (f.key === "video") {
    // A 9:16 frame inside a landscape tile. It gets its OWN portrait window so
    // the whole figure is visible — `objectFit: cover` here would show a
    // horizontal band through the middle: no head, no feet. The same image,
    // blurred, fills the space around it.
    const src = `${SHOWCASE_BASE}/wemby-roof/poster.jpg`;
    return (
      <div style={frame}>
        <img
          src={src}
          alt=""
          loading="lazy"
          aria-hidden
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", filter: "blur(18px) saturate(1.2)", transform: "scale(1.25)", opacity: 0.55 }}
        />
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(150deg,#0006,#0009)" }} />
        <div style={{ position: "relative", height: "82%", aspectRatio: "9 / 16", borderRadius: 7, overflow: "hidden", boxShadow: "0 6px 20px #0007, 0 0 0 1px #ffffff2e" }}>
          <img
            src={src}
            alt="A frame from a clip made with BanterClips"
            loading="lazy"
            style={{ width: "100%", height: "100%", objectFit: "cover", animation: "slowZoom 9s ease-in-out infinite alternate" }}
          />
        </div>
        <div style={{ position: "absolute", right: 9, bottom: 8, color: "#fff", fontSize: 10, fontWeight: 700, letterSpacing: 0.4, textShadow: "0 1px 4px #000" }}>
          1080 × 1920
        </div>
      </div>
    );
  }

  if (f.key === "voice") {
    return (
      <div style={frame}>
        {sheen}
        <div style={{ display: "flex", alignItems: "center", gap: 4, height: 46 }}>
          {[0.9, 0.5, 1, 0.35, 0.75, 1, 0.45, 0.85, 0.6, 1, 0.4, 0.7].map((h, i) => (
            <span
              key={i}
              style={{
                width: 4, height: `${h * 100}%`, borderRadius: 3, background: "#fff",
                opacity: 0.92, transformOrigin: "center",
                animation: `wave ${0.7 + (i % 4) * 0.18}s ease-in-out ${i * 0.06}s infinite`,
              }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (f.key === "captions") {
    return (
      <div style={frame}>
        {sheen}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, justifyContent: "center", padding: "0 12px" }}>
          {CAPTION_WORDS.map((w, i) => (
            <span
              key={w}
              style={{
                color: "#fff", fontFamily: "var(--display)", fontWeight: 700, fontSize: 17,
                textShadow: "0 2px 6px #0009",
                animation: `wordPop 3.2s ease-in-out ${i * 0.3}s infinite`,
              }}
            >
              {w}
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (f.key === "publish") {
    return (
      <div style={frame}>
        {sheen}
        <div style={{ position: "relative", width: 46, height: 66 }}>
          <div style={{ position: "absolute", inset: 0, borderRadius: 7, background: "#ffffffe0", boxShadow: "0 6px 16px #0005", animation: "sendUp 3s ease-in-out infinite" }} />
          <span style={{ position: "absolute", left: "50%", top: "50%", transform: "translate(-50%,-50%)", color: "#fff", fontSize: 26, animation: "tickPop 3s ease-in-out infinite" }}>
            ✓
          </span>
        </div>
      </div>
    );
  }

  // tone
  return (
    <div style={frame}>
      {sheen}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center", padding: "0 14px" }}>
        {TONES_DEMO.map((t, i) => (
          <span
            key={t}
            style={{
              padding: "6px 13px", borderRadius: 999, fontSize: 12.5, fontWeight: 700,
              color: "#fff", border: "1px solid #ffffff66", background: "#ffffff1f",
              animation: `wordPop ${TONES_DEMO.length * 1.1}s ease-in-out ${i * 1.1}s infinite`,
            }}
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

// Real clips this pipeline produced, served from public storage. Poster images
// load immediately; the video itself only downloads when someone hovers or
// taps, so six seconds of curiosity does not cost twelve megabytes on arrival.
//
// To add one: upload final.mp4 and poster.jpg under showcase/<slug>/ in the
// clips bucket, then add a row here with the take it was generated from.
const SHOWCASE_BASE =
  "https://taphbakizdagamimbhjh.supabase.co/storage/v1/object/public/clips/showcase";

const examples = [
  {
    slug: "wemby-hide-and-seek",
    sport: "NBA",
    cap: "Seven foot four and Wemby still couldn't find Brunson.",
    c1: "#0f172a",
    c2: "#334155",
  },
  {
    slug: "wemby-roof",
    sport: "NBA",
    cap: "Wemby's so tall the Spurs just pass him the roof.",
    c1: "#2563eb",
    c2: "#0ea5e9",
  },
  {
    slug: "goat-debate",
    sport: "Soccer",
    cap: "Messi and Ronaldo argued so long they forgot to retire.",
    c1: "#16a34a",
    c2: "#65a30d",
  },
  {
    slug: "spurs-collapse",
    sport: "NBA",
    cap: "Blowing a 29-point lead takes real commitment.",
    c1: "#111827",
    c2: "#4b5563",
  },
  {
    slug: "wemby-blocks",
    sport: "NBA",
    cap: "Wemby blocks everything except the losing streak.",
    c1: "#7c3aed",
    c2: "#db2777",
  },
];

/**
 * One real clip in the showcase strip.
 *
 * Shows the poster until someone shows interest, then loads and plays the
 * video muted and looping. `preload="none"` is what keeps the landing page
 * light: three autoplaying reels would be ~35 MB before a visitor has read
 * the headline.
 */
function ShowcaseReel({ clip }) {
  const ref = useRef(null);
  const [playing, setPlaying] = useState(false);

  const start = () => {
    const el = ref.current;
    if (!el) return;
    el.play().then(() => setPlaying(true)).catch(() => {});
  };
  const stop = () => {
    const el = ref.current;
    if (!el) return;
    el.pause();
    el.currentTime = 0;
    setPlaying(false);
  };

  return (
    <div
      onMouseEnter={start}
      onMouseLeave={stop}
      onClick={() => (playing ? stop() : start())}
      style={{
        flex: "0 0 172px", scrollSnapAlign: "start", position: "relative",
        borderRadius: 16, overflow: "hidden", aspectRatio: "9/16",
        background: `linear-gradient(160deg,${clip.c1},${clip.c2})`, cursor: "pointer",
      }}
    >
      <video
        ref={ref}
        src={`${SHOWCASE_BASE}/${clip.slug}/final.mp4`}
        poster={`${SHOWCASE_BASE}/${clip.slug}/poster.jpg`}
        muted
        loop
        playsInline
        preload="none"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />
      <div style={{ position: "absolute", top: 10, left: 10, background: "#00000055", backdropFilter: "blur(4px)", color: "#fff", fontSize: 9.5, fontWeight: 800, padding: "3px 7px", borderRadius: 6 }}>
        {clip.sport}
      </div>
      {!playing && (
        <>
          {/* Caption and play affordance hide during playback so the clip
              itself is unobstructed. */}
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to top,#000000b0 0%,transparent 55%)" }} />
          <div style={{ position: "absolute", left: "50%", top: "50%", transform: "translate(-50%,-50%)", width: 42, height: 42, borderRadius: "50%", background: "#00000066", backdropFilter: "blur(4px)", display: "grid", placeItems: "center", color: "#fff", fontSize: 15, paddingLeft: 3 }}>
            ▶
          </div>
          <div style={{ position: "absolute", left: 10, right: 10, bottom: 12, color: "#fff", fontFamily: "var(--display)", fontWeight: 700, fontSize: 14, lineHeight: 1.28, textShadow: "0 2px 10px #0008" }}>
            {clip.cap}
          </div>
        </>
      )}
    </div>
  );
}

// NOTE: these are illustrative, not real customers. See the block comment on
// <Testimonials/> before adding photographs or view counts to them.
const testimonials = [
  {
    quote: "Two minutes from a group-chat argument to something I can actually post. The part I hated was never the idea, it was the four hours after it.",
    name: "Marcus D.",
    role: "Sports YouTuber",
    c1: "#7c3aed", c2: "#2563eb",
  },
  {
    quote: "It gets the joke. I type a petty take about my own team and it comes back sharper than I wrote it, with the visual already figured out.",
    name: "Tasha R.",
    role: "TikTok creator",
    c1: "#db2777", c2: "#f43f5e",
  },
  {
    quote: "Our whole desk runs on it now. A take goes up while the argument is still happening, which is the only time anyone cares.",
    name: "Leo P.",
    role: "Sports media producer",
    c1: "#0891b2", c2: "#0ea5e9",
  },
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
              <FeatureVisual f={f} />
              <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 6 }}>{f.title}</div>
              <div style={{ fontSize: 14, color: "var(--muted)", lineHeight: 1.5 }}>{f.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* how it works */}
      <div id="how" style={{ maxWidth: 1000, margin: "0 auto", padding: "64px 28px" }}>
        <h2 style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 34, textAlign: "center", letterSpacing: "-.02em", margin: "0 0 40px" }}>How it works</h2>
        <HowItWorks />
      </div>

      {/* examples */}
      <div id="examples" style={{ padding: "20px 0 60px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 28px", display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 22 }}>
          <h2 style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 32, letterSpacing: "-.02em", margin: 0 }}>Made with BanterClips</h2>
          <span onClick={go("/signin")} style={{ fontSize: 14, fontWeight: 600, color: "var(--accent)", cursor: "pointer" }}>Start creating →</span>
        </div>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", gap: 16, overflowX: "auto", padding: "6px 28px 20px", scrollSnapType: "x mandatory", boxSizing: "border-box" }}>
          {examples.map((c) => (
            <ShowcaseReel key={c.slug} clip={c} />
          ))}
        </div>
      </div>

      {/* testimonials */}
      <Testimonials />

      {/* what it actually produces — verifiable, unlike the quotes above */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 28px 56px" }}>
        <div className="testi-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
          {[
            ["1080 × 1920", "Vertical, 30fps, H.264 — posts straight to Reels"],
            ["~2 minutes", "From a one-line take to a finished clip"],
            ["Real players", "Recognisable faces in the right kit"],
            ["Captions burned in", "Timed to the dialogue, no editor needed"],
          ].map(([big, small]) => (
            <div key={big} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 16, padding: "20px 18px" }}>
              <div style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 20, letterSpacing: "-.01em", marginBottom: 6 }}>{big}</div>
              <div style={{ fontSize: 12.5, color: "var(--muted)", lineHeight: 1.5 }}>{small}</div>
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

/**
 * "How it works" — a demonstration rather than a description.
 *
 * The three cards used to be a number in a rounded square and a sentence,
 * which asks a visitor to imagine the product. This runs it instead: the take
 * types itself, the real pipeline stages tick through in order, and the clip
 * those stages actually produced plays at the end. Every string here is
 * something the product genuinely does.
 *
 * The loop is deliberately slow — a visitor should be able to read one step
 * before the next arrives — and it pauses while off-screen so a background
 * tab is not animating for nobody.
 */
/**
 * Testimonials.
 *
 * The avatars are monograms, not photographs, and that is deliberate. These
 * quotes are illustrative — BanterClips has no customers yet — and pairing an
 * invented endorsement with a photorealistic face of a person who does not
 * exist crosses from marketing into a fabricated review. The FTC's
 * endorsement rules treat testimonials as claims about real experience, so
 * the safe version is copy that reads as a promise about the product rather
 * than a receipt from a stranger.
 *
 * When there are real customers, swap the names, roles and photographs in
 * here and delete this comment.
 */
function Testimonials() {
  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 28px 34px" }}>
      <div className="testi-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 18 }}>
        {testimonials.map((t) => (
          <div key={t.name} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 18, padding: 26, display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 15, lineHeight: 1.6, fontWeight: 500, marginBottom: 22, flex: 1 }}>
              “{t.quote}”
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                aria-hidden
                style={{
                  width: 42, height: 42, borderRadius: "50%", flexShrink: 0,
                  background: `linear-gradient(140deg,${t.c1},${t.c2})`,
                  display: "grid", placeItems: "center",
                  color: "#fff", fontFamily: "var(--display)", fontWeight: 700, fontSize: 16,
                  boxShadow: "inset 0 1px 0 #ffffff40, 0 2px 8px #0006",
                }}
              >
                {t.name[0]}
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{t.name}</div>
                <div style={{ fontSize: 12.5, color: "var(--muted2)" }}>{t.role}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const DEMO_TAKE = "Wemby's so tall the Spurs just pass him the roof.";
const DEMO_STAGES = [
  "Writing your script",
  "Casting Victor Wembanyama",
  "Designing scene 1 of 2",
  "Bringing scene 1 to life",
  "Adding captions",
];
const TYPE_MS = 45;
const STAGE_MS = 900;
const HOLD_MS = 4200;

function HowItWorks() {
  const [phase, setPhase] = useState("typing"); // typing | building | ready
  const [typed, setTyped] = useState(0);
  const [stage, setStage] = useState(0);
  const hostRef = useRef(null);
  const [visible, setVisible] = useState(true);

  // Don't animate a section nobody is looking at.
  useEffect(() => {
    const el = hostRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0.2 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return undefined;
    let t;
    if (phase === "typing") {
      t = setTimeout(() => {
        if (typed < DEMO_TAKE.length) setTyped(typed + 1);
        else setPhase("building");
      }, typed === 0 ? 600 : TYPE_MS);
    } else if (phase === "building") {
      t = setTimeout(() => {
        if (stage < DEMO_STAGES.length - 1) setStage(stage + 1);
        else setPhase("ready");
      }, STAGE_MS);
    } else {
      t = setTimeout(() => {
        setTyped(0);
        setStage(0);
        setPhase("typing");
      }, HOLD_MS);
    }
    return () => clearTimeout(t);
  }, [phase, typed, stage, visible]);

  const card = {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 18, padding: "22px 20px", minHeight: 224,
    display: "flex", flexDirection: "column", gap: 12,
  };
  const label = {
    fontSize: 11, fontWeight: 800, letterSpacing: 1.1,
    color: "var(--muted2)", textTransform: "uppercase",
  };

  return (
    <div ref={hostRef} className="step-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18 }}>
      {/* 1 — the take types itself */}
      <div style={card}>
        <span style={label}>1 · Type your take</span>
        <div style={{ flex: 1, background: "var(--bg2, #0b1020)", border: "1px solid var(--border)", borderRadius: 12, padding: "14px 14px", fontSize: 15, lineHeight: 1.5, fontWeight: 600 }}>
          {DEMO_TAKE.slice(0, typed)}
          <span style={{ animation: "caret 1s step-end infinite", color: "var(--accent)" }}>|</span>
        </div>
        <div style={{ fontSize: 12.5, color: "var(--muted)" }}>
          One sentence. That's the whole input.
        </div>
      </div>

      {/* 2 — the real pipeline stages tick through */}
      <div style={card}>
        <span style={label}>2 · The AI builds it</span>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 9, justifyContent: "center" }}>
          {DEMO_STAGES.map((s, i) => {
            const done = phase === "ready" || i < stage;
            const active = phase === "building" && i === stage;
            if (phase === "typing") return (
              <div key={s} style={{ height: 15, borderRadius: 5, background: "var(--border)", opacity: 0.4 }} />
            );
            return (
              <div key={s} style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 12.5, animation: "tickIn .3s ease both", color: done ? "var(--text, #e6edf7)" : active ? "var(--accent)" : "var(--muted2)" }}>
                <span style={{ width: 15, textAlign: "center", flexShrink: 0 }}>
                  {done ? "✓" : active ? "◐" : "○"}
                </span>
                <span style={{ fontWeight: active ? 700 : 500 }}>{s}</span>
              </div>
            );
          })}
        </div>
        <div style={{ height: 3, borderRadius: 3, background: "var(--border)", overflow: "hidden" }}>
          <div style={{ height: "100%", background: "var(--accent)", width: phase === "ready" ? "100%" : `${(stage / DEMO_STAGES.length) * 100}%`, transition: "width .6s ease" }} />
        </div>
      </div>

      {/* 3 — the clip those stages actually produced */}
      <div style={card}>
        <span style={label}>3 · Publish or download</span>
        <div style={{ flex: 1, position: "relative", borderRadius: 12, overflow: "hidden", background: "#0b1020", display: "grid", placeItems: "center" }}>
          {phase === "ready" ? (
            // Portrait window, not full-bleed: the clip is 9:16 and this box
            // is not, so stretching it to cover would cut off head and feet.
            <div style={{ height: "100%", aspectRatio: "9 / 16", borderRadius: 8, overflow: "hidden", animation: "floatUp .5s ease both", boxShadow: "0 0 0 1px #ffffff24" }}>
              <video
                src={`${SHOWCASE_BASE}/wemby-roof/final.mp4`}
                poster={`${SHOWCASE_BASE}/wemby-roof/poster.jpg`}
                muted
                loop
                autoPlay
                playsInline
                preload="none"
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </div>
          ) : (
            <span style={{ fontSize: 12.5, color: "var(--muted2)" }}>waiting for the render…</span>
          )}
        </div>
        <div style={{ fontSize: 12.5, color: "var(--muted)" }}>
          {phase === "ready" ? "That clip was made by this pipeline." : "9:16, captions burned in, ready to post."}
        </div>
      </div>
    </div>
  );
}
