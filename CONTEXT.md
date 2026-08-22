# IMPLUS: Current Context

Updated: 2026-08-22, Asia/Chita

## Production

- Server: `194.87.54.245`
- SSH port: `13471`, user `root`, password auth (the local `id_ed25519` key is
  not accepted)
- Application directory: `/opt/impplus`
- Service: `impplus.service`; nginx serves `frontend/dist`, ngrok fronts it
- Public URL: `https://pockily-trimorphic-hiroko.ngrok-free.dev/`
- Production commit: `d7a8d84 Make a stalled mind visible from outside the server`
- **Model provider: DeepSeek** (`deepseek-chat`) over the OpenAI-compatible API
- Secrets and access credentials are stored outside Git.
- Backup before the ontology migration:
  `/opt/impplus/backups/mind-20260821-020054.db`, SHA-256
  `54b4f7e482e2a63cb976ff965c4335c1749bcc0fab5fcbeac0624a899b62b128`.
- Local Python is 3.9 and the project needs 3.10+. Run checks on the server
  with `/opt/impplus/.venv/bin/python3`, always against a copy of the database
  (`sqlite3.connect(src).backup(dst)` into `/tmp`), never against the live file.

## Cognition Stopped Twice in Five Days

**2026-08-17 to 08-21.** Groq retired the Llama family for this account. Every
cycle raised a 404 that the loop caught and swallowed. Four days of silence.

**2026-08-21 15:08 UTC to 08-22 00:00 UTC.** The Groq key expired
(`code: expired_api_key`). Seventeen failed cycles. The only symptom visible to
the operator was `Load failed` in the concept form.

Both outages looked identical from outside: service up, site 200, mind clock
advancing, thought stream silent. That is why the provider is now swappable and
why the loop reports its own health.

## The Five Silent Failures Found on 2026-08-21

Each became visible only after the previous one was repaired.

1. **Provider retired the models.** 404 swallowed by the loop.
2. **Reasoning tokens consumed the answer budget.** gpt-oss spent all 700
   tokens reasoning and returned empty content.
3. **A trailing colon in a concept name.** Exact-match lookup lost 1068 of 2094
   relation endpoints across 962 cycles; 958 of those were the single string
   `КОМБИНИРИСТИКА`.
4. **Zero placeholders in the prompt templates.** `"confidence": 0.0` was
   copied back by the model and rejected by the gate at 0.6. This also explains
   the critic reliability repeatedly coming out at zero.
5. **The dominant focus was an isolated node.** `Процесс генерации мысли` has
   degree 0, so the working set held one name while the prompt demanded
   relations between listed names. Cycles 968–976 each had a relation accepted
   at confidence 0.9 and discarded.

Across 962 cycles cognition had written exactly zero edges. The first one —
`КОМБИНИРИСТИКА — Процесс генерации мысли`, label `неразличимость`, confidence
1.00 — landed in cycle 977 on 2026-08-21 at 20:08 Asia/Chita.

## Structural Work

- **Provider abstraction** (`backend/mind_engine.py`): OpenAI SDK against any
  compatible endpoint. `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`,
  `LLM_MODEL_FAST`, falling back to the `GROQ_*` names.
- **Name matching** (`backend/name_matching.py`): normalized lookup plus a
  close-match fallback that refuses ambiguous candidates. Used by focus
  selection, relation endpoints, consolidation and the public API. Unmatched
  endpoints are logged — that log is what exposed failure 5.
- **Ontology cleanup** (`scripts/clean_ontology.py`): definitions moved out of
  names, service punctuation stripped, concepts identical after normalization
  merged. Applied: 33 renamed, 6 merged, 956 duplicate edges collapsed, 27
  trailing colons gone. Semantic near-duplicates are reported, never merged.
- **Prediction deadlines**: `horizon_days` on every prediction; stale ones
  expire and weaken the beliefs resting on them (0.85 on expiry, 0.55 on
  rebuttal). The 74 legacy predictions were given a deadline seven days out
  from 2026-08-21.
- **Observation matching**: an observation is matched against open predictions.
  Evidence must reuse the observation's own words (60% of tokens); at most 3
  close per observation from 5 candidates. Without that guard one observation
  closed 7 of 8 on its own restatement.
- **Exploration quota**: every fourth cycle picks its focus outside the inquiry
  queue, preferring the least grounded concepts. A focus stops accruing
  inquiries past 12.
- **Memory separation**: evidence retrieval uses reasoned event types only.
  Without it the candidate pool was 57 spontaneous rows out of 60.
- **Connection selection**: unconfirmed connections lose confidence, slower the
  more evidence they carry; a concept keeps at most `GRAPH_DEGREE_CAP`
  neighbours; neither path takes a node's last edge or pushes the graph below
  average degree 8. Daily, on a bounded budget. A 300-day simulation matched
  the first production pass exactly (17 decayed, 60 displaced).
