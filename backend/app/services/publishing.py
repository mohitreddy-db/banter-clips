"""Dummy publish worker.

Real publishing waits on the platform OAuth app approval (BR-13). This keeps
the honest status machine (queued → uploading → published | failed), the retry
path, and the caption flow real; only the platform API call is simulated.
"""

import threading
import time
import uuid
from datetime import datetime, timezone

from ..db import SessionLocal
from ..models import Publish

FAIL_MARKER = "[fail]"
UPLOAD_SECONDS = 2.2


def _run_publish(publish_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        pub = db.get(Publish, publish_id)
        if pub is None:
            return
        pub.status = "uploading"
        db.commit()
        time.sleep(UPLOAD_SECONDS)

        # Typing "[fail]" in the caption demos the failed-publish + retry path.
        if FAIL_MARKER in (pub.caption or "").lower():
            pub.status = "failed"
            pub.error = (
                "The platform rejected the upload (simulated). Retrying is free "
                "and never regenerates the video."
            )
            db.commit()
            return

        account = pub.account
        pub.status = "published"
        pub.error = None
        pub.published_at = datetime.now(timezone.utc)
        pub.external_url = (
            f"https://www.instagram.com/reel/BC{str(pub.id)[:8]}/"
            if account and account.platform == "instagram"
            else f"https://example.com/post/{str(pub.id)[:8]}"
        )
        db.commit()
    finally:
        db.close()


def start_publish(publish_id: uuid.UUID) -> None:
    threading.Thread(target=_run_publish, args=(publish_id,), daemon=True).start()
