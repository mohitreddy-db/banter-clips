import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSeo } from "../lib/seo.js";

const LIBRARY = {
  "Hot Takes": ["Arsenal fans are celebrating too early", "This NBA contender is one injury away from disaster"],
  Roasts: ["Roast my team after that embarrassing performance", "This manager has run out of excuses"],
  Predictions: ["Predict the next shock result everyone will dismiss", "This rookie will own the league within two years"],
  GOAT: ["Messi is still the GOAT and it is not close", "Make the case for LeBron over Jordan"],
  "Player Battles": ["Mbappé vs Haaland: who would you build a team around?", "Who wins one-on-one: prime Kobe or prime Jordan?"],
  "Team Battles": ["Which club has the most intimidating home crowd?", "Compare these two teams at their absolute peak"],
  "Match Day": ["The one matchup that will decide tonight's game", "Why the favorite should be nervous before kickoff"],
  "Post-Match": ["The scoreline hides what really happened in this match", "Name the player who changed the game"],
  Rivalry: ["Why this rivalry means more than trophies", "The coldest moment in this rivalry's history"],
  Funny: ["Turn today's biggest sports story into a locker-room comedy", "If this team's season were a group chat"],
  Controversial: ["The rule every fan complains about but secretly needs", "This superstar is brilliant but overrated"],
};

export default function Prompts() {
  useSeo({ title: "Prompt Library — BanterClips", description: "Ready-to-edit sports video ideas.", path: "/prompts", noindex: true });
  const nav = useNavigate();
  const [category, setCategory] = useState("Hot Takes");
  const prompts = useMemo(() => LIBRARY[category] || [], [category]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h1 style={{ margin: "8px 0", fontSize: "clamp(26px,6vw,38px)", color: "var(--app-text)" }}>💡 Prompt Library</h1>
        <div style={{ color: "var(--app-muted)" }}>Pick an angle, edit it in Studio, then generate.</div>
      </div>
      <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4 }}>
        {Object.keys(LIBRARY).map((name) => (
          <button key={name} className={`chip${category === name ? " on" : ""}`} onClick={() => setCategory(name)} style={{ whiteSpace: "nowrap" }}>
            {name}
          </button>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 14 }}>
        {prompts.map((prompt) => (
          <button
            key={prompt}
            className="card"
            onClick={() => nav(`/studio?prompt=${encodeURIComponent(prompt)}`)}
            style={{ padding: 20, textAlign: "left", cursor: "pointer", color: "var(--app-text)", display: "flex", flexDirection: "column", gap: 16 }}
          >
            <span style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.5 }}>“{prompt}”</span>
            <span style={{ color: "var(--app-cyan)", fontSize: 13, fontWeight: 700 }}>Edit & generate →</span>
          </button>
        ))}
      </div>
    </div>
  );
}
