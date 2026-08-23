# IMPLUS: Current Context

Updated: 2026-08-23, Asia/Chita

## The Point of the Project

A pure mind whose reasoning rests on knowledge alone, without the human
factors — hormones, mood, fatigue, haste. We supply knowledge and watch how it
thinks. The goal is emergence: reasoning as a new entity that holds a
conversation, draws conclusions, coins concepts of its own, and asks questions
when something is missing.

Purity is enforced at the level of vocabulary and procedure, not substrate: the
language output is computed by an external model trained on human text. The
mind's own self-model states this first. Treat it as a declared boundary of the
concept, not a defect to fix.

## Production

- Server: `194.87.54.245`, SSH port `13471`, user `root`, password auth (the
  local `id_ed25519` key is not accepted)
- Application directory `/opt/impplus`, service `impplus.service`; nginx serves
  `frontend/dist`, ngrok fronts it
- Public URL: `https://pockily-trimorphic-hiroko.ngrok-free.dev/`
- Production commit: `a1a16c5 Count edges by evidence and stop logging out on a hiccup`
- Model provider: **DeepSeek** (`deepseek-chat`) over the OpenAI-compatible API
- Backups: `/opt/impplus/backups/`, newest `mind-20260823-003227.db`
- Local Python is 3.9 and the project needs 3.10+. Run checks on the server with
  `/opt/impplus/.venv/bin/python3`, always against a copy of the database
  (`sqlite3.connect(src).backup(dst)` into `/tmp`), never the live file.
- Frontend deploys by hand: `npm run build` locally, then scp `dist/index.html`
  and `dist/assets/*` to `/opt/impplus/frontend/dist/`, removing the previous
  hashed assets.

## Two Outages, Five Silent Failures

Cognition stopped twice: 17–21 August (Groq retired the Llama family) and
21–22 August (the Groq key expired). Both looked identical from outside —
service up, site 200, mind clock advancing, stream silent. The provider is now
swappable and the loop reports its own health.

On 21 August five separate blockers were found, each visible only after the
previous was repaired: retired models; reasoning tokens eating the answer
budget; a trailing colon in a concept name losing 1068 of 2094 relation
endpoints; literal `0.0` placeholders in the prompt templates that the model
copied back into a gate demanding ≥0.6; and a focus concept with degree 0 whose
working set held a single name. Across 962 cycles cognition had written zero
edges.

## What 23 August Changed

The day started from a question — a concept was added and nothing visible
happened to it — and turned into a review of the whole concept against the
goal above.

- **Definitions reach the cycle.** The single most important fix. The cycle used
  to receive concept names and nothing else, while the prompt told it to treat
  anything ungrounded as an empty label. Three months of "no distinguishing
  feature found" were starvation, not thinking. The rule is now three-tiered:
  no definition is an empty label; a definition without grounding works fully,
  its content posited rather than observed; grounding adds experienced content
  on top. Missing grounding is no longer a reason to refuse a conclusion.
  **Grounding is an amplifier, not an entry ticket.**
- **The mind can ask us.** The critic fills `operator_request` when external
  fact is principally required. Such inquiries are excluded from focus selection
  — it cannot answer them itself. `GET /mind/requests`, `POST
  /mind/inquiries/{id}/answer` (the answer enters as an external observation and
  runs against open predictions), a "Разум спрашивает" tab, and one pending
  question appended to the daily Telegram message.
- **Contemplation is a conversation.** Threads carry `thread_id`; the last
  exchanges go into the prompt with an instruction to continue rather than
  restart and to ask outright when a clarification is missing.
- **Autonomous concepts are back, gated.** Creation died with the evidence-gated
  rewrite on 27 July; 39 of 168 concepts still carry `is_autonomous` and nothing
  had set it since. Bracket labels are now collected per cycle in
  `label_candidates`; one that recurs across `AUTONOMOUS_LABEL_MIN_CYCLES`
  distinct cycles, matches no existing concept and survives the model's own
  "covered by" refusal becomes a concept. On test it refused twice, correctly.
- **Operator proposals reach the cycle.** Adding a concept had always recorded
  its suggested relations as `proposed` evidence — 17 of them — and nothing read
  them. They now go into the candidate prompt to be confirmed or dropped on the
  evidence, and exploration visits concepts holding open proposals first.
