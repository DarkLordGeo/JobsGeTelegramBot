"""Mirror database/jobs_data.json into Upstash Redis.

Additive, not a replacement: the scrape -> git commit -> notify workflow
chain keeps working exactly as it does today regardless of this script.
This just also makes the current scrape available in Redis under a single
key, for any future consumer that doesn't want to check out the whole
repo just to read the job list (or that also lives in Redis already, like
subscriber preferences).

If UPSTASH_REDIS_REST_URL/TOKEN aren't set, this is a no-op - the git-based
flow doesn't depend on it.
"""

import json
import os
import sys
from pathlib import Path

import requests

JOBS_DATA_PATH = Path(__file__).resolve().parent.parent / "database" / "jobs_data.json"
JOBS_DATA_KEY = "jobs_data"
REQUEST_TIMEOUT = 15


def main():
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        print("UPSTASH_REDIS_REST_URL/TOKEN not set - skipping Redis sync.")
        return

    with open(JOBS_DATA_PATH, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=["SET", JOBS_DATA_KEY, json.dumps(jobs, ensure_ascii=False)],
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("result") != "OK":
        print(f"Unexpected response syncing to Redis: {result}")
        sys.exit(1)

    print(f"Synced {len(jobs)} jobs to Redis under key '{JOBS_DATA_KEY}'.")


if __name__ == "__main__":
    main()
