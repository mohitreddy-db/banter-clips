"""Live progress lines for an in-flight clip.

The 7 coarse stages tell a user *which* phase is running; these tell them what
is actually happening inside it ("scene 2/4: keyframe attempt 1/3 for Messi",
"scene 1: animated in 74s"). The two expensive stages take minutes, so without
this the UI sits on one unchanging row for most of the job.

Deliberately in memory, not in Postgres: these are ephemeral, high-frequency,
worthless once the clip is done, and a column would need a migration. The
trade-off is that they vanish on restart and do not survive multiple worker
processes — acceptable, because they are a nicety and `clip.status` remains
the source of truth for job state.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict, deque

# Enough history for the longest job (12 scenes x ~6 lines), far below memory
# concern. Older clips are evicted whole once this many have been tracked.
MAX_LINES = 200
MAX_CLIPS = 50

_lock = threading.Lock()
_logs: "OrderedDict[str, deque]" = OrderedDict()


def start(clip_id: uuid.UUID | str) -> None:
    """Begin (or restart) the log for a clip."""
    key = str(clip_id)
    with _lock:
        _logs[key] = deque(maxlen=MAX_LINES)
        _logs.move_to_end(key)
        while len(_logs) > MAX_CLIPS:
            _logs.popitem(last=False)


def push(clip_id: uuid.UUID | str, text: str, kind: str = "step") -> None:
    """Record one line. Never raises — progress must not break generation."""
    key = str(clip_id)
    try:
        with _lock:
            log = _logs.get(key)
            if log is None:
                log = _logs[key] = deque(maxlen=MAX_LINES)
            log.append({"at": round(time.time(), 3), "text": str(text)[:300], "kind": kind})
    except Exception:  # noqa: BLE001 — a reporting failure is never fatal
        pass


def get(clip_id: uuid.UUID | str) -> list[dict]:
    with _lock:
        return list(_logs.get(str(clip_id), ()))


def clear(clip_id: uuid.UUID | str) -> None:
    with _lock:
        _logs.pop(str(clip_id), None)
