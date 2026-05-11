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
import html
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH   = Path(__file__).parent.parent / "data" / "mind.db"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL   = os.environ.get("TELEGRAM_CHANNEL", "@imp_plus")
GROQ_KEY  = os.environ.get("GROQ_API_KEY", "")
MODEL     = "llama-3.3-70b-versatile"
WINDOW    = 24 * 3600  # last day
os.environ.setdefault("MPLCONFIGDIR", str(DB_PATH.parent / ".matplotlib-cache"))


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


def get_recent_graph(since: float):
    with db() as c:
        edges = [dict(r) for r in c.execute(
            """SELECT cc.concept_a_id, cc.concept_b_id, cc.relationship, cc.strength,
                      cc.created_at, ca.name AS source_name, cb.name AS target_name
               FROM concept_connections cc
               JOIN concepts ca ON ca.id = cc.concept_a_id
               JOIN concepts cb ON cb.id = cc.concept_b_id
               WHERE cc.created_at >= ?
               ORDER BY cc.created_at""",
            (since,),
        ).fetchall()]
        concept_ids = {
            concept_id
            for edge in edges
            for concept_id in (edge["concept_a_id"], edge["concept_b_id"])
        }
        new_nodes = [dict(r) for r in c.execute(
            """SELECT id, name, is_seed, is_autonomous, real_time_added
               FROM concepts
               WHERE real_time_added >= ?
               ORDER BY real_time_added""",
            (since,),
        ).fetchall()]
        concept_ids.update(node["id"] for node in new_nodes)
        if not concept_ids:
            return {"nodes": [], "edges": []}
        placeholders = ",".join("?" for _ in concept_ids)
        nodes = [dict(r) for r in c.execute(
            f"""SELECT id, name, is_seed, is_autonomous, real_time_added
                FROM concepts
                WHERE id IN ({placeholders})""",
            tuple(concept_ids),
        ).fetchall()]
    return {"nodes": nodes, "edges": edges}


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
Стиль: наблюдение со стороны, без эмоций, точно и ёмко.
Обязательно заверши последнюю фразу полным предложением."""

    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "max_tokens": 800,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=30,
    )
    resp.raise_for_status()
    return finish_sentence(resp.json()["choices"][0]["message"]["content"].strip())


def finish_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    if text[-1] in ".!?…":
        return text
    last_end = max(text.rfind("."), text.rfind("!"), text.rfind("?"), text.rfind("…"))
    if last_end > len(text) // 2:
        return text[:last_end + 1].strip()
    return text + "."


def truncate(text: str, limit: int) -> str:
    """Truncate at sentence end if possible, otherwise at word boundary."""
    if len(text) <= limit:
        return text
    chunk = text[:limit]
    # try to end at sentence boundary
    for sep in ('. ', '! ', '? ', '.\n'):
        pos = chunk.rfind(sep)
        if pos > limit // 2:
            return chunk[:pos + 1]
    # fall back to word boundary
    pos = chunk.rfind(' ')
    if pos > limit // 2:
        return chunk[:pos] + '…'
    return chunk + '…'


def format_message(concepts, events, mind_age, n_concepts, n_edges, summary) -> str:
    lines = [f"◈ <b>IMPLUS — Дайджест</b>", f"<i>{html.escape(mind_age)}</i>", ""]

    lines.append(f"🧠 <b>Граф:</b> {n_concepts} концепций · {n_edges} связей")
    lines.append("")

    if concepts:
        lines.append("📚 <b>Новые концепции:</b>")
        for c in concepts:
            name = html.escape(c["name"])
            defn = html.escape(truncate(c["definition"], 120))
            lines.append(f"• <b>{name}</b> — {defn}")
        lines.append("")

    type_icons = {"spontaneous": "💭", "milestone": "🏆", "contemplation": "🔍", "reaction": "⚡"}
    shown_events = [e for e in events if e["type"] in ("milestone", "contemplation")][:3]
    if not shown_events:
        shown_events = events[:3]
    if shown_events:
        lines.append("📡 <b>События:</b>")
        for e in shown_events:
            icon = type_icons.get(e["type"], "·")
            text = html.escape(truncate(e["content"], 200))
            lines.append(f"{icon} {text}")
        lines.append("")

    lines.append("🔮 <b>Голос наблюдателя:</b>")
    lines.append(html.escape(summary))

    return "\n".join(lines)


def split_telegram_text(text: str, limit: int = 3900) -> list[str]:
    parts = []
    rest = text
    while len(rest) > limit:
        cut = rest.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        parts.append(rest)
    return parts


def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for part in split_telegram_text(text):
        resp = httpx.post(url, json={
            "chat_id": CHANNEL,
            "text": part,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        if not resp.is_success:
            print(f"Telegram error: {resp.status_code} {resp.text}", file=sys.stderr)
            return False
    return True


def render_graph_image(graph_data, output_path: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx
    except Exception as exc:
        print(f"Graph image skipped: {exc}", file=sys.stderr)
        return None

    output_path.parent.mkdir(exist_ok=True)
    g = nx.Graph()
    for node in graph_data["nodes"]:
        g.add_node(node["id"], label=node["name"], is_autonomous=bool(node["is_autonomous"]))
    for edge in graph_data["edges"]:
        g.add_edge(
            edge["concept_a_id"],
            edge["concept_b_id"],
            weight=float(edge["strength"] or 1.0),
            label=edge["relationship"] or "",
        )

    fig, ax = plt.subplots(figsize=(12, 7), dpi=180)
    fig.patch.set_facecolor("#070914")
    ax.set_facecolor("#070914")
    ax.axis("off")
    ax.set_title("IMPLUS: связи за прошедшие 24 часа", color="#dde0f0",
                 fontsize=18, pad=18)

    if g.number_of_nodes() == 0:
        ax.text(0.5, 0.5, "За прошедшие 24 часа новых связей не появилось",
                color="#7880a0", ha="center", va="center", fontsize=16,
                transform=ax.transAxes)
    else:
        pos = nx.spring_layout(g, seed=42, k=1.0, iterations=120)
        degrees = dict(g.degree())
        node_sizes = [360 + degrees[node] * 180 for node in g.nodes]
        node_colors = [
            "#c8a84b" if g.nodes[node].get("is_autonomous") else "#2d5a9e"
            for node in g.nodes
        ]
        edge_widths = [0.8 + float(g.edges[edge].get("weight", 1.0)) * 2.2 for edge in g.edges]

        nx.draw_networkx_edges(g, pos, ax=ax, width=edge_widths, edge_color="#3d7fff",
                               alpha=0.38)
        nx.draw_networkx_nodes(g, pos, ax=ax, node_size=node_sizes,
                               node_color=node_colors, edgecolors="#9bb3ff",
                               linewidths=1.1, alpha=0.96)
        labels = {
            node: str(g.nodes[node]["label"])[:28] + ("…" if len(str(g.nodes[node]["label"])) > 28 else "")
            for node in g.nodes
        }
        nx.draw_networkx_labels(g, pos, labels=labels, ax=ax, font_size=8,
                                font_color="#dde0f0", font_family="DejaVu Sans")

    plt.tight_layout(pad=1.4)
    fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return output_path


def send_telegram_photo(image_path: Path, caption: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with image_path.open("rb") as image:
        resp = httpx.post(
            url,
            data={"chat_id": CHANNEL, "caption": caption},
            files={"photo": (image_path.name, image, "image/png")},
            timeout=30,
        )
    if not resp.is_success:
        print(f"Telegram photo error: {resp.status_code} {resp.text}", file=sys.stderr)
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
    recent_graph = get_recent_graph(since)
    mind_age = mind_age_display(born_at)
    n_concepts = get_concept_count()
    n_edges    = get_edge_count()

    summary = generate_summary(concepts, events, mind_age, n_concepts, n_edges)
    message = format_message(concepts, events, mind_age, n_concepts, n_edges, summary)

    print(message)
    ok = send_telegram(message)
    image_path = render_graph_image(recent_graph, DB_PATH.parent / "daily_graph.png")
    if image_path is not None:
        ok = send_telegram_photo(image_path, "Связи IMPLUS за прошедшие 24 часа") and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
