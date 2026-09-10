"""Post newly scraped jobs to Telegram, grouped by category.

Lives alongside the scraper it reads from - no cross-repo checkout, no
separate token. Run after database/jobs_data.json is updated (see
.github/workflows/telegram_notify.yml). Tracks which job_ids have already
been posted in seen_jobs.json so re-runs only notify about genuinely new
listings, not the whole dataset every time.

Also sends personalized per-category messages to anyone who's set
preferences via the webhook bot (webhook_bot/app.py) - preferences live in
Upstash Redis (a "subscribers" hash), which that service maintains.

Required environment variables:
    TELEGRAM_BOT_TOKEN  - from @BotFather
    TELEGRAM_CHAT_ID    - the channel/group/user id to post to

Optional:
    FORCE_SEND                - if "true", sends every job in
                                database/jobs_data.json regardless of
                                seen_jobs.json (used for manual test runs -
                                see .github/workflows/telegram_notify.yml,
                                which sets this automatically on
                                workflow_dispatch)
    UPSTASH_REDIS_REST_URL    - if unset, personalized delivery is skipped
    UPSTASH_REDIS_REST_TOKEN  - (the channel broadcast still happens)
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

from categorize import categorize, group_by_category

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_DATA_PATH = REPO_ROOT / "database" / "jobs_data.json"
SEEN_JOBS_PATH = Path(__file__).resolve().parent / "seen_jobs.json"
SUBSCRIBERS_KEY = "subscribers"  # Redis hash: chat_id -> JSON {"categories": [...]}

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


def load_subscribers():
    """Return {chat_id: {"categories": [...]}} from Redis, or {} if Upstash
    isn't configured (personalized delivery is optional - the channel
    broadcast works regardless)."""
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return {}

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=["HGETALL", SUBSCRIBERS_KEY],
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    flat = response.json()["result"] or []  # [field1, value1, field2, value2, ...]

    subscribers = {}
    for i in range(0, len(flat) - 1, 2):
        chat_id, raw_value = flat[i], flat[i + 1]
        try:
            subscribers[chat_id] = json.loads(raw_value)
        except json.JSONDecodeError:
            print(f"Skipping malformed subscriber entry for {chat_id}")
    return subscribers


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


def send_grouped(token, destination_chat_id, grouped):
    """Send one message per category to a single destination. Isolated per
    destination by the caller - a failure here (e.g. a subscriber blocked
    the bot) shouldn't take down delivery to everyone else."""
    for category, category_jobs in grouped.items():
        header = f"🆕 <b>{category}</b> ({len(category_jobs)})"
        lines = [format_job_line(job) for job in category_jobs]
        for message in chunk_message(header, lines):
            send_telegram_message(token, destination_chat_id, message)
            time.sleep(1)  # stay well under Telegram's rate limits


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set.")
        sys.exit(1)

    jobs = load_jobs()
    seen_ids = load_seen_ids()
    force_send = os.environ.get("FORCE_SEND", "false").lower() == "true"

    if force_send:
        jobs_to_send = jobs
        print(f"{len(jobs)} total jobs. FORCE_SEND is on - sending all of them.")
    else:
        jobs_to_send = [job for job in jobs if job.get("job_id") not in seen_ids]
        print(f"{len(jobs)} total jobs, {len(jobs_to_send)} new since last run.")

    if not jobs_to_send:
        print("Nothing new to post.")
        return

    grouped = group_by_category(jobs_to_send)

    try:
        send_grouped(token, chat_id, grouped)
    except requests.exceptions.HTTPError as exc:
        print(f"Failed to post to the main channel/chat: {exc}")

    subscribers = load_subscribers()
    jobs_by_category = [(categorize(job.get("position", "")), job) for job in jobs_to_send]
    sent_to = 0
    for subscriber_id, prefs in subscribers.items():
        wanted = set(prefs.get("categories", []))
        subscriber_grouped = {}
        for category, job in jobs_by_category:
            if category in wanted:
                subscriber_grouped.setdefault(category, []).append(job)
        if not subscriber_grouped:
            continue
        try:
            send_grouped(token, subscriber_id, subscriber_grouped)
            sent_to += 1
        except requests.exceptions.HTTPError as exc:
            # A blocked bot, a deleted account, etc. shouldn't stop delivery
            # to everyone else.
            print(f"Failed to notify subscriber {subscriber_id}: {exc}")

    all_ids = seen_ids | {job["job_id"] for job in jobs if job.get("job_id")}
    save_seen_ids(all_ids)
    print(
        f"Posted {len(jobs_to_send)} jobs across {len(grouped)} categories "
        f"to the main destination, and to {sent_to}/{len(subscribers)} subscribers."
    )


if __name__ == "__main__":
    main()
