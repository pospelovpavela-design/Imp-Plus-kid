"""
Daily digest: reads from SQLite, generates summary via Groq, posts to Telegram.
Run via cron: 0 9,21 * * * /opt/impplus/.venv/bin/python /opt/impplus/backend/digest.py
"""
import os
import sys
import time
import json
import sqlite3
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH   = Path(__file__).parent.parent / "data" / "mind.db"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL   = os.environ.get("TELEGRAM_CHANNEL", "@imp_plus")
GROQ_KEY  = os.environ.get("GROQ_API_KEY", "")
MODEL     = "llama-3.3-70b-versatile"
WINDOW    = 12 * 3600  # last 12 hours


def db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_mind_state():
    with db() as c:
        return dict(c.execute("SELECT * FROM mind_state WHERE id=1").fetchone())


def get_new_concepts(since: float):
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT name, definition, mind_time_added FROM concepts "
            "WHERE real_time_added >= ? AND is_seed=0 ORDER BY real_time_added",
            (since,)
        ).fetchall()]


def get_events(since: float):
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT type, content, mind_time FROM thought_stream "
            "WHERE created_at >= ? ORDER BY created_at",
            (since,)
        ).fetchall()]


def get_concept_count():
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]


def get_edge_count():
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM concept_connections").fetchone()[0]


def mind_age_display(born_at: float) -> str:
    elapsed = (time.time() - born_at) * 6  # MIND_TIME_RATIO
    d = int(elapsed // 86400)
    h = int((elapsed % 86400) // 3600)
    m = int((elapsed % 3600) // 60)
    return f"День {d+1}, {h:02d}:{m:02d}"


def generate_summary(concepts, events, mind_age, n_concepts, n_edges) -> str:
    if not concepts and not events:
        return "За этот период активности не было."

    concepts_text = "\n".join(
        f"- «{c['name']}»: {c['definition'][:80]}" for c in concepts
    ) or "нет"

    events_text = "\n".join(
        f"[{e['type']}] {e['content'][:120]}" for e in events[:10]
    ) or "нет"

    prompt = f"""Ты составляешь дайджест для наблюдателей за разумом IMPLUS.
Возраст разума: {mind_age}. Концепций в графе: {n_concepts}. Связей: {n_edges}.

Новые концепции:
{concepts_text}

События (спонтанные мысли, рефлексии, созерцания):
{events_text}

Напиши короткий дайджест на русском (4-6 предложений):
- Что разум узнал нового
- Какие мысли генерировал
- Как изменился граф знаний
Стиль: наблюдение со стороны, без эмоций, точно и ёмко."""

    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "max_tokens": 300,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def format_message(concepts, events, mind_age, n_concepts, n_edges, summary) -> str:
    lines = [f"◈ *IMPLUS — Дайджест*", f"_{mind_age}_", ""]

    lines.append(f"🧠 *Граф:* {n_concepts} концепций · {n_edges} связей")
    lines.append("")

    if concepts:
        lines.append("📚 *Новые концепции:*")
        for c in concepts:
            defn = c['definition'][:60] + ("…" if len(c['definition']) > 60 else "")
            lines.append(f"• *{c['name']}* — {defn}")
        lines.append("")

    type_icons = {"spontaneous": "💭", "milestone": "🏆", "contemplation": "🔍", "reaction": "⚡"}
    shown_events = [e for e in events if e["type"] in ("milestone", "contemplation")][:3]
    if not shown_events:
        shown_events = events[:3]
    if shown_events:
        lines.append("📡 *События:*")
        for e in shown_events:
            icon = type_icons.get(e["type"], "·")
            text = e["content"][:100] + ("…" if len(e["content"]) > 100 else "")
            lines.append(f"{icon} {text}")
        lines.append("")

    lines.append("🔮 *Голос наблюдателя:*")
    lines.append(summary)

    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = httpx.post(url, json={
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }, timeout=15)
    if not resp.is_success:
        print(f"Telegram error: {resp.status_code} {resp.text}", file=sys.stderr)
        return False
    return True


def main():
    if not DB_PATH.exists():
        print("DB not found", file=sys.stderr)
        sys.exit(1)

    since = time.time() - WINDOW
    state = get_mind_state()
    born_at = state["born_at"]

    concepts = get_new_concepts(since)
    events   = get_events(since)
    mind_age = mind_age_display(born_at)
    n_concepts = get_concept_count()
    n_edges    = get_edge_count()

    summary = generate_summary(concepts, events, mind_age, n_concepts, n_edges)
    message = format_message(concepts, events, mind_age, n_concepts, n_edges, summary)

    print(message)
    ok = send_telegram(message)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
