"""(Re)post and pin the "choose your categories" instructions in the main
channel/group.

The channel broadcast (telegram_bot/notify.py) sends every new job to
everyone - there's no way to show different members different content in a
Telegram channel. The only way to get a personalized, filtered feed is to
DM the bot directly, so the channel needs a standing, pinned pointer to
that - a message with a button that deep-links straight into the bot's
/start flow.

This is a one-off/on-demand script, not part of the regular scrape/notify
pipeline - run it via the "post channel instructions" GitHub Actions
workflow (workflow_dispatch) whenever the pinned message needs to be
(re)posted, e.g. because it was manually unpinned or the wording changed.

Required environment variables:
    TELEGRAM_BOT_TOKEN  - from @BotFather
    TELEGRAM_CHAT_ID    - the channel/group id to post to
Optional:
    TELEGRAM_BOT_USERNAME - the bot's @username, used to build the deep
                            link (defaults to the aggregator bot's current
                            username)
"""

import os

import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "jobsge_aggregator_bot")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
REQUEST_TIMEOUT = 15

MESSAGE_TEXT = (
    "🔧 Want only specific job categories instead of everything? Tap below to choose."
)


def main():
    send_response = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": MESSAGE_TEXT,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "Choose my categories",
                            "url": f"https://t.me/{BOT_USERNAME}?start=setprefs",
                        }
                    ]
                ]
            },
        },
        timeout=REQUEST_TIMEOUT,
    )
    send_response.raise_for_status()
    message_id = send_response.json()["result"]["message_id"]
    print(f"Posted instructions message {message_id}")

    pin_response = requests.post(
        f"{TELEGRAM_API}/pinChatMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "disable_notification": True,
        },
        timeout=REQUEST_TIMEOUT,
    )
    pin_response.raise_for_status()
    print(f"Pinned message {message_id}")


if __name__ == "__main__":
    main()
