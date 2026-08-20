"""Build catalog reference stills — `python -m app.video.catalog_build`.

Generates the AI reference images described in VIDEO-GENERATION-PLAN.md §5.6:
one face close-up and one full-body still per character, in neutral studio
conditions, wearing exactly the plain no-lettering kit used in production.

Deliberate rules:

- Uses `providers.image_provider()` — the SAME provider and IMAGE_MODEL that
  renders scene keyframes. References and keyframes must share one visual
  dialect; building references with a different model would defeat them.
- Spending is explicit. The command prints the still count and estimated cost
  and refuses to run without `--yes`. With the stub provider it generates free
  placeholder gradients, which is only useful for testing the wiring.
- `characters.json` is rewritten in place with the new `reference_images`
  paths, so the runtime lookup (`catalog.select_references`) finds them on the
  next job with no further steps.

Usage:
    python -m app.video.catalog_build                # list who is missing refs
    python -m app.video.catalog_build ronaldo --yes  # build one character
    python -m app.video.catalog_build --all --yes    # build everyone missing
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid

from . import catalog, prompts, providers

EST_COST_PER_STILL = 0.05  # measured for x-ai/grok-imagine-image-quality


def build_character(char: catalog.Character, images,
                    notes: str = "") -> tuple[list[str], float]:
    """Generate the reference views for one character. Returns (paths, cost).

    `notes` is admin direction folded into the prompt ("2005 Barcelona era,
    long curly hair, gold boots"). Filenames are unique per batch so history
    accumulates instead of overwriting."""
    catalog.REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    batch = uuid.uuid4().hex[:6]
    written, spent = [], 0.0
    for view, framing in prompts.REFERENCE_VIEWS.items():
        prompt = prompts.REFERENCE_STILL_PROMPT.format(
            name=char.name,
            look=char.look or f"a professional {char.sport} figure",
            wardrobe=char.default_wardrobe or "an authentic team kit with the real "
                                              "crest, name and number in crisp legible lettering",
            framing=framing,
        )
        if notes.strip():
            prompt += f" Specific direction, follow exactly: {notes.strip()}."
        out = catalog.REFERENCES_DIR / f"{char.id}_{view}_{batch}.jpg"
        path, cost = images.generate(prompt, out)
        spent += cost
        if path:
            written.append(f"references/{out.name}")
            print(f"  {char.id}: {view} -> {out.name} (${cost:.3f})")
        else:
            print(f"  {char.id}: {view} FAILED")
    return written, spent


def update_characters_json(char_id: str, reference_paths: list[str]) -> None:
    """Point the catalog entry at its new stills.

    Curated characters get the curated file updated (committed to git);
    anyone else lives in the DB layer, where `set_reference_images` also
    uploads the stills to Supabase Storage for durability."""
    path = catalog.CATALOG_DIR / "characters.json"
    data = json.loads(path.read_text())
    hit = False
    for entry in data.get("characters", []):
        if entry.get("id") == char_id:
            entry["reference_images"] = reference_paths
            hit = True
    if hit:
        path.write_text(json.dumps(data, indent=2) + "\n")
        catalog.reload()
    else:
        catalog.set_reference_images(char_id, reference_paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate catalog reference stills")
    parser.add_argument("character", nargs="?", help="character id to build")
    parser.add_argument("--all", action="store_true", help="build every character missing refs")
    parser.add_argument("--force", action="store_true", help="rebuild even if refs exist")
    parser.add_argument("--yes", action="store_true", help="confirm the spend")
    args = parser.parse_args(argv)

    chars = catalog.characters()
    if args.character:
        if args.character not in chars:
            print(f"unknown character {args.character!r}. Known: {', '.join(sorted(chars))}")
            return 1
        targets = [chars[args.character]]
    elif args.all:
        targets = [c for c in chars.values() if args.force or not c.reference_paths()]
    else:
        # No selection: report state and exit without spending anything.
        for c in sorted(chars.values(), key=lambda c: (c.sport, c.id)):
            state = f"{len(c.reference_paths())} refs" if c.reference_paths() else "MISSING"
            print(f"  {c.sport:<7} {c.id:<14} {state}")
        print("\nRun with a character id or --all, plus --yes, to generate.")
        return 0

    if not args.force:
        targets = [c for c in targets if not c.reference_paths()] or targets

    stills = len(targets) * len(prompts.REFERENCE_VIEWS)
    images = providers.image_provider()
    real = not isinstance(images, providers.StubImageProvider)
    est = stills * EST_COST_PER_STILL if real else 0.0
    print(f"{len(targets)} character(s), {stills} stills, estimated ${est:.2f} "
          f"({'REAL generation' if real else 'stub placeholders — set IMAGE_PROVIDER=openrouter for real'})")
    if not args.yes:
        print("Add --yes to proceed.")
        return 1

    total = 0.0
    for char in targets:
        paths, cost = build_character(char, images)
        total += cost
        if paths:
            update_characters_json(char.id, paths)
    print(f"done. spent ${total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
