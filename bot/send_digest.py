import html
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import feedparser
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MAX_PER_RUN = 5
LOOKBACK_HOURS = 4

FEEDS = [
    # 🔥 Java & AI — Hacker News
    {"url": "https://hnrss.org/newest?q=java&count=20", "label": "Hacker News"},
    {"url": "https://hnrss.org/newest?q=artificial+intelligence&count=20", "label": "Hacker News"},

    # 💻 Dev.to
    {"url": "https://dev.to/feed/tag/ai", "label": "Dev.to"},

    # 🧠 AI core
    {"url": "https://openai.com/blog/rss.xml", "label": "OpenAI"},
    {"url": "https://blog.google/technology/ai/rss/", "label": "Google AI"},
    {"url": "https://www.deepmind.com/blog/rss.xml", "label": "DeepMind"},

    # 📰 Новости
    {"url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "label": "MIT Tech Review"},
]


def is_recent(entry: dict) -> bool:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        return True  # no timestamp → include it
    published_dt = datetime(*published[:6], tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    return published_dt >= cutoff


def fetch_recent_articles(feed: dict) -> list[dict]:
    try:
        parsed = feedparser.parse(feed["url"])
        articles = []
        for entry in parsed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "No title")
            if url and is_recent(entry):
                articles.append({"url": url, "title": title, "label": feed["label"]})
        return articles
    except Exception as e:
        log.error("Failed to fetch %s: %s", feed["url"], e)
        return []


def send_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def main() -> None:
    new_articles = []
    seen_urls: set[str] = set()

    with ThreadPoolExecutor(max_workers=len(FEEDS)) as executor:
        for articles in executor.map(fetch_recent_articles, FEEDS):
            for article in articles:
                url = article["url"]
                if url not in seen_urls:
                    new_articles.append(article)
                    seen_urls.add(url)

    log.info("Found %d recent articles (last %dh)", len(new_articles), LOOKBACK_HOURS)

    to_send = new_articles[:MAX_PER_RUN]
    if not to_send:
        log.info("Nothing new to send")
        return

    lines = []
    for article in to_send:
        title = html.escape(article["title"])
        lines.append(f'📰 <b>{title}</b>\n🔗 {article["url"]}\n📌 {article["label"]}')

    text = "\n\n".join(lines)
    try:
        send_message(text)
        log.info("Sent digest with %d articles", len(to_send))
    except Exception as e:
        log.error("Failed to send digest: %s", e)


if __name__ == "__main__":
    main()
