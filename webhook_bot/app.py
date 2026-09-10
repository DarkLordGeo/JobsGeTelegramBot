"""Telegram webhook handler for per-user category preferences.

Separate from telegram_bot/notify.py: that script runs on a GitHub Actions
schedule and only ever pushes messages outward. This is the interactive
half - an always-on service that receives Telegram updates (a user
messaging the bot, or tapping an inline-keyboard button) and lets them
choose which job categories they want to be DMed about.

Preferences are stored in telegram_bot/subscribers.json, committed back to
this repo via the GitHub Contents API (Render's free tier disk is
ephemeral - anything written locally is lost on restart/redeploy, so state
has to live somewhere durable). notify.py reads that same file on its next
scheduled run to know who wants what.

Required environment variables:
    TELEGRAM_BOT_TOKEN   - from @BotFather
    GITHUB_TOKEN         - fine-grained PAT, Contents: Read & write, scoped
                           to this repo
    GITHUB_REPO          - "owner/repo", e.g. "DarkLordGeo/JobsGeTelegramBot"
Optional:
    TELEGRAM_WEBHOOK_SECRET - if set, incoming requests must carry a
                              matching X-Telegram-Bot-Api-Secret-Token
                              header (set the same value when registering
                              the webhook with Telegram)
"""

import base64
import json
import os
import sys
import threading

import requests
from flask import Flask, request, abort

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "telegram_bot"))
from categorize import CATEGORIES, OTHER_CATEGORY  # noqa: E402

ALL_CATEGORIES = [name for name, _keywords in CATEGORIES] + [OTHER_CATEGORY]

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = os.environ["GITHUB_REPO"]
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

SUBSCRIBERS_PATH = "telegram_bot/subscribers.json"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SUBSCRIBERS_PATH}"
REQUEST_TIMEOUT = 15

app = Flask(__name__)


# ---------------------------------------------------------------- storage --
#
# Every button tap used to do a synchronous GitHub read + GitHub write + two
# Telegram calls before responding - each GitHub Contents API round trip is
# a real git commit under the hood, so that added up to a very sluggish
# button. Fix: keep the subscribers dict cached in memory (this process
# runs as a single gunicorn worker, so a plain dict + lock is safe - no
# cross-process inconsistency to worry about), answer Telegram immediately
# from the in-memory state, and commit to GitHub afterward in a background
# thread. A crash between updating the cache and the background commit
# finishing could lose that one toggle, which is an acceptable tradeoff for
# a personal preferences bot.

_cache_lock = threading.Lock()
_subscribers_cache = None
_subscribers_sha = None


def _fetch_subscribers():
    """Return (data, sha) straight from GitHub. sha is None if the file
    doesn't exist yet."""
    response = requests.get(
        GITHUB_API,
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 404:
        return {}, None
    response.raise_for_status()
    payload = response.json()
    content = base64.b64decode(payload["content"]).decode("utf-8")
    return json.loads(content), payload["sha"]


def _put_subscribers(data, sha):
    """Commit the given subscribers dict. Retries once on a sha conflict
    (another request updated the file in between our read and write).
    Returns the new sha."""
    body = {
        "message": "Update subscriber preferences",
        "content": base64.b64encode(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8"),
    }
    if sha:
        body["sha"] = sha

    response = requests.put(
        GITHUB_API,
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}"},
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 409:
        _, fresh_sha = _fetch_subscribers()
        body["sha"] = fresh_sha
        response = requests.put(
            GITHUB_API,
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}"},
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
    response.raise_for_status()
    return response.json()["content"]["sha"]


def get_subscribers():
    """Return the live in-memory subscribers dict, loading it from GitHub
    once per process lifetime. Callers mutate the returned dict in place,
    then call queue_persist() to save it."""
    global _subscribers_cache, _subscribers_sha
    with _cache_lock:
        if _subscribers_cache is None:
            _subscribers_cache, _subscribers_sha = _fetch_subscribers()
        return _subscribers_cache


def queue_persist():
    """Commit the current in-memory subscribers dict to GitHub in the
    background, so the caller doesn't block on GitHub's round trip."""

    def _run():
        global _subscribers_sha
        with _cache_lock:
            snapshot = json.loads(json.dumps(_subscribers_cache))
            sha = _subscribers_sha
        try:
            new_sha = _put_subscribers(snapshot, sha)
            with _cache_lock:
                _subscribers_sha = new_sha
        except Exception as exc:  # noqa: BLE001 - log and move on, never crash a background thread
            print(f"Failed to persist subscribers.json: {exc}")

    threading.Thread(target=_run, daemon=True).start()


# --------------------------------------------------------------- Telegram --

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=REQUEST_TIMEOUT)


def edit_message_markup(chat_id, message_id, reply_markup):
    requests.post(
        f"{TELEGRAM_API}/editMessageReplyMarkup",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": reply_markup,
        },
        timeout=REQUEST_TIMEOUT,
    )


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    requests.post(
        f"{TELEGRAM_API}/answerCallbackQuery", json=payload, timeout=REQUEST_TIMEOUT
    )


def build_keyboard(selected_categories):
    buttons = []
    for name in ALL_CATEGORIES:
        checked = "✅" if name in selected_categories else "⬜"
        buttons.append(
            [{"text": f"{checked} {name}", "callback_data": f"t:{name}"}]
        )
    return {"inline_keyboard": buttons}


# ------------------------------------------------------------------ routes --

@app.route("/webhook", methods=["POST"])
def webhook():
    if WEBHOOK_SECRET:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header != WEBHOOK_SECRET:
            abort(403)

    update = request.get_json(silent=True) or {}

    if "message" in update:
        handle_message(update["message"])
    elif "callback_query" in update:
        handle_callback(update["callback_query"])

    return "", 200


def handle_message(message):
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text in ("/start", "/preferences"):
        data = get_subscribers()
        key = str(chat_id)
        entry = data.get(key)
        if entry:
            selected = set(entry["categories"])
        else:
            # First-time user: nothing selected until they opt in. Persist
            # the (empty) entry immediately anyway, so they're recorded as
            # a known subscriber the moment they interact with the bot.
            selected = set()
            data[key] = {"categories": []}
            queue_persist()

        send_message(
            chat_id,
            "Tap a category to turn it on. You'll only be notified about the ones you select:",
            reply_markup=build_keyboard(selected),
        )
    else:
        send_message(chat_id, "Send /preferences to choose which job categories you get notified about.")


def handle_callback(callback_query):
    callback_id = callback_query["id"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    data_str = callback_query.get("data", "")

    if not data_str.startswith("t:"):
        answer_callback_query(callback_id)
        return

    category = data_str[len("t:"):]
    if category not in ALL_CATEGORIES:
        answer_callback_query(callback_id)
        return

    data = get_subscribers()
    key = str(chat_id)
    entry = data.get(key)
    selected = set(entry["categories"]) if entry else set()

    if category in selected:
        selected.discard(category)
        note = f"Turned off: {category}"
    else:
        selected.add(category)
        note = f"Turned on: {category}"

    data[key] = {"categories": sorted(selected)}

    # Answer Telegram immediately from the in-memory state - the button
    # should feel instant regardless of GitHub's round trip.
    answer_callback_query(callback_id, text=note)
    edit_message_markup(chat_id, message_id, build_keyboard(selected))

    queue_persist()


@app.route("/", methods=["GET"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
