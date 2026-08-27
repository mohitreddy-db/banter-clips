"""Focus detection — what is this take actually about? (plan §7.1)

Classifies a take as player / team / matchup / generic by scanning it for
catalog names and aliases. Deterministic, free, and never fails: a take that
mentions nothing recognisable is simply "generic".

The result drives team identity downstream: which players the planner should
prefer, which colour palette the jerseys use, which venues the scenes reuse.
A player-focused take inherits the player's own team as context, so "Wemby is
overrated" still renders in black and silver.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog


@dataclass
class Focus:
    kind: str = "generic"  # "player" | "team" | "matchup" | "generic"
    player_ids: list[str] = field(default_factory=list)
    team_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "players": self.player_ids, "teams": self.team_ids}

    @property
    def primary_team(self) -> catalog.Team | None:
        for team_id in self.team_ids:
            team = catalog.get_team(team_id)
            if team:
                return team
        return None


def detect(take: str, sport: str) -> Focus:
    """Never raises, never returns None."""
    try:
        chars, teams = catalog.find_mentions(take, sport)
    except Exception:  # noqa: BLE001 — a broken catalog means a generic take
        return Focus()

    player_ids = [c.id for c in chars]
    team_ids = [t.id for t in teams]

    # A named player drags their own team in as context (palette + venues),
    # unless the take already names teams explicitly.
    if chars and not team_ids:
        for char in chars:
            for team_id in char.teams:
                if team_id not in team_ids and catalog.get_team(team_id):
                    team_ids.append(team_id)
                    break  # one team per player is enough context

    if len(teams) >= 2:
        kind = "matchup"
    elif player_ids:
        kind = "player"
    elif team_ids:
        kind = "team"
    else:
        kind = "generic"
    return Focus(kind=kind, player_ids=player_ids, team_ids=team_ids)
