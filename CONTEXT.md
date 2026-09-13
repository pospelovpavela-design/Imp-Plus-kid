# IMPLUS: Current Context

Updated: 2026-09-13, Asia/Chita

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

**Three principles set by the operator, each after I got it wrong:**

1. **A grounding amplifies a concept; it is not an entry ticket.** A concept
   with a definition must work on its own. This exposed that the cycle received
   bare concept names — no definitions — which is why three months of output
   said "no distinguishing feature found".
2. **An explanation is accepted in the form it is given.** Strictness belongs to
   falsification, not to the intake of knowledge. Demanding lab-protocol answers
   meant three operator explanations in a row taught the mind nothing.
3. **External material is raw experience, never an answer.** Web lookup (added
   13 September) enters through the grounding path with its URL kept, so what
   was reasoned can always be separated from what was read.

## Production

- Server `194.87.54.245`, SSH port `13471`, user `root`, password auth (the
  local `id_ed25519` key is not accepted)
- `/opt/impplus`, service `impplus.service`; nginx serves `frontend/dist`,
  ngrok fronts it
- `https://pockily-trimorphic-hiroko.ngrok-free.dev/`
- Production commit: `892b564 Keep the lookup off the event loop and off Wikipedia's back`
- Provider: **DeepSeek** (`deepseek-chat`) over the OpenAI-compatible API
- Backups in `/opt/impplus/backups/`
- Local Python is 3.9, the project needs 3.10+. Run checks on the server with
  `/opt/impplus/.venv/bin/python3`, always against a copy of the database
  (`sqlite3.connect(src).backup(dst)` into `/tmp`), never the live file. Do not
  leave scripts in `/tmp` named after stdlib modules — a stray `queue.py` once
  shadowed the standard library and broke every import.
- Frontend deploys by hand: `npm run build` locally, scp `dist/index.html` and
  `dist/assets/*`, remove the previous hashed assets.

## The Shape of Every Failure Here

Nothing fails loudly. The service stays up, the site returns 200, the stream
keeps producing fluent sentences, and the pipeline is dead. Ten blockers were
found this way, each visible only after the previous was repaired: retired
models; reasoning tokens eating the answer budget; a trailing colon in a concept
name; literal `0.0` placeholders copied back into a gate demanding ≥0.6; a focus
concept with degree 0; an expired API key; consolidation discarding truncated
JSON; predictions verifiable only by the mind's own memory; assimilation
silently dropping names absent from the graph; and a synchronous web fetch
inside the async loop. The last three were my own code, found within a day of
writing it.

**Diagnose by data, never by how the stream reads.** Count rows in
`relation_evidence`, edges by `source`, verdict distribution, focus diversity.
Log every silent loss explicitly.

## 13 September: Two Weeks Alone

The mind ran 14 days with zero operator input — no observations, no
contemplations, no concepts — and no failures.

| | 30 Aug | 13 Sep |
|---|---|---|
| distinct focuses | 17–24 per 60 cycles | **349 per 669** |
| density / cognition-written edges | 0.306 / 21 | **0.251 / 33** |
| novel pairs (never discussed together, never proposed) | 3 | **12** |
| active beliefs | 111 | **428** |
| self-retractions | 3 | **8** |
| Brier / resolved predictions | 0.125 / 2 | unchanged |

The backlog drain plus exploration every second cycle broke the focus lock for
good. Novel relations now span domains: `смерть — связь — Изменение как
процесс`, `Тригонометрическое тождество — похожесть — Сложение`, `связь между
мыслью и существованием — предполагает — случайность`.

It also learned to state the limit of its own knowledge, distinguishing
"the boundary was not observed" from "there is no boundary", and naming that as
a property of its corpus rather than of the world.

## What Was Added on 13 September

- **Label ripening threshold lowered to 2.** Five candidates in two weeks never
  reached three; the model's own "covered by" refusal is the real quality gate.
- **Web lookup** (`backend/web_lookup.py`): the mind takes an ungrounded
  concept, searches Russian Wikipedia by its name, and a relevance judgement
  decides whether the article is about the same thing its definition posits.
  Accepted material is stored as a grounding excerpt with author "Википедия" and
  the URL as source, then digested by the existing grounding analysis. Working
  definitions from it carry `source='web'`. One lookup per cycle, each concept
  attempted once (`cognitive_state` key `web_lookup:<id>`), disabled with
  `WEB_LOOKUP_ENABLED=0`.

