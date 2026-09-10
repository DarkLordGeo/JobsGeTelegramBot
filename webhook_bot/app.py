"""Telegram webhook handler for per-user category preferences.

Separate from telegram_bot/notify.py: that script runs on a GitHub Actions
schedule and only ever pushes messages outward. This is the interactive
half - an always-on service that receives Telegram updates (a user
messaging the bot, or tapping an inline-keyboard button) and lets them
choose which job categories they want to be DMed about.

Preferences are stored in Upstash Redis (a "subscribers" hash: field is a
chat_id, value is a JSON blob like {"categories": [...]}) rather than on
local disk - Render's free tier disk is ephemeral, wiped on every
restart/redeploy. Each user's entry is an independent hash field, so
concurrent updates from different users never conflict with each other,
and a single HSET is fast enough to just do synchronously in the request -
no caching or background writes needed.

Required environment variables:
    TELEGRAM_BOT_TOKEN        - from @BotFather
    UPSTASH_REDIS_REST_URL    - from the Upstash console
    UPSTASH_REDIS_REST_TOKEN  - from the Upstash console
Optional:
    TELEGRAM_WEBHOOK_SECRET - if set, incoming requests must carry a
                              matching X-Telegram-Bot-Api-Secret-Token
                              header (set the same value when registering
                              the webhook with Telegram)
"""

import json
import os
import sys

import requests
from flask import Flask, request, abort

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "telegram_bot"))
from categorize import CATEGORIES, OTHER_CATEGORY  # noqa: E402

ALL_CATEGORIES = [name for name, _keywords in CATEGORIES] + [OTHER_CATEGORY]

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
UPSTASH_URL = os.environ["UPSTASH_REDIS_REST_URL"]
UPSTASH_TOKEN = os.environ["UPSTASH_REDIS_REST_TOKEN"]
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

SUBSCRIBERS_KEY = "subscribers"  # Redis hash: chat_id -> JSON {"categories": [...]}
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
REQUEST_TIMEOUT = 15

app = Flask(__name__)


# ------------------------------------------------------------------ Redis --

def redis_command(*args):
    response = requests.post(
        UPSTASH_URL,
        headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
        json=list(args),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["result"]


def get_categories(chat_id):
    """Return the set of categories this chat_id is subscribed to (empty
    if they've never interacted with the bot)."""
    raw = redis_command("HGET", SUBSCRIBERS_KEY, str(chat_id))
    if not raw:
        return set()
    return set(json.loads(raw).get("categories", []))


def set_categories(chat_id, categories):
    redis_command(
        "HSET",
        SUBSCRIBERS_KEY,
        str(chat_id),
        json.dumps({"categories": sorted(categories)}, ensure_ascii=False),
    )


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
    # Deep links (t.me/<bot>?start=xyz) send "/start xyz", not bare "/start" -
    # match on the command itself, ignore any payload after it.
    command = text.split()[0] if text else ""

    if command in ("/start", "/preferences"):
        # Nothing selected until the user opts in. This also doubles as
        # "register this chat_id as a known subscriber" even before they've
        # picked anything, by writing the (empty) entry if none exists yet.
        selected = get_categories(chat_id)
        if not selected:
            set_categories(chat_id, [])

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

    selected = get_categories(chat_id)
    if category in selected:
        selected.discard(category)
        note = f"Turned off: {category}"
    else:
        selected.add(category)
        note = f"Turned on: {category}"

    set_categories(chat_id, selected)

    answer_callback_query(callback_id, text=note)
    edit_message_markup(chat_id, message_id, build_keyboard(selected))


@app.route("/", methods=["GET"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
