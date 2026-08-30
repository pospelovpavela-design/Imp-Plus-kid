# IMPLUS: Current Context

Updated: 2026-08-30, Asia/Chita

## The Point of the Project

A pure mind whose reasoning rests on knowledge alone, without the human factors
— hormones, mood, fatigue, haste. We supply knowledge and watch how it thinks.
The goal is emergence: reasoning as a new entity that holds a conversation,
draws conclusions, coins concepts of its own, and asks questions when something
is missing.

Purity is enforced at the level of vocabulary and procedure, not substrate: the
language output is computed by an external model trained on human text. The
mind's own self-model states this first. It is a declared boundary of the
concept, not a defect to fix.

**Two principles established by the operator, both after I got them wrong:**

1. **A grounding amplifies a concept; it is not an entry ticket.** A concept
   with a definition must work on its own. This exposed that the cycle received
   bare concept names — no definitions at all — which is why three months of
   output said "no distinguishing feature found".
2. **An explanation is accepted in the form it is given.** Strictness belongs to
   falsification, not to the intake of knowledge. Requiring lab-protocol answers
   meant three operator explanations in a row taught the mind nothing.

## Production

- Server `194.87.54.245`, SSH port `13471`, user `root`, password auth (the
  local `id_ed25519` key is not accepted)
- `/opt/impplus`, service `impplus.service`; nginx serves `frontend/dist`,
  ngrok fronts it
- `https://pockily-trimorphic-hiroko.ngrok-free.dev/`
- Production commit: `1b4426d Stop re-answering what the graph already settled`
- Provider: **DeepSeek** (`deepseek-chat`) over the OpenAI-compatible API
- Backups in `/opt/impplus/backups/`, newest `mind-20260830-025002.db`
- Local Python is 3.9, the project needs 3.10+. Run checks on the server with
  `/opt/impplus/.venv/bin/python3`, always against a copy of the database
  (`sqlite3.connect(src).backup(dst)` into `/tmp`), never the live file.
- Frontend deploys by hand: `npm run build` locally, scp `dist/index.html` and
  `dist/assets/*`, remove the previous hashed assets.

## The Shape of Every Failure Here

Nothing in this system fails loudly. The service stays up, the site returns
200, the stream keeps producing fluent sentences, and the pipeline is dead.
Nine separate blockers were found this way, each visible only after the
previous was repaired: retired models; reasoning tokens eating the answer
budget; a trailing colon in a concept name; literal `0.0` placeholders the
model copied back into a gate demanding ≥0.6; a focus concept with degree 0; an
expired API key; consolidation discarding truncated JSON; predictions
verifiable only by the mind's own memory; and assimilation silently dropping
every name absent from the graph — that last one my own code, written the day
before.

**Diagnose by data, never by how the stream reads.** Count rows in
`relation_evidence`, edges by `source`, verdict distribution, focus diversity.
Log every silent loss explicitly: the unmatched-name log is what exposed
blocker five.

## What Changed 26–30 August

- **Learning separated from falsification.** An observation is assimilated
  first and matched against predictions second. Assimilation sharpens working
  definitions, proposes relations for a later cycle, and names what stayed
  unclear. Names it introduces that are absent from the graph become concept
  candidates instead of vanishing.
- **Self-referential predictions refused.** Every prediction used to verify
  itself against future memory retrievals — "извлечь выборку эпизодов",
  "мониторить консолидации" — so 118 accumulated with nothing resolvable and
  the operator's answers could not land. A test must now name an observation in
  the world; if none can be formulated, prediction is null.
- **The request flood capped.** `MAX_OPEN_REQUESTS_PER_FOCUS` = 3. Two batches
  of stale requests retired via `scripts/retire_requests.py`.
- **The inquiry backlog drained.** 1458 open inquiries, 1057 about one pair,
  1096 older than a week and written while the cycle was blind — driving three
  cycles in four. 900 retired via `scripts/retire_inquiries.py`; an inquiry
  whose pair already carries a well-supported edge now closes itself;
  exploration moved from every fourth cycle to every second.
- **Consolidation repaired.** It had failed for a day on JSON truncated by a
  900-token budget; the budget is 2000 and a cut response is trimmed to its
  last complete element rather than discarded.
