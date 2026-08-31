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

export const SPORTS = [
  { key: "Soccer", icon: "⚽" },
  { key: "NBA", icon: "🏀" },
  { key: "NFL", icon: "🏈" },
  { key: "MLB", icon: "⚾" },
  { key: "NHL", icon: "🏒" },
  { key: "Tennis", icon: "🎾" },
  { key: "F1", icon: "🏎" },
  { key: "Cricket", icon: "🏏" },
  { key: "Golf", icon: "⛳" },
  { key: "Boxing", icon: "🥊" },
  { key: "MMA", icon: "🥋" },
  { key: "Other", icon: "🎯" },
];

export const SPORT_KEYS = SPORTS.map((s) => s.key);
export const sportIcon = (key) => SPORTS.find((s) => s.key === key)?.icon || "🎯";

export const SUGGESTIONS = {
  Soccer: {
    teams: ["Arsenal", "Real Madrid", "Barcelona", "Man City", "Liverpool", "Man Utd", "Chelsea", "Bayern", "PSG", "Inter Milan"],
    players: ["Mbappé", "Haaland", "Vinícius Jr", "Bellingham", "Saka", "Yamal", "Salah", "Messi", "Ronaldo", "Ødegaard"],
  },
  NBA: {
    teams: ["Lakers", "Celtics", "Warriors", "Knicks", "Nuggets", "Bucks", "Heat", "Thunder", "Mavericks", "76ers"],
    players: ["LeBron", "Curry", "Jokić", "Dončić", "Giannis", "Wembanyama", "Tatum", "Durant", "Brunson", "Edwards"],
  },
  NFL: {
    teams: ["Chiefs", "Eagles", "49ers", "Cowboys", "Bills", "Ravens", "Lions", "Packers", "Dolphins", "Steelers"],
    players: ["Mahomes", "Josh Allen", "Lamar Jackson", "Kelce", "Burrow", "Jefferson", "Hurts", "Tyreek Hill", "Micah Parsons", "CMC"],
  },
  MLB: {
    teams: ["Yankees", "Dodgers", "Red Sox", "Mets", "Braves", "Astros", "Cubs", "Phillies", "Padres", "Orioles"],
    players: ["Ohtani", "Aaron Judge", "Mookie Betts", "Juan Soto", "Acuña Jr", "Freeman", "Skenes", "Witt Jr", "Harper", "Machado"],
  },
  NHL: {
    teams: ["Maple Leafs", "Oilers", "Bruins", "Rangers", "Panthers", "Avalanche", "Canadiens", "Golden Knights", "Penguins", "Lightning"],
    players: ["McDavid", "Crosby", "Ovechkin", "Matthews", "MacKinnon", "Draisaitl", "Makar", "Bedard", "Hellebuyck", "Kucherov"],
  },
  Tennis: {
    teams: ["Wimbledon", "US Open", "Roland Garros", "Australian Open", "ATP Finals", "Davis Cup"],
    players: ["Alcaraz", "Sinner", "Djokovic", "Medvedev", "Zverev", "Świątek", "Sabalenka", "Gauff", "Nadal", "Federer"],
  },
  F1: {
    teams: ["Red Bull", "Ferrari", "McLaren", "Mercedes", "Aston Martin", "Williams", "Alpine"],
    players: ["Verstappen", "Norris", "Leclerc", "Hamilton", "Piastri", "Russell", "Alonso", "Sainz"],
  },
  Cricket: {
    teams: ["India", "Australia", "England", "Pakistan", "Mumbai Indians", "Chennai Super Kings", "RCB", "New Zealand"],
    players: ["Virat Kohli", "Rohit Sharma", "Bumrah", "Babar Azam", "Joe Root", "Ben Stokes", "Smith", "Rashid Khan"],
  },
  Golf: {
    teams: ["The Masters", "The Open", "PGA Championship", "US Open", "Ryder Cup", "LIV Golf"],
    players: ["Scottie Scheffler", "Rory McIlroy", "Tiger Woods", "Jon Rahm", "Bryson DeChambeau", "Xander Schauffele"],
  },
  Boxing: {
    teams: ["Heavyweight", "Middleweight", "Welterweight", "Undisputed"],
    players: ["Canelo", "Usyk", "Tyson Fury", "Anthony Joshua", "Terence Crawford", "Mike Tyson", "Jake Paul"],
  },
  MMA: {
    teams: ["UFC", "Bellator", "PFL", "Lightweight", "Heavyweight"],
    players: ["Jon Jones", "Islam Makhachev", "Conor McGregor", "Alex Pereira", "Sean O'Malley", "Khabib", "Ilia Topuria"],
  },
  Other: { teams: [], players: [] },
};

/** Suggested teams/players across everything the user follows, de-duped. */
export function suggestionsFor(sports, kind, limit = 12) {
  const picked = sports?.length ? sports : ["Soccer", "NBA"];
  const out = [];
  // Round-robin across the chosen sports so a two-sport fan sees both, rather
  // than ten Arsenal players and nothing else.
  for (let i = 0; out.length < limit && i < 12; i += 1) {
    for (const sport of picked) {
      const item = SUGGESTIONS[sport]?.[kind]?.[i];
      if (item && !out.includes(item)) out.push(item);
      if (out.length >= limit) break;
    }
  }
  return out;
}
