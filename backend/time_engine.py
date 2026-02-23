"""
Mind-time engine.

Ratio: 1 real second = MIND_TIME_RATIO mind seconds (default 6).
So 10 real minutes = 60 mind minutes = 1 mind hour.

mind_start_timestamp is stored once in DB on first launch and never changes.
The mind's subjective age is always calculated from that immutable anchor.
"""
import time
from dataclasses import dataclass
from typing import Optional

MIND_TIME_RATIO: int = 6  # 1 real second → 6 mind seconds

# Milestone thresholds in mind-seconds → (key, label)
MILESTONES: list[tuple[str, int, str]] = [
    ("1h",  3_600,       "Первый час"),
    ("6h",  21_600,      "Шесть часов"),
    ("12h", 43_200,      "Двенадцать часов"),
    ("1d",  86_400,      "Первый день"),
    ("3d",  259_200,     "Три дня"),
    ("7d",  604_800,     "Первая неделя"),
    ("14d", 1_209_600,   "Две недели"),
    ("30d", 2_592_000,   "Первый месяц"),
]


@dataclass
class TimeDisplay:
    mind_days: int
    mind_hours: int
    mind_minutes: int
    mind_seconds: int
    mind_display: str          # "День 2, 14:33:07"
    mind_total_seconds: float

    real_days: int
    real_hours: int
    real_minutes: int
    real_seconds: int
    real_display: str          # "00:47:12" (elapsed real time)
    real_total_seconds: float

    mind_age_human: str        # "2 дня 14 часов 33 минуты"
    ratio: int


def get_mind_elapsed_seconds(born_at: float) -> float:
    """Total mind-seconds elapsed since birth."""
    real_elapsed = time.time() - born_at
    return real_elapsed * MIND_TIME_RATIO


def _format_seconds(total: float) -> tuple[int, int, int, int]:
    total = int(total)
    days = total // 86400
    rem  = total % 86400
    hours   = rem // 3600
    rem  = rem % 3600
    minutes = rem // 60
    seconds = rem % 60
    return days, hours, minutes, seconds


def _age_human(days: int, hours: int, minutes: int) -> str:
    parts = []
    if days:
        d_word = "день" if days == 1 else ("дня" if 2 <= days <= 4 else "дней")
        parts.append(f"{days} {d_word}")
    if hours:
        h_word = "час" if hours == 1 else ("часа" if 2 <= hours <= 4 else "часов")
        parts.append(f"{hours} {h_word}")
    if minutes or not parts:
        m_word = "минута" if minutes == 1 else ("минуты" if 2 <= minutes <= 4 else "минут")
        parts.append(f"{minutes} {m_word}")
    return " ".join(parts)


def get_time_display(born_at: float) -> TimeDisplay:
    real_elapsed = time.time() - born_at
    mind_elapsed = real_elapsed * MIND_TIME_RATIO

    md, mh, mm, ms = _format_seconds(mind_elapsed)
    rd, rh, rm, rs = _format_seconds(real_elapsed)

    mind_display = f"День {md + 1}, {mh:02d}:{mm:02d}:{ms:02d}"
    if rd > 0:
        real_display = f"{rd}д {rh:02d}:{rm:02d}:{rs:02d}"
    else:
        real_display = f"{rh:02d}:{rm:02d}:{rs:02d}"

    return TimeDisplay(
        mind_days=md, mind_hours=mh, mind_minutes=mm, mind_seconds=ms,
        mind_display=mind_display,
        mind_total_seconds=mind_elapsed,
        real_days=rd, real_hours=rh, real_minutes=rm, real_seconds=rs,
        real_display=real_display,
        real_total_seconds=real_elapsed,
        mind_age_human=_age_human(md, mh, mm),
        ratio=MIND_TIME_RATIO,
    )


def format_mind_timestamp(born_at: float, at_real: Optional[float] = None) -> str:
    """Format a specific real timestamp as mind-time string."""
    ref = at_real if at_real is not None else time.time()
    mind_elapsed = (ref - born_at) * MIND_TIME_RATIO
    d, h, m, s = _format_seconds(mind_elapsed)
    return f"День {d + 1}, {h:02d}:{m:02d}:{s:02d}"


def check_new_milestones(born_at: float, reached_keys: set[str]) -> list[tuple[str, str]]:
    """
    Returns list of (key, label) for milestones crossed since last check
    that are not yet in reached_keys.
    """
    mind_elapsed = get_mind_elapsed_seconds(born_at)
    new: list[tuple[str, str]] = []
    for key, threshold, label in MILESTONES:
        if key not in reached_keys and mind_elapsed >= threshold:
            new.append((key, label))
    return new