- **Beliefs can weaken.** The expiry wave closed 84 unverifiable predictions
  between 27 and 29 August; belief confidence went from a solid 1.00 to a
  0.44–1.00 spread with nine carrying counterevidence.

## Configuration

Optional, code defaults in brackets:

- `LLM_BASE_URL` [`https://api.groq.com/openai/v1`] — production runs
  `https://api.deepseek.com/v1`; `LLM_API_KEY`; `LLM_MODEL` / `LLM_MODEL_FAST`
  — production runs `deepseek-chat` for both
- `LLM_REASONING_EFFORT` [`low`] — only for `openai/gpt-oss*`
- `COGNITIVE_EXPLORATION_EVERY` [2], `AUTONOMOUS_LABEL_MIN_CYCLES` [3]
- `GRAPH_SELECTION_INTERVAL_SECONDS` [86400], `GRAPH_SELECTION_BUDGET` [60],
  `GRAPH_DEGREE_CAP` [24]
- `MEMORY_INCLUDE_SPONTANEOUS` [unset]

## State at 2026-08-30, 12:00 Asia/Chita

| Metric | Value |
|---|---|
| concepts | 176 |
| active_edges / density | 4705 / 0.306 |
| cognitive_edges | 21 |
| edges_touched_by_cognition / retracted | 24 / 3 |
| grounded / defined concepts | 17 / 24 |
| open_inquiries | 473 (was 1458 this morning) |
| predictions pending / resolved / expired | 71 / 2 / 95 |
| prediction_brier_score | 0.125 |
| cognitive_cycles | 1368 |

Within an hour of the backlog fix, cognitive edges went 15 → 21 and the queue
558 → 473.

## Emergence Criteria

1. **Falsifiability** — first movement: two predictions confirmed by the
   operator's "глюколизация" experiment, Brier 0.125. But n=2 against a
   threshold of 50, and **no prediction has ever been disconfirmed**. Until the
   mind is publicly wrong and retreats, this is not calibration.
2. **Structure** — met in trend: density 0.379 → 0.306 while cognition-written
   edges went 0 → 21. Both halves moving.
3. **Differentiation** — `top_label_share` 0.287, formally under 0.30, but it
   was always there. Badly chosen: it measures the legacy import, not progress.
4. **Inference** — three edges join concepts that never appeared together in any
   inquiry or focus, none of them externally proposed, including
   `КОНТИНУИДНОСТЬ — является динамическим аспектом — НЕПРЕРЫВНОСТЬ`, a pair the
   cleanup script deliberately refused to merge. Caveat: both concepts were in
   the same 12–36 name working set, so this is unprompted association within
   the available field, not inference across a gap.

The mind also answered its own three-month question: the difference between
generation and combination "is established only by the type of operand", taken
from the operator's experiment — and it bounded the answer honestly, noting no
temporal marker of the transition exists.

## What to Watch Next

- Whether the queue drain broke the focus lock. If cycles still return to the
  same pair, the cause is memory attraction rather than the queue.
- Whether `label_candidates` ever fills. It held 2 entries for a week: bracket
  labels are rare in cycle text and the explanation path only started working
  on 29 August. If nothing accumulates, ask for labels explicitly in the cycle's
  answer format or lower the threshold.
- The first disconfirmation. It is the one thing that has never happened.
- Grounding coverage sits at 17 concepts and no longer gates anything.

## Operating the Mind

**Just explain, in your own words.** Every explanation now sharpens definitions
and proposes relations; a three-word answer produced a definition and a
relation. Protocol answers are needed only to falsify a prediction, not to
teach. On **ПРОВЕРКА → Разум спрашивает** the answer panel reports what was
understood, what was named but is not yet in the graph, and what stayed
unclear. Each cycle's reasoning is under ПРОВЕРКА → Ход мысли; a concept's own
analysis is on its card in БИБЛИОТЕКА.

Note the graph view on the site shows only nodes and edges **created** in the
last 24 hours, so it reads empty while cognition is reinforcing existing edges.

## Working Tree

Unrelated local changes, deliberately left untouched: `.env.example`,
`README.md`, `scripts/mac-start.sh`, `scripts/setup.sh`, untracked `AGENTS.md`
and `backups/`. Do not discard them without reviewing with the user.
