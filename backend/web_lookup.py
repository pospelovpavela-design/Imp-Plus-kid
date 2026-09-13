"""Поиск внешнего материала для концепций, у которых нет основания.

Проект строился как изолированный разум, и внешний текст здесь — не источник
готовых ответов, а такой же сырой материал опыта, как фрагмент книги от
оператора. Поэтому найденное проходит тем же путём: сохраняется как основание с
указанием источника, перерабатывается через граф и никогда не выдаётся за
собственный вывод. Происхождение остаётся в базе, чтобы выведенное всегда можно
было отделить от вычитанного.
"""
from __future__ import annotations

import os
import time

import httpx

API = "https://ru.wikipedia.org/w/api.php"
PAGE = "https://ru.wikipedia.org/wiki/"
USER_AGENT = "IMPLUS/1.0 (isolated mind research; pospelovpavel.a@gmail.com)"
MAX_EXCERPT_CHARS = 3000
# Запрос раз в полчаса из цикла, но подряд их два — держим паузу между ними
REQUEST_PAUSE_SECONDS = 1.0
_last_request = 0.0


def enabled() -> bool:
    """Поиск выключается одной переменной: это заявленная граница проекта."""
    return os.environ.get("WEB_LOOKUP_ENABLED", "1").strip().casefold() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _get(params: dict) -> dict:
    global _last_request
    wait = REQUEST_PAUSE_SECONDS - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()
    response = httpx.get(
        API,
        params={**params, "format": "json"},
        timeout=20,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response.json()


def search(term: str, limit: int = 3) -> list[str]:
    """Заголовки статей по запросу."""
    term = " ".join(str(term or "").split())
    if not term:
        return []
    data = _get({"action": "query", "list": "search", "srsearch": term, "srlimit": limit})
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


def extract(title: str) -> tuple[str, str]:
    """Вводная часть статьи и ссылка на неё."""
    data = _get(
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "exintro": 1,
            "titles": title,
            "redirects": 1,
        }
    )
    for page in data.get("query", {}).get("pages", {}).values():
        text = " ".join(str(page.get("extract") or "").split())
        if len(text) > MAX_EXCERPT_CHARS:
            text = text[: MAX_EXCERPT_CHARS - 3].rstrip() + "..."
        return text, PAGE + str(page.get("title", title)).replace(" ", "_")
    return "", ""


def lookup(term: str) -> dict | None:
    """Первая статья с содержательной вводной частью, либо None.

    Отказ источника — не повод ронять цикл: разум обойдётся без материала.
    """
    try:
        titles = search(term)
    except httpx.HTTPError:
        return None
    for title in titles:
        try:
            text, url = extract(title)
        except httpx.HTTPError:
            return None
        if len(text) >= 120:
            return {"title": title, "text": text, "url": url}
    return None
