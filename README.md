# RssDevPulseBot

Serverless RSS → Telegram digest bot powered by **GitHub Actions**.  
No server. No database. Completely free.

## How it works

1. GitHub Actions runs on cron — every 4 hours (07:00, 11:00, 15:00, 19:00 UTC)
2. Python script fetches RSS feeds in parallel
3. Articles already sent (tracked in `data/sent.json`) are skipped
4. Remaining articles are sorted by publish date — freshest first
5. Up to 5 articles are sent, capped at 2 per source for variety
6. Updated `sent.json` is committed back to the repo

## Example message

```
🗞 Dev Digest · 20 Apr, 14:00
━━━━━━━━━━━━━━━━

New JVM features in Java 25
🔶 Hacker News · 1h ago

GPT-5 announced
🤖 OpenAI · 3h ago

Building AI agents with Java
🟣 Dev.to · 5h ago
```

## Setup

### 1. Create a Telegram bot

- Open [@BotFather](https://t.me/BotFather) → `/newbot` → copy the **token**
- Get your **chat ID** via [@userinfobot](https://t.me/userinfobot)

### 2. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name           | Value                    |
|-----------------------|--------------------------|
| `TELEGRAM_BOT_TOKEN`  | Token from BotFather     |
| `TELEGRAM_CHAT_ID`    | Your chat or channel ID  |

### 3. Push to GitHub

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/<you>/RssDevPulseBot.git
git push -u origin main
```

### 4. Run manually to test

GitHub repo → **Actions → RSS Digest → Run workflow**

## RSS Sources

| Source          | Feed                                         |
|-----------------|----------------------------------------------|
| 🔶 Hacker News  | `hnrss.org/newest?q=java`                    |
| 🔶 Hacker News  | `hnrss.org/newest?q=artificial+intelligence` |
| 🟣 Dev.to       | `dev.to/feed/tag/java`                       |
| 🟣 Dev.to       | `dev.to/feed/tag/ai`                         |
| 🤖 OpenAI       | `openai.com/blog/rss.xml`                    |
| 🔵 Google AI    | `blog.google/technology/ai/rss/`             |
| 🧠 DeepMind     | `deepmind.com/blog/rss.xml`                  |
| 📡 MIT Tech Review | `technologyreview.com/.../feed`           |
| 🔴 Reddit r/java | `reddit.com/r/java/.rss`                    |

## Customization

- **Add/remove feeds** — edit `FEEDS` in [bot/send_digest.py](bot/send_digest.py)
- **Change schedule** — edit `schedule` in [.github/workflows/rss_digest.yml](.github/workflows/rss_digest.yml)
- **Max articles per run** — `MAX_PER_RUN` in [bot/send_digest.py](bot/send_digest.py) (default: 5)
- **Max per source** — `MAX_PER_SOURCE` in [bot/send_digest.py](bot/send_digest.py) (default: 2)
- **URL memory window** — `SENT_MAX_AGE_DAYS` in [bot/send_digest.py](bot/send_digest.py) (default: 7 days)
