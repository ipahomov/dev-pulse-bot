# RssDevPulseBot

Serverless RSS → Telegram digest bot powered by **GitHub Actions**.  
No server. No database. Completely free.

## How it works

1. GitHub Actions runs on cron — **08:00 UTC** and **18:00 UTC**
2. Python script fetches RSS feeds (Hacker News, Dev.to, Reddit r/java)
3. New articles (not in `data/sent.json`) are sent to Telegram
4. Updated `sent.json` is committed back to the repo — no duplicates next run

## Setup

### 1. Create a Telegram bot

- Open [@BotFather](https://t.me/BotFather) → `/newbot` → copy the **token**
- Get your **chat ID** via [@userinfobot](https://t.me/userinfobot) (or use a channel ID like `-100xxxxxxxxxx`)

### 2. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name           | Value                        |
|-----------------------|------------------------------|
| `TELEGRAM_BOT_TOKEN`  | Token from BotFather         |
| `TELEGRAM_CHAT_ID`    | Your chat or channel ID      |

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

| Source          | Feed                                              |
|-----------------|---------------------------------------------------|
| Hacker News     | `hnrss.org/newest?q=java`                         |
| Hacker News     | `hnrss.org/newest?q=artificial+intelligence`      |
| Dev.to          | `dev.to/feed/tag/java`                            |
| Dev.to          | `dev.to/feed/tag/ai`                              |
| Reddit r/java   | `reddit.com/r/java/.rss`                          |

## Customization

- **Add/remove feeds** — edit `FEEDS` list in [bot/send_digest.py](bot/send_digest.py)
- **Change cron schedule** — edit `schedule` in [.github/workflows/rss_digest.yml](.github/workflows/rss_digest.yml)
- **Change max articles per run** — edit `MAX_PER_RUN` in [bot/send_digest.py](bot/send_digest.py) (default: 5)