**What the gate revealed.** It refuses most of Wikipedia, correctly: `полет` →
aerodynamics, `жизнь` → biology, `Эмоции` → embodied psychology, `локальность`
→ an ethnology term about marital residence. The mind has no body, so articles
about bodies describe a world it does not have. It accepts mathematics
(`Сложение`, `Вычитание`, `Сравнение`) where the subject really is the same, and
refuses where only the word matches — including philosophically: "my definition
makes understanding an act of the mind discovering the unknown, the text makes
it absorption of new content".

**Therefore the internet helps less than the operator does.** The encyclopedia
describes the human embodied world; this mind's concepts are about its own
reasoning. Operator explanations remain the only input that lands on target.

## Configuration

Optional, code defaults in brackets:

- `LLM_BASE_URL` [`https://api.groq.com/openai/v1`] — production runs
  `https://api.deepseek.com/v1`; `LLM_API_KEY`; `LLM_MODEL` / `LLM_MODEL_FAST`
  — production runs `deepseek-chat` for both
- `LLM_REASONING_EFFORT` [`low`] — only for `openai/gpt-oss*`
- `COGNITIVE_EXPLORATION_EVERY` [2], `AUTONOMOUS_LABEL_MIN_CYCLES` [2]
- `GRAPH_SELECTION_INTERVAL_SECONDS` [86400], `GRAPH_SELECTION_BUDGET` [60],
  `GRAPH_DEGREE_CAP` [24]
- `WEB_LOOKUP_ENABLED` [1], `MEMORY_INCLUDE_SPONTANEOUS` [unset]

## State at 2026-09-13

concepts 176 · active edges 3869 · density 0.251 · cognition edges 33 (43
touched, 8 retracted) · grounded 17 · defined 24 · open inquiries 1604 ·
predictions 33 pending / 2 resolved / 200 expired · Brier 0.125 · cycles 2034 ·
no stall, no errors.

## Emergence Criteria

1. **Falsifiability** — frozen. Two confirmations from the operator's
   "глюколизация" experiment, Brier 0.125, and **no prediction has ever been
   disconfirmed**. Two weeks produced 200 expiries and no resolutions because
   nobody answered. Until the mind is publicly wrong and retreats, this is not
   calibration.
2. **Structure** — met: density 0.379 → 0.251 while cognition-written edges went
   0 → 33.
3. **Differentiation** — `top_label_share` 0.282, under 0.30 but flat since the
   beginning. A badly chosen metric: it measures the legacy import.
4. **Inference** — 12 relations join concepts that never appeared together in
   any inquiry or focus and were never externally proposed. Caveat: both
   concepts sat in the same 12–36 name working set, so this is unprompted
   association within the available field, not inference across a gap.

## What to Watch Next

- The first disconfirmation. It is the one thing that has never happened, and
  it needs the operator to answer a prediction's test.
- Whether any label finally ripens into a concept at threshold 2. `инвариант`
  stands at two occurrences.
- Whether web lookup grounds anything at all in practice — the gate refuses most
  candidates by design.
- The inquiry queue regrew 473 → 1604 in two weeks; 236 of them are operator
  requests, so the per-focus cap does not hold once focuses diversify.
  `scripts/retire_inquiries.py` and `scripts/retire_requests.py` drain it.

## Operating the Mind

**Just explain, in your own words.** Every explanation sharpens definitions and
proposes relations; a three-word answer once produced a definition and a
relation. Protocol answers are needed only to falsify a prediction, not to
teach. On **ПРОВЕРКА → Разум спрашивает** the answer panel reports what was
understood, what was named but is not yet in the graph, and what stayed unclear.
Each cycle's reasoning is under ПРОВЕРКА → Ход мысли; a concept's own analysis
is on its card in БИБЛИОТЕКА.

The graph view on the site shows only nodes and edges **created** in the last 24
hours, so it reads empty while cognition is reinforcing existing edges.

## Working Tree

Unrelated local changes, deliberately left untouched: `.env.example`,
`README.md`, `scripts/mac-start.sh`, `scripts/setup.sh`, untracked `AGENTS.md`
and `backups/`. Do not discard them without reviewing with the user.
