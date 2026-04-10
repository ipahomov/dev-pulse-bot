# RssDevPulseBot — как это работает

## Идея в одном предложении

GitHub сам по расписанию запускает Python-скрипт, который читает RSS-ленты и отправляет новые статьи в Telegram. Никакого сервера, никакой базы данных, всё бесплатно.

---

## Архитектура

```
GitHub Actions (cron)
        │
        ▼
bot/send_digest.py
        │
        ├── читает data/sent.json      — список уже отправленных URL
        ├── парсит 5 RSS-фидов         — через библиотеку feedparser
        ├── фильтрует новые статьи     — которых нет в sent.json
        ├── отправляет до 5 статей     — через Telegram Bot API (HTTP POST)
        └── сохраняет sent.json        — коммит обратно в репо
```

---

## Файлы проекта

| Файл | Назначение |
|------|-----------|
| `bot/send_digest.py` | Основной скрипт. Вся логика здесь |
| `data/sent.json` | JSON-массив URL уже отправленных статей. Обновляется после каждого запуска |
| `.github/workflows/rss_digest.yml` | Описание GitHub Actions job: расписание, шаги, права |
| `requirements.txt` | Python-зависимости: `feedparser` + `requests` |

---

## Как работает скрипт (bot/send_digest.py)

### 1. Загрузка состояния
```python
sent = load_sent()  # читает data/sent.json → set URL
```
Если файл не существует — возвращает пустое множество.

### 2. Обход RSS-фидов
```python
FEEDS = [
    {"url": "https://hnrss.org/newest?q=java&count=20",              "label": "Hacker News"},
    {"url": "https://hnrss.org/newest?q=artificial+intelligence&count=20", "label": "Hacker News"},
    {"url": "https://dev.to/feed/tag/java",                           "label": "Dev.to"},
    {"url": "https://dev.to/feed/tag/ai",                             "label": "Dev.to"},
    {"url": "https://www.reddit.com/r/java/.rss",                     "label": "Reddit r/java"},
]
```
`feedparser.parse(url)` скачивает и парсит RSS/Atom. Для каждой записи берём `link` и `title`.

### 3. Фильтрация дублей
Статья пропускается, если её URL уже есть в `sent` (из прошлых запусков) или уже встречался в этом же запуске (один URL может быть в нескольких фидах).

### 4. Отправка в Telegram
```python
requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
)
```
Используется HTTP API Telegram напрямую — без сторонних Telegram-библиотек.  
Заголовок экранируется через `html.escape()`, чтобы символы `&`, `<`, `>` не ломали HTML-разметку.

### 5. Сохранение состояния
После отправки URL добавляется в `sent`, потом весь set сохраняется в `data/sent.json`. Следующий запуск не продублирует эти статьи.

---

## Как работает GitHub Actions (rss_digest.yml)

### Расписание
```yaml
schedule:
  - cron: "0 8,10,12,14,16,18,20 * * *"  # каждые 2ч с 8:00 до 20:00 UTC
```
UTC+3 (Москва) → запуски в 11:00, 13:00, 15:00, 17:00, 19:00, 21:00, 23:00.  
Также есть `workflow_dispatch` — ручной запуск прямо из GitHub UI.

### Шаги job
1. `actions/checkout` — клонирует репо (нужен для чтения/записи `sent.json`)
2. `actions/setup-python` — Python 3.12
3. `pip install -r requirements.txt` — устанавливает feedparser и requests
4. `python bot/send_digest.py` — запускает скрипт с секретами из GitHub Secrets
5. Коммит `sent.json` обратно в репо — только если файл изменился (новые статьи были отправлены)

### Права
```yaml
permissions:
  contents: write  # нужно для git push обратно в репо
```

---

## Хранение состояния без базы данных

Вместо БД используется `data/sent.json` — обычный JSON-файл в самом репо.  
После каждого успешного запуска GitHub Actions делает коммит:
```
chore: update sent.json [skip ci]
```
`[skip ci]` — чтобы этот коммит не триггерил новый запуск workflow.

Недостаток: при большом количестве статей файл растёт. Не критично для личного использования, но если нужно — можно добавить ротацию (хранить только последние N URL).

---

## Секреты (GitHub Secrets)

| Переменная | Где взять |
|------------|-----------|
| `TELEGRAM_BOT_TOKEN` | @BotFather → `/newbot` |
| `TELEGRAM_CHAT_ID` | Свой личный ID (узнать через `getUpdates` или @userinfobot) |

Секреты задаются в: репо → Settings → Secrets and variables → Actions.  
В скрипте читаются через `os.environ["TELEGRAM_BOT_TOKEN"]`.

---

## Как добавить новый RSS-источник

Добавь словарь в список `FEEDS` в [bot/send_digest.py](bot/send_digest.py):
```python
{"url": "https://example.com/feed.rss", "label": "Example"},
```
Больше ничего менять не нужно.

---

## Как изменить расписание

Отредактируй cron-выражение в [.github/workflows/rss_digest.yml](.github/workflows/rss_digest.yml):
```yaml
- cron: "0 8,10,12,14,16,18,20 * * *"
```
Синтаксис: `минута час день месяц день_недели`. Время всегда UTC.

---

## Как запустить локально

```bash
pip install -r requirements.txt

TELEGRAM_BOT_TOKEN=<токен> TELEGRAM_CHAT_ID=<chat_id> python3 bot/send_digest.py
```

## Запустить вручную

GitHub → Actions → RSS Digest → Run workflow