- **Working set floor**: at least 12 names per cycle, topped up from concepts
  seen alongside the focus in memory and then from the least grounded.
- **Health reporting**: the loop records each successful cycle and the last
  failure; streaming endpoints answer a model failure with one readable
  sentence instead of a dropped connection. A concept whose analysis failed is
  not persisted.

## Configuration

All optional, code defaults in brackets:

- `LLM_BASE_URL` [`https://api.groq.com/openai/v1`] — production is set to
  `https://api.deepseek.com/v1`
- `LLM_API_KEY` (falls back to `GROQ_API_KEY`, `DEEPSEEK_API_KEY`)
- `LLM_MODEL` / `LLM_MODEL_FAST` [`openai/gpt-oss-120b` / `openai/gpt-oss-20b`]
  — production runs `deepseek-chat` for both
- `LLM_REASONING_EFFORT` [`low`] — applies only to `openai/gpt-oss*`; `medium`
  empirically overruns the budget and returns empty content
- `COGNITIVE_EXPLORATION_EVERY` [4]
- `GRAPH_SELECTION_INTERVAL_SECONDS` [86400], `GRAPH_SELECTION_BUDGET` [60],
  `GRAPH_DEGREE_CAP` [24]
- `MEMORY_INCLUDE_SPONTANEOUS` [unset] — set to 1 to restore the old pool

`.env.example` has not been updated: it carries unrelated uncommitted local
changes. The stale `GROQ_API_KEY` is still in the production `.env` and is
ignored, since `LLM_*` takes precedence.

## State at 2026-08-22, 09:50 Asia/Chita

| Metric | Value |
|---|---|
| concepts | 169 |
| active_edges | 5173 |
| active_graph_density | 0.364 |
| cognitive_edges | 1 |
| decayed / displaced edges | 17 / 60 |
| top_label_share | 0.284 |
| grounded_concepts | 17 (10.1%) |
| open_inquiries | 967 |
| pending_predictions | 83 |
| expired / resolved predictions | 0 / 0 |
| prediction_brier_score | null |
| cognitive_cycles | 985 |
| latest_daily_insight_date | 2026-08-21 |

Cycle 985 ran on DeepSeek at 09:40 with verdict `revise`. Health fields are
populated and `cognition_stalled` is false.

Grounding coverage is moving fast under the operator's own input: 4.2% on the
morning of 21 August, 7.8% that evening, 10.1% the next morning.

## Emergence Criteria

Four measurable conditions:

1. `prediction_brier_score` below 0.25 over at least 50 resolved predictions —
   **null**, needs observations through the ПРОВЕРКА tab.
2. Density falling while `cognitive_edges` rises — **both halves moved**:
   0.379 → 0.364, edges 0 → 1.
3. `top_label_share` below 0.30 — **0.284**, formally met but weak while the
   graph is still dense.
4. A relation accepted between two concepts that never appeared together in an
   inquiry — **not yet**; this is the real test of inference.

The binding constraint is grounding coverage. Structure formation needs roughly
30%. Without external observations the loop has no error signal at all.

## Next Checks

- Whether DeepSeek is too strict a critic. It rejected on a test cycle where
  gpt-oss accepted at 0.9. Watch `cognitive_edges` and `accepted_cycle_rate`
  over a few days; if edges stay at 1, reconsider the gates rather than the
  model.
- 2026-08-28: first wave of prediction expiry; belief confidence should start
  to spread away from 1.00.
- Connection selection reaches the degree cap in roughly 58 days at the default
  budget, then settles at the floor of 668 edges.
- Telegram delivers the daily insight at 21:40 Asia/Chita with retries at 21:55
  and 22:10. Insights for 17–20 August are permanently missing.
- A "mind is silent" banner on the site itself is still not built: it needs a
  React change and a `dist` rebuild, and `ContemplationView.tsx` carries
  uncommitted local edits. Resolve those first.

## Operating the Mind

Daily input is what moves everything. On the **ПРОВЕРКА** tab an observation
must contain a quotable fact — the matcher requires 60% word overlap between
its evidence quote and the observation, so abstract statements close nothing.
Reliability below 0.6 excludes the observation from consolidation. On the
**БИБЛИОТЕКА → Основание** tab a fragment grounds a concept. New concepts
should be rare: each one lowers coverage and pushes the threshold away.

## Working Tree

Unrelated local changes, deliberately left untouched:

- `.env.example`
- `README.md`
- `frontend/src/views/ContemplationView.tsx`
- `scripts/mac-start.sh`
- `scripts/setup.sh`
- untracked `AGENTS.md`
- untracked `backups/`

Do not discard or overwrite those files without reviewing them with the user.
