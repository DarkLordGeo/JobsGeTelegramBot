"""Post newly scraped jobs.ge/IT jobs to Telegram, grouped by category.

Reads job data scraped by DarkLordGeo/scrap_jobs_ge (this repo doesn't do
any scraping itself - see .github/workflows/notify.yml for how the data
gets checked out). Tracks which job_ids have already been posted in
seen_jobs.json so re-runs only notify about genuinely new listings.

Required environment variables:
    TELEGRAM_BOT_TOKEN  - from @BotFather
    TELEGRAM_CHAT_ID    - the channel/group/user id to post to

Optional:
    JOBS_DATA_PATH      - path to the scraped jobs_data.json
                          (default: scraper-data/database/jobs_data.json,
                          matching the checkout path used in the workflow)
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

from categorize import group_by_category

REPO_ROOT = Path(__file__).resolve().parent
JOBS_DATA_PATH = Path(
    os.environ.get("JOBS_DATA_PATH", "scraper-data/database/jobs_data.json")
)
SEEN_JOBS_PATH = REPO_ROOT / "seen_jobs.json"

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4096
REQUEST_TIMEOUT = 15


def clean_text(value):
    """Strip the tabs/newlines/<b> tags scraped job fields come wrapped in."""
    if not value:
        return ""
    text = re.sub(r"</?b>", "", value)
    text = re.sub(r"[\t\r\n]+", " ", text)
    return text.strip()


def load_jobs():
    with open(JOBS_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_seen_ids():
    if not SEEN_JOBS_PATH.exists():
        return set()
    with open(SEEN_JOBS_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_seen_ids(job_ids):
    with open(SEEN_JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(job_ids), f, ensure_ascii=False, indent=2)


def format_job_line(job):
    position = clean_text(job.get("position"))
    company = clean_text(job.get("company"))
    date = job.get("date") or []
    expiry = clean_text(date[1]) if len(date) > 1 else ""
    link = job.get("job_link", "")

    line = f"• <b>{position or 'Untitled position'}</b>"
    if company:
        line += f" — {company}"
    if expiry:
        line += f" (until {expiry})"
    if link:
        line += f'\n  <a href="{link}">Apply</a>'
    return line


def chunk_message(header, lines, max_length=MAX_MESSAGE_LENGTH):
    """Yield one or more messages, each under Telegram's length limit."""
    current = header
    for line in lines:
        candidate = current + "\n\n" + line
        if len(candidate) > max_length:
            yield current
            current = header + " (cont'd)\n\n" + line
        else:
            current = candidate
    yield current


def send_telegram_message(token, chat_id, text):
    response = requests.post(
        TELEGRAM_API.format(token=token),
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if not response.ok:
        print(f"Telegram API error {response.status_code}: {response.text}")
    response.raise_for_status()


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set.")
        sys.exit(1)

    if not JOBS_DATA_PATH.exists():
        print(f"No job data found at {JOBS_DATA_PATH}.")
        sys.exit(1)

    jobs = load_jobs()
    seen_ids = load_seen_ids()

    new_jobs = [job for job in jobs if job.get("job_id") not in seen_ids]
    print(f"{len(jobs)} total jobs, {len(new_jobs)} new since last run.")

    if not new_jobs:
        print("Nothing new to post.")
        return

    grouped = group_by_category(new_jobs)

    for category, category_jobs in grouped.items():
        header = f"🆕 <b>{category}</b> ({len(category_jobs)} new)"
        lines = [format_job_line(job) for job in category_jobs]
        for message in chunk_message(header, lines):
            send_telegram_message(token, chat_id, message)
            time.sleep(1)  # stay well under Telegram's rate limits

    all_ids = seen_ids | {job["job_id"] for job in jobs if job.get("job_id")}
    save_seen_ids(all_ids)
    print(f"Posted {len(new_jobs)} new jobs across {len(grouped)} categories.")


if __name__ == "__main__":
    main()
