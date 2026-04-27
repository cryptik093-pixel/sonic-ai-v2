from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import redis

from analyzer.process import process_audio_file

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JOB_QUEUE = os.getenv("SONIC_JOB_QUEUE", "sonic:jobs")
RESULT_PREFIX = os.getenv("SONIC_RESULT_PREFIX", "sonic:result:")
POLL_SECONDS = float(os.getenv("SONIC_POLL_SECONDS", "3"))


def handle_job(job: Dict[str, Any]) -> Dict[str, Any]:
    result = process_audio_file(
        file_path=job["file_path"],
        processing_mode=job.get("processing_mode", "none"),
    )

    return {
        "job_id": job.get("job_id"),
        "status": "completed",
        "result": {
            "bpm": result["bpm"],
            "key": result["key"],
            "analysis": result["analysis"]["summary"],
            "peaks": result["peaks"],
            "loudness": result["loudness"],
            "details": result["analysis"],
        },
    }


def run_worker() -> None:
    """Minimal Redis queue consumer loop."""
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    while True:
        message = client.brpop(JOB_QUEUE, timeout=int(POLL_SECONDS))
        if message is None:
            time.sleep(POLL_SECONDS)
            continue

        _, raw_job = message

        try:
            job = json.loads(raw_job)
            response = handle_job(job)
        except Exception as exc:  # pragma: no cover
            job_id = None
            try:
                job_id = json.loads(raw_job).get("job_id")
            except Exception:
                pass

            response = {
                "job_id": job_id,
                "status": "failed",
                "error": str(exc),
            }

        result_key = f"{RESULT_PREFIX}{response.get('job_id', 'unknown')}"
        client.set(result_key, json.dumps(response))


if __name__ == "__main__":
    run_worker()
