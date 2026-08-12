"""Run the pipeline from the command line, without the API or a database.

    cd backend
    .venv/bin/python -m app.video.cli "Wemby still can't find Brunson"
    .venv/bin/python -m app.video.cli "" --seconds 30          # missing take is fine
    .venv/bin/python -m app.video.cli "take" --plan-only       # show the script only

Every argument is optional. With none of them it still produces a video.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from pathlib import Path

from . import defaults, planner, prompts, providers
from .runner import generate_video


def _print_plan(plan) -> None:
    print(f"\n  title   {plan.title}")
    print(f"  source  {plan.source}   sport {plan.sport}   tone {plan.tone}")
    print(f"  cast    {', '.join(f'{m.name} [{m.id}]' for m in plan.cast)}")
    print(f"  length  {plan.total_seconds:.1f}s across {len(plan.scenes)} scenes\n")
    for scene in plan.scenes:
        speaker = plan.speaker_for(scene)
        who = speaker.name if speaker else "—"
        print(f"  [{scene.index + 1}] {scene.beat:<10} {scene.seconds:>4.1f}s  @ {scene.venue[:52]}")
        print(f"      action  {scene.action[:96]}")
        print(f"      {who}: \"{scene.line}\"  ({scene.delivery})")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the BanterClips video workflow")
    parser.add_argument("take", nargs="?", default="", help="the opinion (optional)")
    parser.add_argument("--sport", default=None)
    parser.add_argument("--tone", default=None)
    parser.add_argument("--seconds", default=None)
    parser.add_argument("--out", default=None, help="output mp4 path")
    parser.add_argument("--work", default=None, help="working directory to keep")
    parser.add_argument("--plan-only", action="store_true", help="print the script and stop")
    parser.add_argument("--no-watermark", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    resolved = defaults.resolve(args.take, args.sport, args.tone, args.seconds)
    print(f"resolved input: {json.dumps(resolved.to_dict())}")

    if args.plan_only:
        plan = planner.build_plan(resolved, providers.text_client())
        _print_plan(plan)
        print("image prompt for scene 1:\n")
        print("  " + prompts.build_image_prompt(plan, plan.scenes[0])[:600] + "\n")
        print("motion prompt for scene 1:\n")
        print("  " + prompts.build_motion_prompt(plan, plan.scenes[0])[:600] + "\n")
        return 0

    work = Path(args.work) if args.work else Path(tempfile.mkdtemp(prefix="banter_"))
    out = Path(args.out) if args.out else work / "out.mp4"

    result = generate_video(
        args.take, args.sport, args.tone, args.seconds,
        work_dir=work, out_path=out,
        watermark=None if args.no_watermark else "BanterClips",
        on_stage=lambda name: print(f"  → {name}"),
    )

    if result.plan:
        _print_plan(result.plan)
    for warning in result.warnings:
        print(f"  warning: {warning}")
    print(f"\nwork dir: {work}")
    if result.ok:
        print(f"OK  {result.video_path}  {result.duration}s  cost ${result.cost_usd:.3f}")
        return 0
    print(f"FAILED  {result.error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
