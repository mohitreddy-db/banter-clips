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

from . import defaults, enhancer, planner, prompts, providers
from .runner import generate_video


def _ask_questions(brief, interactive: bool) -> dict:
    """Put the enhancer's questions to the user. Enter accepts the default."""
    if not brief.questions:
        return {}
    print("\n  A few things would improve the result:\n")
    answers: dict = {}
    for question in brief.questions:
        print(f"  {question.prompt}")
        print(f"    why: {question.why}")
        for index, option in enumerate(question.options, 1):
            mark = "*" if option.value == question.default else " "
            detail = f" — {option.detail}" if option.detail else ""
            print(f"   {mark}{index}. {option.label}{detail}")
        if not interactive:
            print(f"    [using default: {question.default or 'as written'}]\n")
            continue
        try:
            reply = input(f"    > [{question.default or 'skip'}] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not reply:
            print()
            continue
        if question.options and reply.isdigit() and 1 <= int(reply) <= len(question.options):
            answers[question.id] = question.options[int(reply) - 1].value
        else:
            answers[question.id] = reply
        print()
    return answers


def _print_brief(brief) -> None:
    print(f"\n  take    {brief.take}")
    if brief.original_take and brief.original_take != brief.take:
        print(f"  was     {brief.original_take}")
    print(f"  setup   {brief.sport} · {brief.tone} · {brief.seconds}s · "
          f"{enhancer.STYLE_PRESETS[brief.style_id]['label']}")
    if brief.cast_ids or brief.team_ids:
        print(f"  subject {', '.join(brief.cast_ids + brief.team_ids)}")
    if brief.unknown_names:
        print(f"  unknown {', '.join(brief.unknown_names)}  (no reference stills)")


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
    parser.add_argument("--brief-only", action="store_true",
                        help="enhance the take, show the questions, and stop")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="answer the enhancer's questions at the prompt")
    parser.add_argument("--answers", default=None,
                        help='pre-supplied answers as JSON, e.g. \'{"style":"gritty"}\'')
    parser.add_argument("--raw", action="store_true",
                        help="skip enhancement entirely and use the take as written")
    parser.add_argument("--full-prompts", action="store_true",
                        help="print prompts untruncated")
    parser.add_argument("--no-watermark", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        preset = json.loads(args.answers) if args.answers else {}
    except json.JSONDecodeError:
        print("could not parse --answers as JSON; ignoring")
        preset = {}

    brief = None
    if not args.raw:
        brief = enhancer.enhance(
            args.take, args.sport, args.tone, args.seconds,
            answers=preset, client=providers.text_client(),
        )
        _print_brief(brief)
        replies = _ask_questions(brief, args.interactive)
        if replies:
            brief = enhancer.apply_answers(brief, {**preset, **replies})
            _print_brief(brief)
        resolved = enhancer.resolved_from(brief)
    else:
        resolved = defaults.resolve(args.take, args.sport, args.tone, args.seconds)

    if args.brief_only:
        print(f"\n{json.dumps(brief.to_dict() if brief else resolved.to_dict(), indent=2)}")
        return 0

    print(f"\nresolved input: {json.dumps(resolved.to_dict())}")

    if args.plan_only:
        plan = planner.build_plan(resolved, providers.text_client())
        if brief and brief.style:
            plan.style = brief.style
        _print_plan(plan)
        cut = None if args.full_prompts else 600
        print("image prompt for scene 1:\n")
        print("  " + prompts.build_image_prompt(plan, plan.scenes[0])[:cut] + "\n")
        print("motion prompt for scene 1:\n")
        print("  " + prompts.build_motion_prompt(plan, plan.scenes[0])[:cut] + "\n")
        return 0

    work = Path(args.work) if args.work else Path(tempfile.mkdtemp(prefix="banter_"))
    out = Path(args.out) if args.out else work / "out.mp4"

    result = generate_video(
        args.take, args.sport, args.tone, args.seconds,
        work_dir=work, out_path=out,
        watermark=None if args.no_watermark else "BanterClips",
        on_stage=lambda name: print(f"  → {name}"),
        brief=brief,
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
