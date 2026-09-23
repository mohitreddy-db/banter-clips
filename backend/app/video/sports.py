"""Working out which sport a take is about.

Sport used to be a required choice before the user could type anything. It is
now optional: most takes name a league, a club or a player, and a take that
says "Mbappé just turned Real Sociedad's defense into cone drills" does not
need the user to also tick "Soccer".

Deterministic on purpose. An LLM call would cost money and latency on the
create page's hot path for something a keyword table answers correctly, and a
wrong guess is cheap anyway — sport only picks the fallback venue list and
roster, both of which the planner overrides once it has real context.

Order of resolution: what the user explicitly picked, then what the take says,
then what the user follows, then Soccer (what the app is actually used for).
"""

from __future__ import annotations

import re
import unicodedata

from ..models import SPORTS

# Marker words per sport: leagues, competitions, famous clubs and the terms
# only that sport uses. Kept to strong signals — "goal" appears in hockey and
# soccer, "ball" in everything, so neither earns a place here.
MARKERS: dict[str, tuple[str, ...]] = {
    "Soccer": (
        "soccer", "football club", "premier league", "la liga", "serie a",
        "bundesliga", "ligue 1", "champions league", "uefa", "fifa", "epl",
        "world cup", "ballon d'or", "arsenal", "chelsea", "liverpool",
        "man utd", "manchester united", "manchester city", "man city",
        "tottenham", "spurs fc", "real madrid", "barcelona", "barca",
        "atletico", "bayern", "juventus", "inter milan", "ac milan", "psg",
        "napoli", "dortmund", "ajax", "messi", "ronaldo", "mbappe", "mbappé",
        "haaland", "vinicius", "vinícius", "bellingham", "salah", "saka",
        "yamal", "neymar", "modric", "mourinho", "guardiola", "arteta",
        "klopp", "ancelotti", "midfielder", "striker", "offside", "nutmeg",
        "clean sheet", "var ", "penalty box", "free kick", "hat-trick",
    ),
    "NBA": (
        "nba", "basketball", "lakers", "celtics", "warriors", "knicks",
        "nuggets", "bucks", "heat", "spurs", "sixers", "76ers", "clippers",
        "mavericks", "mavs", "suns", "thunder", "grizzlies", "pelicans",
        "lebron", "curry", "steph", "durant", "giannis", "jokic", "doncic",
        "luka", "wembanyama", "wemby", "brunson", "tatum", "kawhi", "harden",
        "dunk", "three-pointer", "3-pointer", "triple-double", "free throw",
        "buzzer beater", "the paint", "playoffs seed",
    ),
    "NFL": (
        "nfl", "super bowl", "quarterback", " qb ", "touchdown", "field goal",
        "chiefs", "eagles", "cowboys", "packers", "49ers", "niners", "bills",
        "ravens", "steelers", "patriots", "dolphins", "jets", "lions",
        "mahomes", "brady", "kelce", "burrow", "allen", "lamar jackson",
        "interception", "end zone", "wide receiver", "running back",
    ),
    "MLB": (
        "mlb", "baseball", "world series", "yankees", "dodgers", "red sox",
        "mets", "cubs", "braves", "astros", "giants baseball", "ohtani",
        "judge", "home run", "grand slam", "strikeout", "pitcher", "innings",
        "bullpen", "shortstop",
    ),
    "NHL": (
        "nhl", "hockey", "stanley cup", "maple leafs", "canadiens", "bruins",
        "rangers hockey", "oilers", "flames", "penguins", "blackhawks",
        "mcdavid", "crosby", "ovechkin", "power play", "slapshot", "puck",
        "goalie", "hat trick on ice", "blue line",
    ),
    "Tennis": (
        "tennis", "wimbledon", "us open", "roland garros", "french open",
        "australian open", "atp", "wta", "grand slam title", "djokovic",
        "federer", "nadal", "alcaraz", "sinner", "swiatek", "serena",
        "medvedev", "forehand", "backhand", "double fault", "tiebreak",
        "deuce", "baseline rally",
    ),
    "F1": (
        "f1", "formula 1", "formula one", "grand prix", "verstappen",
        "hamilton", "leclerc", "norris", "alonso", "russell", "piastri",
        "ferrari", "mclaren", "red bull racing", "mercedes f1", "pit stop",
        "pole position", "drs", "safety car", "podium finish", "qualifying lap",
    ),
    "Cricket": (
        "cricket", "ipl", "test match", "odi", "t20", "the ashes", "kohli",
        "rohit sharma", "bumrah", "dhoni", "babar", "root", "stokes",
        "wicket", "batsman", "batter out", "bowler", "century partnership",
        "lbw", "six over", "yorker", "spinner", "crease",
    ),
    "Golf": (
        "golf", "the masters", "pga", "ryder cup", "the open championship",
        "augusta", "tiger woods", "rory mcilroy", "scheffler", "birdie",
        "eagle putt", "bogey", "fairway", "the green", "caddie", "tee off",
        "hole in one",
    ),
    "Boxing": (
        "boxing", "heavyweight", "welterweight", "title fight", "tyson fury",
        "canelo", "usyk", "joshua", "mike tyson", "ali", "knockout", " ko ",
        "the ring", "jab", "uppercut", "split decision", "undercard",
    ),
    "Esports": (
        "esports", "e-sports", "league of legends", "lol worlds",
        "counter-strike", "cs2", "csgo", "valorant", "dota", "the international",
        "overwatch", "rocket league", "call of duty league", "fortnite",
        "faker", "s1mple", "zywoo", "t1 ", "g2 esports", "fnatic", "navi",
        "team liquid", "cloud9", "faze", "100 thieves", "pentakill", "clutch round",
        "grand final bo5", "twitch chat",
    ),
    "MMA": (
        "mma", "ufc", "octagon", "mcgregor", "khabib", "jon jones",
        "adesanya", "poirier", "makhachev", "submission", "takedown",
        "chokehold", "armbar", "cage fight", "walkout",
    ),
}


def _plain(text: object) -> str:
    """Lowercase, accent-stripped and padded, so "Mbappé" matches "mbappe"
    and " qb " can anchor on word boundaries."""
    stripped = unicodedata.normalize("NFKD", str(text or ""))
    flat = "".join(c for c in stripped if not unicodedata.combining(c)).lower()
    return f" {re.sub(r'[^a-z0-9]+', ' ', flat).strip()} "


def infer(take: str, prefer: list[str] | None = None) -> str | None:
    """The sport this take is about, or None when nothing points anywhere.

    Scored rather than first-match: a take can mention a city that belongs to
    two leagues, and the sport with more distinct hits wins. A user's followed
    sports break ties, so "the Giants collapsed again" resolves the way that
    particular fan means it.
    """
    text = _plain(take)
    if not text.strip():
        return None
    scores: dict[str, int] = {}
    for sport, markers in MARKERS.items():
        hits = sum(1 for m in markers if _plain(m).strip() in text)
        if hits:
            scores[sport] = hits
    if not scores:
        return None
    followed = [s for s in (prefer or []) if s in SPORTS]
    best = max(scores.values())
    tied = [s for s, n in scores.items() if n == best]
    if len(tied) > 1:
        for sport in followed:                    # the fan's own leagues win
            if sport in tied:
                return sport
    return tied[0]


def resolve(explicit: str | None, take: str, prefer: list[str] | None = None) -> str:
    """The sport to build this video in. Always returns something usable."""
    if explicit in SPORTS:
        return explicit
    guessed = infer(take, prefer)
    if guessed:
        return guessed
    for sport in (prefer or []):
        if sport in SPORTS:
            return sport
    return "Soccer"
