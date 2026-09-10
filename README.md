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

## Per-user category preferences (optional)

The channel/group gets every new job, always. Anyone who wants only
specific categories can instead DM the bot directly and pick what they
want - that's a separate, always-on service (`webhook_bot/app.py`,
deployed on Render) that Telegram calls whenever someone messages the bot
or taps a button.

Preferences are stored in [Upstash](https://upstash.com) Redis (free tier)
rather than this repo - a `subscribers` hash, one field per chat_id. Setup:

1. Create a free Redis database at console.upstash.com, grab its
   **REST URL** and **REST token**.
2. Add two more repo secrets (same place as above):

   | Secret | Value |
   |---|---|
   | `UPSTASH_REDIS_REST_URL` | from the Upstash console |
   | `UPSTASH_REDIS_REST_TOKEN` | from the Upstash console |

3. Deploy `webhook_bot/` as its own Render web service (build:
   `pip install -r webhook_bot/requirements.txt`, start:
   `gunicorn --chdir webhook_bot app:app`), with env vars
   `TELEGRAM_BOT_TOKEN`, `UPSTASH_REDIS_REST_URL`,
   `UPSTASH_REDIS_REST_TOKEN`, and optionally `TELEGRAM_WEBHOOK_SECRET`
   (a random string - if set, Telegram must echo it back on every request
   for the webhook to accept it).
4. Point Telegram at it once:
   ```
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=<RENDER_URL>/webhook&secret_token=<SECRET>
   ```

This step is entirely optional - without it, `notify.py` just skips
personalized delivery and the channel broadcast keeps working exactly the
same either way.

Since the channel/group itself always gets the same message for everyone
(Telegram has no way to show different content to different members of a
channel), the only way people find out DM preferences exist is a pinned
message in the channel with a button that deep-links into the bot's
`/start` flow. Post (or re-post, e.g. after an accidental unpin) that
pinned message via Actions tab → "post channel instructions" → Run
workflow (`telegram_bot/post_channel_instructions.py`, uses the same
`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` secrets as everything else).

The same two secrets also let the scrape workflow mirror its output into
Redis under a plain string key, `jobs_data` (`scheduled_scripts/sync_to_redis.py`,
run as a step in `test.yml`) - purely additive, alongside the existing
git commit, for anything that'd rather read the current job list from
Redis than check out the repo.

## Tuning categories

`telegram_bot/categorize.py` is a plain keyword matcher, not ML - it
checks a job's position title against ordered lists of English and
Georgian keywords and returns the first category that matches. If jobs
keep landing in "Other / IT", add the keyword that should have caught them
to the relevant category (or add a new one).
