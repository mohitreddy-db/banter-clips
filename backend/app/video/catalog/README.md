# Character & team catalog

The data behind real-player likenesses and team identity
(VIDEO-GENERATION-PLAN.md §5). Loaded by `../catalog.py`; a missing or corrupt
file degrades to an empty catalog — it can never fail a job.

```
catalog/
├── characters.json   # who can appear: look, wardrobe, voice, aliases, teams
├── teams.json        # colour palettes, jersey text, venues, rosters
└── references/       # AI-generated identity stills (may be empty)
```

## How it is used at runtime

1. Focus detection scans the take for character/team names and aliases.
2. The planner gets the roster with the focused players first, and the
   focused team's palette + venues as context.
3. Cast members belonging to a focused team are re-dressed in that team's
   `jersey_description`.
4. At keyframe time, `catalog.select_references` picks up to two stills for
   the speaker (face ref for close-ups, full-body otherwise) and attaches
   them as identity anchors. No stills → pure text description, which still
   works for famous faces.

## Managing the catalog

| Task | How |
|---|---|
| Add a player | Write the JSON entry (look description does the heavy lifting — build, height, hair, face, distinctive features), link `teams`, then `python -m app.video.catalog_build <id> --yes` to generate stills |
| Add a team | Add colours, a `jersey_description` ending in `no logos, no numbers, no lettering`, 2–3 venues, `associated_players` |
| Retire someone | Set `"active": false` — never delete, ids may appear in old plans |
| Update stills | `catalog_build <id> --force --yes`, only when the image model improves meaningfully |
| Keep it small | Quality over quantity: ~8–12 strong characters per sport. Every entry should have been seen in a render. |

## Non-negotiable rules

- **Wardrobes never carry lettering.** Every jersey/wardrobe string ends with
  `no logos, no numbers, no lettering`. Image models garble requested text
  (measured: 3 of 4 scenes had text defects when text was allowed).
- **Team identity is colours + players + venues** — never official logos,
  crests, or wordmarks. Dialogue and burned-in captions may name anyone
  freely; only the *visuals* stay text-free.
- **References are AI-generated, never real photos** — legal simplicity,
  wardrobe control, and visual consistency with the keyframes.
- **References use the production image model.** `catalog_build` goes through
  `providers.image_provider()` — the same `IMAGE_MODEL` that renders scene
  keyframes. Do not generate references with a different tool.
