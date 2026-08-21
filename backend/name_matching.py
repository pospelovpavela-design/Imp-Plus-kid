"""Устойчивое сопоставление имён концепций.

Модель называет концепции естественным языком: склоняет их и опускает
служебную пунктуацию, осевшую в именах графа (например «КОМБИНИРИСТИКА:»).
Точное сравнение по casefold теряло такие имена молча, поэтому сопоставление
идёт по нормализованной форме, а затем по близости с проверкой однозначности.
"""
from __future__ import annotations

import difflib
import re
from typing import Iterable

_SERVICE_CHARS = " \t\r\n:;,.!?«»\"'()[]{}-–—"
_SPACES = re.compile(r"\s+")


def normalize(name: str) -> str:
    """Форма имени без регистра, лишних пробелов и служебной пунктуации."""
    text = _SPACES.sub(" ", str(name or "")).strip()
    return text.strip(_SERVICE_CHARS).casefold()


def build_index(names: Iterable[str]) -> dict[str, str]:
    """Нормализованная форма → исходное имя концепции."""
    index: dict[str, str] = {}
    for name in names:
        key = normalize(name)
        if key:
            index.setdefault(key, name)
    return index


def resolve(
    name: str,
    index: dict[str, str],
    *,
    cutoff: float = 0.86,
    margin: float = 0.04,
) -> str | None:
    """Имя из ответа модели → имя концепции графа, либо None.

    Неоднозначное совпадение (два имени графа одинаково близки) считается
    несопоставленным: лучше потерять связь, чем приписать её чужой концепции.
    """
    key = normalize(name)
    if not key:
        return None
    exact = index.get(key)
    if exact is not None:
        return exact
    matches = difflib.get_close_matches(key, list(index), n=2, cutoff=cutoff)
    if not matches:
        return None
    if len(matches) > 1:
        best = difflib.SequenceMatcher(None, key, matches[0]).ratio()
        runner_up = difflib.SequenceMatcher(None, key, matches[1]).ratio()
        if best - runner_up < margin:
            return None
    return index[matches[0]]