- **Memory stays on the chosen focus.** Episodes tagged with a focus concept
  rank first; ones that merely say the word fill at most three slots; unrelated
  ones only when the focus turns up nothing. Cycle 1031 had chosen "Оценка
  государства ↔ прошлое" and reasoned about КОМБИНИРИСТИКА off eight episodes
  of the old obsession.
- **Duplicate concepts rejected.** The check compared names byte for byte, so
  «память» was accepted beside «Память» (degree 52) and «Добро» beside «добро»
  (degree 75). Both merged; the check now uses the resolver.
- **"Ход мысли" tab.** `/mind/cycles` had always returned the hypothesis, the
  critic's revision and reasoning, accepted and declined relations,
  contradictions, the next question and the memory episodes — and nothing in the
  interface called it.
- **Metrics count by evidence.** A retraction changes a connection's source, so
  `cognitive_edges` dropped to zero although the work happened. Added
  `edges_touched_by_cognition` and `retracted_edges`.
- **No logout on a hiccup.** Any bootstrap failure used to clear the session.

## Configuration

All optional, code defaults in brackets:

- `LLM_BASE_URL` [`https://api.groq.com/openai/v1`] — production runs
  `https://api.deepseek.com/v1`
- `LLM_API_KEY` (falls back to `GROQ_API_KEY`, `DEEPSEEK_API_KEY`)
- `LLM_MODEL` / `LLM_MODEL_FAST` — production runs `deepseek-chat` for both
- `LLM_REASONING_EFFORT` [`low`] — only for `openai/gpt-oss*`; `medium`
  empirically overruns the budget and returns empty content
- `COGNITIVE_EXPLORATION_EVERY` [4], `AUTONOMOUS_LABEL_MIN_CYCLES` [3]
- `GRAPH_SELECTION_INTERVAL_SECONDS` [86400], `GRAPH_SELECTION_BUDGET` [60],
  `GRAPH_DEGREE_CAP` [24]
- `MEMORY_INCLUDE_SPONTANEOUS` [unset] — set to 1 to restore the old pool

`.env.example` still carries unrelated uncommitted local edits.

## State at 2026-08-23, 10:50 Asia/Chita

| Metric | Value |
|---|---|
| concepts | 168 |
| active_edges / density | 5112 / 0.364 |
| cognitive_edges | 0 |
| edges_touched_by_cognition / retracted | 1 / 1 |
| grounded_concepts | 17 (10.1%) |
| open_inquiries | 1007 |
| pending_predictions | 96 |
| prediction_brier_score | null |
| cognitive_cycles | 1033 |
| cognition_stalled / last_cycle_error | false / none |

The first edge cognition ever wrote appeared in cycle 977 on 21 August
(`КОМБИНИРИСТИКА — Процесс генерации мысли`, label `неразличимость`) and the
mind retracted it a day later after 13 confirmations and 17 contradictions —
its first self-correction.

## What to Watch Next

- **Within a day:** the `needs_evidence` share, 25 of 46 cycles before the
  definitions fix — it should fall noticeably. Whether any request appears under
  "Разум спрашивает"; none in a day means the condition is too strict. Whether
  `edges_touched_by_cognition` grows.
- **2026-08-28:** first wave of prediction expiry; belief confidence should
  start to spread away from 1.00 on its own.
- **Within a week:** whether any label ever ripens into a concept. It refused
  twice on test, with argument. A hundred percent refusal rate means the gate
  needs loosening.
- **Connection selection** reaches the degree cap around mid-October at the
  default budget, then settles at the floor of 668 edges.
- `prediction_brier_score` moves only on observations carrying a quotable fact.
  The mind now names which ones it needs.

## Operating the Mind

On **ПРОВЕРКА** an observation must contain a quotable fact — the matcher
requires 60% word overlap between its evidence quote and the observation, so
abstract statements close nothing. Reliability below 0.6 excludes it from
consolidation. **БИБЛИОТЕКА → Основание** grounds a concept and multiplies what
it already means; it is not required for the concept to work. New concepts
should stay rare: each one lowers coverage. The concept analysis itself is on
the concept card in БИБЛИОТЕКА, and each cycle's reasoning is under ПРОВЕРКА →
Ход мысли.

## Working Tree

Unrelated local changes, deliberately left untouched: `.env.example`,
`README.md`, `scripts/mac-start.sh`, `scripts/setup.sh`, untracked `AGENTS.md`
and `backups/`. Do not discard them without reviewing with the user.
