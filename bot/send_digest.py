import html
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MAX_PER_RUN = 5
MAX_PER_SOURCE = 2       # max articles from a single source label per digest
LOOKBACK_HOURS = 24      # how far back to look in RSS feeds
SENT_FILE = Path(__file__).parent.parent / "data" / "sent.json"
SENT_MAX_AGE_DAYS = 7    # forget URLs older than this to keep file small

FEEDS = [
    # 🔥 Java & AI — Hacker News
    {"url": "https://hnrss.org/newest?q=java&count=20",                    "label": "Hacker News"},
    {"url": "https://hnrss.org/newest?q=artificial+intelligence&count=20", "label": "Hacker News"},

    # 💻 Dev.to
    {"url": "https://dev.to/feed/tag/java", "label": "Dev.to"},
    {"url": "https://dev.to/feed/tag/ai",   "label": "Dev.to"},

    # 🧠 AI core
    {"url": "https://openai.com/blog/rss.xml",            "label": "OpenAI"},
    {"url": "https://blog.google/technology/ai/rss/",     "label": "Google AI"},
    {"url": "https://www.deepmind.com/blog/rss.xml",      "label": "DeepMind"},

    # 📰 Новости
    {"url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "label": "MIT Tech Review"},

    # 🔴 Reddit
    {"url": "https://www.reddit.com/r/java/.rss", "label": "Reddit r/java"},
]


# ---------------------------------------------------------------------------
# sent.json helpers
# ---------------------------------------------------------------------------

def load_sent() -> dict[str, str]:
    """Load sent URLs → {url: iso_timestamp}. Returns empty dict if file missing."""
    if not SENT_FILE.exists():
        return {}
    try:
        raw = json.loads(SENT_FILE.read_text())
        if isinstance(raw, list):
            return {url: "1970-01-01T00:00:00+00:00" for url in raw}
        return raw
    except Exception as e:
        log.warning("Could not read sent.json: %s", e)
        return {}


def save_sent(sent: dict[str, str]) -> None:
    """Persist sent dict, pruning entries older than SENT_MAX_AGE_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=SENT_MAX_AGE_DAYS)
    pruned = {
        url: ts
        for url, ts in sent.items()
        if datetime.fromisoformat(ts) >= cutoff
    }
    SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SENT_FILE.write_text(json.dumps(pruned, indent=2, ensure_ascii=False))
    log.info("Saved %d URLs to sent.json (pruned %d old)", len(pruned), len(sent) - len(pruned))


# ---------------------------------------------------------------------------
# Feed fetching
# ---------------------------------------------------------------------------

def parse_published(entry: dict) -> datetime | None:
    raw = entry.get("published_parsed") or entry.get("updated_parsed")
    if not raw:
        return None
    return datetime(*raw[:6], tzinfo=timezone.utc)


def is_recent(published_dt: datetime | None) -> bool:
    if published_dt is None:
        return True  # no timestamp → include it
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    return published_dt >= cutoff


def fetch_feed(feed: dict) -> list[dict]:
    try:
        parsed = feedparser.parse(feed["url"])
        articles = []
        for entry in parsed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "No title")
            published_dt = parse_published(entry)
            if url and is_recent(published_dt):
                articles.append({
                    "url": url,
                    "title": title,
                    "label": feed["label"],
                    "published_dt": published_dt,
                })
        return articles
    except Exception as e:
        log.error("Failed to fetch %s: %s", feed["url"], e)
        return []


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

SOURCE_ICONS: dict[str, str] = {
    "Hacker News":    "🔶",
    "Dev.to":         "🟣",
    "OpenAI":         "🤖",
    "Google AI":      "🔵",
    "DeepMind":       "🧠",
    "MIT Tech Review":"📡",
    "Reddit r/java":  "🔴",
}


def format_age(published_dt: datetime | None) -> str:
    if published_dt is None:
        return ""
    delta = datetime.now(timezone.utc) - published_dt
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 60:
        return f"{total_minutes}m ago"
    hours = total_minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def build_message(articles: list[dict]) -> str:
    TZ_MSK = timezone(timedelta(hours=3))
    now_msk = datetime.now(TZ_MSK)
    header = f"🗞 <b>Dev Digest · {now_msk.strftime('%-d %b, %H:%M')}</b>\n{'━' * 16}"

    lines = [header]
    for article in articles:
        title = html.escape(article["title"])
        url = article["url"]
        label = article["label"]
        icon = SOURCE_ICONS.get(label, "📌")
        age = format_age(article["published_dt"])
        age_part = f" · {age}" if age else ""
        lines.append(
            f'<a href="{url}"><b>{title}</b></a>\n'
            f'{icon} {label}{age_part}'
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def notify_error(error: Exception) -> None:
    try:
        send_message(f"⚠️ <b>RSS Digest failed</b>\n\n<code>{html.escape(str(error))}</code>")
    except Exception:
        pass  # don't recurse


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        _run()
    except Exception as e:
        log.exception("Unhandled error")
        notify_error(e)
        raise


def _run() -> None:
    sent = load_sent()
    log.info("Loaded %d already-sent URLs from sent.json", len(sent))

    # Collect all candidate articles (dedup within this run and against sent.json)
    candidates: list[dict] = []
    seen_in_run: set[str] = set()

    with ThreadPoolExecutor(max_workers=len(FEEDS)) as executor:
        for articles in executor.map(fetch_feed, FEEDS):
            for article in articles:
                url = article["url"]
                if url not in sent and url not in seen_in_run:
                    candidates.append(article)
                    seen_in_run.add(url)

    # Sort newest first so we pick the freshest articles
    candidates.sort(key=lambda a: a["published_dt"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    log.info("Found %d new candidate articles", len(candidates))

    # Apply per-source cap to ensure variety
    source_counts: dict[str, int] = {}
    to_send: list[dict] = []
    for article in candidates:
        label = article["label"]
        if source_counts.get(label, 0) < MAX_PER_SOURCE:
            to_send.append(article)
            source_counts[label] = source_counts.get(label, 0) + 1
        if len(to_send) >= MAX_PER_RUN:
            break

    if not to_send:
        log.info("Nothing new to send")
        return

    send_message(build_message(to_send))

    now_iso = datetime.now(timezone.utc).isoformat()
    for article in to_send:
        sent[article["url"]] = now_iso
    save_sent(sent)

    log.info("Sent digest with %d articles", len(to_send))


if __name__ == "__main__":
    main()
