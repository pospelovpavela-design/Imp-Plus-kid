"""Generate one daily insight and send only that insight to Telegram.

Production schedule (UTC, 21:40 with two safe retries in Asia/Chita):
    40 12 * * * /opt/impplus/.venv/bin/python /opt/impplus/backend/digest.py
    55 12 * * * /opt/impplus/.venv/bin/python /opt/impplus/backend/digest.py
    10 13 * * * /opt/impplus/.venv/bin/python /opt/impplus/backend/digest.py
"""

from __future__ import annotations

import asyncio
import html
import os
from pathlib import Path
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import daily_insight_engine
import db


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@imp_plus")


def format_message(content: str, request: str = "") -> str:
    """Итог дня и, если он есть, один вопрос разума к оператору."""
    text = html.escape(content.strip())
    if request.strip():
        text += "\n\n" + html.escape("Мне не хватает: " + " ".join(request.split()))
    return text


def pending_request() -> str:
    """Самая насущная просьба разума. Канал наружу один, вопрос за раз тоже один."""
    rows = db.list_operator_requests(limit=1)
    return str(rows[0]["question"]) if rows else ""


def send_telegram(content: str, request: str = "") -> bool:
    if not BOT_TOKEN or not CHANNEL:
        print("Telegram credentials are not configured", file=sys.stderr)
        return False
    response = httpx.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHANNEL,
            "text": format_message(content, request),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    if not response.is_success:
        print(
            f"Telegram error: {response.status_code} {response.text}",
            file=sys.stderr,
        )
        return False
    return True


async def prepare_today() -> dict:
    state = db.get_mind_state()
    if state is None:
        raise RuntimeError("Mind state is not initialized")
    insight, _created = await daily_insight_engine.generate_for_date(
        daily_insight_engine.local_today(),
        float(state["born_at"]),
    )
    return insight


def main() -> int:
    db.init_db()
    insight = asyncio.run(prepare_today())
    if insight["sent_at"] is not None:
        print(f"daily insight {insight['local_date']} already sent")
        return 0

    if not send_telegram(insight["content"], pending_request()):
        return 1
    if not db.mark_daily_insight_sent(int(insight["id"]), time.time()):
        print("Daily insight was sent but sent_at was already set", file=sys.stderr)
        return 1
    print(f"sent daily insight {insight['local_date']}: {insight['content']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
