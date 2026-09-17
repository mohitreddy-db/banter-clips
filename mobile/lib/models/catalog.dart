/// The static catalogue the web app ships in `Studio.jsx` / `Onboarding.jsx`:
/// every sport the backend accepts, the five tones, and the teams and players
/// we suggest for the "who is in it" box. Kept in one place so the create
/// screen, the viral feed and onboarding cannot drift from each other — or
/// from the `ClipCreate` enum on the server.
library;

class Sport {
  const Sport(this.key, this.emoji);
  final String key;
  final String emoji;
}

/// Exactly the `sport` enum in `ClipCreate`, in the order the web shows them.
const sports = <Sport>[
  Sport('Soccer', '⚽'),
  Sport('NBA', '🏀'),
  Sport('NFL', '🏈'),
  Sport('MLB', '⚾'),
  Sport('NHL', '🏒'),
  Sport('Tennis', '🎾'),
  Sport('F1', '🏎'),
  Sport('Cricket', '🏏'),
  Sport('Golf', '⛳'),
  Sport('Boxing', '🥊'),
  Sport('MMA', '🥋'),
  Sport('Esports', '🎮'),
  Sport('Other', '🎯'),
];

final List<String> sportKeys = sports.map((s) => s.key).toList(growable: false);

String sportEmoji(String key) {
  for (final sport in sports) {
    if (sport.key == key) return sport.emoji;
  }
  return '🎯';
}

bool isKnownSport(String? key) => key != null && sportKeys.contains(key);

class Tone {
  const Tone(this.key, this.emoji, this.sub);
  final String key;
  final String emoji;
  final String sub;
}

/// The `tone` enum in `ClipCreate`. Roast sits between Savage and Hype, as it
/// does on the web.
const tones = <Tone>[
  Tone('Funny', '😄', 'Playful roast'),
  Tone('Savage', '🔪', 'No mercy'),
  Tone('Roast', '🔥', 'Friendly burn'),
  Tone('Hype', '📣', 'Full energy'),
  Tone('Bold', '💪', 'Fearless claim'),
];

final List<String> toneKeys = tones.map((t) => t.key).toList(growable: false);

bool isKnownTone(String? key) => key != null && toneKeys.contains(key);

