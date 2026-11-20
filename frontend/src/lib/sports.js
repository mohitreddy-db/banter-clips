/* The sport vocabulary, shared by the create page, onboarding and the admin
 * catalog. Mirrors backend models.SPORTS — the order matters (Soccer leads
 * because it is what the app is actually used for) and the ids must match
 * exactly, since the API validates against the same list.
 *
 * SUGGESTIONS exist so onboarding never shows an empty text box. Asking a
 * fan to *type* their teams is a worse question than asking them to tap two
 * chips, and a blank field is the step people abandon. They are curated
 * rather than live: a name here only has to be recognisable enough to tap,
 * and a static list costs nothing and never fails. The trending feed
 * (backend video/trending.py) is the obvious upgrade when we want these to
 * move week to week.
 */

// `key` is the API value stored on every clip and preference and cannot
// change. `label` is what people see: league names (NBA, NFL, MLB, NHL, F1)
// are registered marks and were showing in App Store screenshots as filter
// chips, so the chips now name the sport instead.
export const SPORTS = [
  { key: "Soccer", icon: "⚽" },
  { key: "NBA", icon: "🏀", label: "Basketball" },
  { key: "NFL", icon: "🏈", label: "American Football" },
  { key: "MLB", icon: "⚾", label: "Baseball" },
  { key: "NHL", icon: "🏒", label: "Ice Hockey" },
  { key: "Tennis", icon: "🎾" },
  { key: "F1", icon: "🏎", label: "Motorsport" },
  { key: "Cricket", icon: "🏏" },
  { key: "Golf", icon: "⛳" },
  { key: "Boxing", icon: "🥊" },
  { key: "MMA", icon: "🥋" },
  { key: "Esports", icon: "🎮" },
  { key: "Other", icon: "🎯" },
];

export const SPORT_KEYS = SPORTS.map((s) => s.key);
export const sportIcon = (key) => SPORTS.find((s) => s.key === key)?.icon || "🎯";
export const sportLabel = (key) => SPORTS.find((s) => s.key === key)?.label || key;

/**
 * Per-sport suggestions for sides and roles.
 *
 * These were real clubs and real players until App Review rejected the app
 * under guideline 4.1(a) for trading on sports celebrities without the rights
 * to them. The generator refuses a real name now (see
 * `backend/app/services/content_safety.py`), so suggesting one would hand the
 * user a dead end. Kept in step with `mobile/lib/models/catalog.dart`.
 */
export const SUGGESTIONS = {
  Soccer: {
    teams: ["my club", "the league leaders", "our rivals", "the title race", "the relegation scrap", "the derby", "the away end", "the cup draw"],
    players: ["the striker", "the keeper", "the captain", "the new signing", "the wonderkid", "the manager", "the referee", "the pundit", "the winger", "the holding midfielder"],
  },
  NBA: {
    teams: ["my team", "the top seed", "our rivals", "the playoff race", "the rebuild", "the trade deadline", "the bench mob", "the draft"],
    players: ["the franchise guy", "the rookie", "the sixth man", "the point guard", "the centre", "the head coach", "the ref", "the sideline reporter", "the sharpshooter", "the veteran"],
  },
  NFL: {
    teams: ["my team", "the number one seed", "our division rivals", "the playoffs", "the draft", "free agency", "the offensive line", "the defence"],
    players: ["the quarterback", "the rookie QB", "the running back", "the lineman", "the kicker", "the head coach", "the coordinator", "the commentator", "the wide receiver", "the veteran"],
  },
  MLB: {
    teams: ["my team", "the division leaders", "our rivals", "the wild card", "the trade deadline", "the farm system", "the bullpen", "the lineup"],
    players: ["the slugger", "the ace", "the closer", "the rookie", "the catcher", "the manager", "the umpire", "the broadcaster", "the leadoff hitter", "the utility guy"],
  },
  NHL: {
    teams: ["my team", "the conference leaders", "our rivals", "the playoff push", "the trade deadline", "the fourth line", "the power play", "the draft"],
    players: ["the captain", "the goalie", "the rookie", "the enforcer", "the sniper", "the head coach", "the ref", "the analyst", "the defenceman", "the veteran"],
  },
  Tennis: {
    teams: ["the draw", "the seeds", "centre court", "the final", "the qualifiers", "the tour", "the rankings", "the doubles"],
    players: ["the top seed", "the qualifier", "the big server", "the grinder", "the teenager", "the comeback player", "the umpire", "the coach", "the crowd favourite", "the veteran"],
  },
  Cricket: {
    teams: ["my side", "the table toppers", "our rivals", "the series", "the selectors", "the dressing room", "the tail", "the top order"],
    players: ["the opener", "the captain", "the spinner", "the quick", "the wicketkeeper", "the all-rounder", "the umpire", "the commentator", "the nightwatchman", "the veteran"],
  },
  Golf: {
    teams: ["the leaderboard", "the final group", "the cut", "the majors", "the back nine", "the tour", "the gallery", "the team event"],
    players: ["the leader", "the rookie", "the long hitter", "the putter", "the caddie", "the playing captain", "the rules official", "the commentator", "the journeyman", "the veteran"],
  },
  Boxing: {
    teams: ["the undercard", "the main event", "the belts", "the division", "the weigh-in", "the judges", "the promotion", "the rematch"],
    players: ["the champion", "the challenger", "the prospect", "the journeyman", "the trainer", "the cutman", "the referee", "the ring announcer", "the promoter", "the veteran"],
  },
  MMA: {
    teams: ["the main card", "the title picture", "the division", "the weigh-in", "the judges", "the promotion", "the rematch", "the prelims"],
    players: ["the champion", "the challenger", "the prospect", "the grappler", "the striker", "the coach", "the referee", "the commentator", "the short-notice replacement", "the veteran"],
  },
  Esports: {
    teams: ["my team", "the top seed", "our rivals", "the group stage", "the roster move", "the bootcamp", "the grand final", "the meta"],
    players: ["the star player", "the rookie", "the in-game leader", "the support", "the coach", "the analyst", "the caster", "the sub", "the free agent", "the veteran"],
  },
  Other: { teams: [], players: [] },
};

/** Suggested teams/players across everything the user follows, de-duped. */
export function suggestionsFor(sports, kind, limit = 12) {
  const picked = sports?.length ? sports : ["Soccer", "NBA"];
  const out = [];
  // Round-robin across the chosen sports so a two-sport fan sees both, rather
  // than ten soccer roles and nothing else.
  for (let i = 0; out.length < limit && i < 12; i += 1) {
    for (const sport of picked) {
      const item = SUGGESTIONS[sport]?.[kind]?.[i];
      if (item && !out.includes(item)) out.push(item);
      if (out.length >= limit) break;
    }
  }
  return out;
}
