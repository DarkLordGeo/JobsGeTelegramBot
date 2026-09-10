# JobsGeTelegramBot

Posts newly scraped jobs.ge/IT listings to a Telegram channel or group,
grouped by category (Backend, Frontend, DevOps, QA, Data/ML, etc).

Runs entirely on a schedule via GitHub Actions - there's no server, and no
bot process to keep alive. Each run:

1. Checks out the latest `database/jobs_data.json` from
   [DarkLordGeo/scrap_jobs_ge](https://github.com/DarkLordGeo/scrap_jobs_ge)
   (the repo that actually scrapes jobs.ge).
2. Compares it against `seen_jobs.json` to find jobs it hasn't posted yet.
3. Buckets the new jobs by category (see `categorize.py`) and posts one
   message per category to Telegram.
4. Commits the updated `seen_jobs.json` so the next run only reports jobs
   that are genuinely new.

## Setup

### 1. Create the Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`,
   and follow the prompts. You'll get a bot token that looks like
   `123456789:AAExampleTokenGoesHere`.
2. Add the bot to the channel or group you want it posting to, and give it
   permission to post messages.
3. Get the chat id:
   - For a channel: forward any message from the channel to
     [@userinfobot](https://t.me/userinfobot), or use the
     `https://api.telegram.org/bot<TOKEN>/getUpdates` endpoint after posting
     something in the channel - the response includes a `chat.id` (channel
     ids are negative numbers, e.g. `-1001234567890`).
   - For a group: same approach - add the bot, post a message, check
     `getUpdates`.

### 2. Add repo secrets

In this repo's Settings → Secrets and variables → Actions, add:

| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather |
| `TELEGRAM_CHAT_ID` | the channel/group id from step 1.3 |
| `SCRAPER_REPO_TOKEN` | a GitHub [personal access token](https://github.com/settings/tokens) with `repo` scope, since `scrap_jobs_ge` is private and the default `GITHUB_TOKEN` can't read across repos |

### 3. Run it

- It runs automatically every 6 hours (see `.github/workflows/notify.yml`).
- To test immediately: Actions tab → "Notify Telegram of new jobs" →
  "Run workflow".
- To test locally:
  ```bash
  git clone https://github.com/DarkLordGeo/scrap_jobs_ge ../scrap_jobs_ge
  pip install -r requirements.txt
  export TELEGRAM_BOT_TOKEN=...
  export TELEGRAM_CHAT_ID=...
  export JOBS_DATA_PATH=../scrap_jobs_ge/database/jobs_data.json
  python notify.py
  ```

## Tuning categories

`categorize.py` is a plain keyword matcher, not ML - it checks a job's
position title against ordered lists of English and Georgian keywords and
returns the first category that matches. If you notice jobs consistently
landing in "Other / IT", add the keyword that should have caught them to
the relevant category (or add a new category). It's meant to be tuned over
time as you see what jobs.ge's IT category titles actually look like.

## Why a separate repo, and why the cross-repo checkout

This bot is intentionally decoupled from the scraper - it only reads
`database/jobs_data.json`, so it doesn't care how that file gets produced.
The tradeoff is the `SCRAPER_REPO_TOKEN` setup step above, needed because
`scrap_jobs_ge` is private.