/// Per-sport suggestions for teams and players — the same list the web
/// offers under the "who is in it" and onboarding boxes.
const _subjects = <String, ({List<String> teams, List<String> players})>{
  'Soccer': (
    teams: [
      'Arsenal', 'Real Madrid', 'Barcelona', 'Man City', 'Liverpool',
      'Man Utd', 'Chelsea', 'Bayern', 'PSG', 'Inter Milan',
    ],
    players: [
      'Mbappé', 'Haaland', 'Vinícius Jr', 'Bellingham', 'Saka', 'Yamal',
      'Salah', 'Messi', 'Ronaldo', 'Ødegaard',
    ],
  ),
  'NBA': (
    teams: [
      'Lakers', 'Celtics', 'Warriors', 'Knicks', 'Nuggets', 'Bucks', 'Heat',
      'Thunder', 'Mavericks', '76ers',
    ],
    players: [
      'LeBron', 'Curry', 'Jokić', 'Dončić', 'Giannis', 'Wembanyama', 'Tatum',
      'Durant', 'Brunson', 'Edwards',
    ],
  ),
  'NFL': (
    teams: [
      'Chiefs', 'Eagles', '49ers', 'Cowboys', 'Bills', 'Ravens', 'Lions',
      'Packers', 'Dolphins', 'Steelers',
    ],
    players: [
      'Mahomes', 'Josh Allen', 'Lamar Jackson', 'Kelce', 'Burrow',
      'Jefferson', 'Hurts', 'Tyreek Hill', 'Micah Parsons', 'CMC',
    ],
  ),
  'MLB': (
    teams: [
      'Yankees', 'Dodgers', 'Red Sox', 'Mets', 'Braves', 'Astros', 'Cubs',
      'Phillies', 'Padres', 'Orioles',
    ],
    players: [
      'Ohtani', 'Aaron Judge', 'Mookie Betts', 'Juan Soto', 'Acuña Jr',
      'Freeman', 'Skenes', 'Witt Jr', 'Harper', 'Machado',
    ],
  ),
  'NHL': (
    teams: [
      'Maple Leafs', 'Oilers', 'Bruins', 'Rangers', 'Panthers', 'Avalanche',
      'Canadiens', 'Golden Knights', 'Penguins', 'Lightning',
    ],
    players: [
      'McDavid', 'Crosby', 'Ovechkin', 'Matthews', 'MacKinnon', 'Draisaitl',
      'Makar', 'Bedard', 'Hellebuyck', 'Kucherov',
    ],
  ),
  'Tennis': (
    teams: [
      'Wimbledon', 'US Open', 'Roland Garros', 'Australian Open',
      'ATP Finals', 'Davis Cup',
    ],
    players: [
      'Alcaraz', 'Sinner', 'Djokovic', 'Medvedev', 'Zverev', 'Świątek',
      'Sabalenka', 'Gauff', 'Nadal', 'Federer',
    ],
  ),
  'F1': (
    teams: [
      'Red Bull', 'Ferrari', 'McLaren', 'Mercedes', 'Aston Martin',
      'Williams', 'Alpine',
    ],
    players: [
      'Verstappen', 'Norris', 'Leclerc', 'Hamilton', 'Piastri', 'Russell',
      'Alonso', 'Sainz',
    ],
  ),
  'Cricket': (
    teams: [
      'India', 'Australia', 'England', 'Pakistan', 'Mumbai Indians',
      'Chennai Super Kings', 'RCB', 'New Zealand',
    ],
    players: [
      'Virat Kohli', 'Rohit Sharma', 'Bumrah', 'Babar Azam', 'Joe Root',
      'Ben Stokes', 'Smith', 'Rashid Khan',
    ],
  ),
  'Golf': (
    teams: [
      'The Masters', 'The Open', 'PGA Championship', 'US Open', 'Ryder Cup',
      'LIV Golf',
    ],
    players: [
      'Scottie Scheffler', 'Rory McIlroy', 'Tiger Woods', 'Jon Rahm',
      'Bryson DeChambeau', 'Xander Schauffele',
    ],
  ),
  'Boxing': (
    teams: ['Heavyweight', 'Middleweight', 'Welterweight', 'Undisputed'],
    players: [
      'Canelo', 'Usyk', 'Tyson Fury', 'Anthony Joshua', 'Terence Crawford',
      'Mike Tyson', 'Jake Paul',
    ],
  ),
  'MMA': (
    teams: ['UFC', 'Bellator', 'PFL', 'Lightweight', 'Heavyweight'],
    players: [
      'Jon Jones', 'Islam Makhachev', 'Conor McGregor', 'Alex Pereira',
      "Sean O'Malley", 'Khabib', 'Ilia Topuria',
    ],
  ),
  'Esports': (
    teams: [
      'T1', 'G2 Esports', 'Fnatic', 'NAVI', 'Team Liquid', 'Cloud9',
      'FaZe Clan', '100 Thieves',
    ],
    players: ['Faker', 's1mple', 'ZywOo', 'Caps', 'TenZ', 'Bugha', 'Chovy', 'donk'],
  ),
  'Other': (teams: [], players: []),
};

/// Round-robin suggestions across the chosen sports, so someone who follows
/// two sports sees both represented rather than ten from the first. With no
/// sports picked, Soccer and NBA stand in — the same default the web uses.
List<String> subjectSuggestions(
  List<String> forSports, {
  required bool players,
  int limit = 12,
}) {
  final chosen = forSports.isEmpty ? const ['Soccer', 'NBA'] : forSports;
  final out = <String>[];
  for (var i = 0; out.length < limit && i < 12; i++) {
    for (final sport in chosen) {
      final entry = _subjects[sport];
      if (entry == null) continue;
      final list = players ? entry.players : entry.teams;
      if (i < list.length && !out.contains(list[i])) out.add(list[i]);
      if (out.length >= limit) break;
    }
  }
  return out;
}
