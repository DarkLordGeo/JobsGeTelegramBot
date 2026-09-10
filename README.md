# JobsGeTelegramBot

Scrapes jobs.ge's IT/Programming category and posts newly found listings to
a Telegram channel or group, grouped by category (Backend, Frontend,
DevOps, QA, Data/ML, etc). Runs entirely on GitHub Actions - no server to
maintain.

This is a standalone pipeline, separate from
[DarkLordGeo/scrap_jobs_ge](https://github.com/DarkLordGeo/scrap_jobs_ge)
(which runs the live jobs.ge website's API) - it does its own scraping and
keeps its own copy of the data.

## How it works

Two workflows, chained by a commit:

1. **`.github/workflows/test.yml`** ("generate links") - runs daily (plus
   on push/PR and manual dispatch). Generates the list of listing pages
   (`scheduled_scripts/link_generator.py`), crawls them with Scrapy
   (`jobs_ge/`), writes the result to `database/jobs_data.json`, then runs
   `scheduled_scripts/data_analysis.py` to update `database/top_jobs.json`
   and `database/daily_analytics.ndjson`. Commits and pushes the updated
   files.
2. **`.github/workflows/telegram_notify.yml`** - triggers automatically
   whenever that push updates `database/jobs_data.json` (also runs every 6
   hours and on manual dispatch as a fallback). Diffs the fresh data
   against `telegram_bot/seen_jobs.json`, buckets genuinely new jobs by
   category (`telegram_bot/categorize.py`), and posts one message per
   category to Telegram (`telegram_bot/notify.py`).

## Setup

### 1. Create the Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow the
   prompts. You'll get a token like `123456789:AAExampleTokenGoesHere`.
2. Add the bot to your channel/group with permission to post messages.
3. Get the chat id without leaving Telegram: add
   [@RawDataBot](https://t.me/RawDataBot) to the channel/group, post any
   message, and it replies with the full JSON including
   `"chat":{"id": ...}` (channel/group ids are negative, e.g.
   `-1001234567890`). Remove RawDataBot once you have it.

### 2. Add repo secrets

Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather |
| `TELEGRAM_CHAT_ID` | the id from step 1.3 |

`GITHUB_TOKEN` (used to commit scraped data and `seen_jobs.json` back) is
provided automatically - nothing to add for that.

### 3. Run it

- Both workflows run automatically once secrets are set (scrape daily,
  notify triggers off the scrape or every 6h as a fallback).
- To test immediately: Actions tab → "generate links" → Run workflow, then
  once it finishes → "Notify Telegram of new jobs" → Run workflow.

`telegram_bot/seen_jobs.json` ships pre-seeded with every job already in
`database/jobs_data.json` at the time this was set up, so the first real
notify run only reports what's actually new - not the whole dataset.

## Tuning categories

`telegram_bot/categorize.py` is a plain keyword matcher, not ML - it
checks a job's position title against ordered lists of English and
Georgian keywords and returns the first category that matches. If jobs
keep landing in "Other / IT", add the keyword that should have caught them
to the relevant category (or add a new one).
