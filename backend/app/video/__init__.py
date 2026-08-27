"""Video generation workflow.

Entry points:
    generate_video(...)  — pure pipeline, no database, returns a Result
    run_clip_job(id)     — drives one Clip row and updates its status

See VIDEO-PIPELINE.md for the design and the measurements behind it.
"""

from .runner import Result, generate_video, run_clip_job

__all__ = ["Result", "generate_video", "run_clip_job"]
