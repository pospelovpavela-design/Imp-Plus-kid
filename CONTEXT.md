# IMPLUS: Current Context

Updated: 2026-08-21, Asia/Chita

## Production

- Server: `194.87.54.245`
- SSH port: `13471`
- Application directory: `/opt/impplus`
- Service: `impplus.service`
- Public URL: `https://pockily-trimorphic-hiroko.ngrok-free.dev/`
- Production commit: `fd6392f Stop dropping relations to concepts outside the working set`
- Secrets and access credentials are stored outside Git.
- Pre-migration backup: `/opt/impplus/backups/mind-20260821-020054.db`,
  SHA-256 `54b4f7e482e2a63cb976ff965c4335c1749bcc0fab5fcbeac0624a899b62b128`,
  `quick_check=ok`.

## What Happened on 2026-08-21

Cognition had been dead since 2026-08-17 17:28 Asia/Chita. The service stayed
up the whole time: the mind clock advanced, the site returned 200, and the
background loop woke every 30 minutes, failed, logged, and slept again.

Five separate failures were found. Each one only became visible after the
previous one was repaired, and none of them produced a visible symptom.

1. **Groq retired the Llama family for this account.** Every cycle raised a
   404, which the loop caught and swallowed. Four days of silence, four missed
   daily insights.
2. **Reasoning tokens consumed the answer budget.** The replacement models
   spend reasoning tokens from `max_tokens`. At 700 tokens the whole budget
   went to reasoning and the model returned empty content.
3. **A trailing colon in a concept name.** Relation endpoints were matched
   against the graph by exact name. `КОМБИНИРИСТИКА:` never matched what the
   model wrote. 1068 of 2094 endpoints were lost across 962 cycles; 958 of
   those losses were that single string.
4. **Zero placeholders in the prompt templates.** Every JSON template carried
   literal `"confidence": 0.0`, the model copied it back, and the gate at
   `confidence >= 0.6` rejected everything. This also explains the critic
   reliability repeatedly coming out at zero.
5. **The dominant focus was an isolated node.** `Процесс генерации мысли` has
   degree 0, so `relevant_names` returned a single name while the prompt
   demanded relations between listed names only. Cycles 968–976 each had the
   critic accept a relation at confidence 0.9 and each one was discarded.

Across 962 cycles cognition had written exactly zero edges into the graph.

## Structural Work Delivered the Same Day

- **Name matching** (`backend/name_matching.py`): normalized lookup plus a
  close-match fallback that refuses ambiguous candidates. Used for focus
  selection, relation endpoints, consolidation names and the public API.
  Unmatched endpoints are logged instead of silently dropped — this is what
  exposed failure 5.
- **Ontology cleanup** (`scripts/clean_ontology.py`): definitions moved out of
  concept names, service punctuation stripped, concepts identical after
  normalization merged. Applied to production: 33 renamed, 6 merged, 956
  duplicate edges collapsed, 11 self-loops removed, 27 trailing colons gone.
  Semantic near-duplicates are reported, never merged.
- **Prediction deadlines**: predictions carry `horizon_days`; stale ones expire
  and weaken the beliefs that rest on them (0.85 on expiry, 0.55 on rebuttal).
  All 74 legacy predictions were given a deadline seven days out from
  2026-08-21.
- **Observation matching**: an external observation is matched against open
  predictions. Evidence must reuse the observation's own words (60% of tokens),
  at most 3 predictions close per observation, from 5 candidates. Without that
  guard one observation closed 7 of 8 predictions on its own restatement.
- **Exploration quota**: every fourth cycle picks its focus outside the inquiry
  queue, preferring the least grounded concepts. A focus stops accruing
  inquiries past 12.
- **Memory separation**: evidence retrieval draws on reasoned event types only.
  Without it the candidate pool was 57 spontaneous rows out of 60.
- **Connection selection**: unconfirmed connections lose confidence (slower the
  more evidence they carry), a concept keeps at most `GRAPH_DEGREE_CAP`
  neighbours, and neither path takes a node's last active edge or pushes the
  graph below average degree 8. Runs daily on a bounded budget.
- **Working set floor**: the cycle now works with at least 12 names, topped up
  from concepts seen alongside the focus in memory and then from the least
  grounded ones.

## Configuration

New environment variables, all optional, code defaults in brackets:

- `GROQ_MODEL` [`openai/gpt-oss-120b`], `GROQ_MODEL_FAST` [`openai/gpt-oss-20b`]
- `GROQ_REASONING_EFFORT` [`low`] — `medium` empirically overruns the budget
  and returns empty content
- `COGNITIVE_EXPLORATION_EVERY` [4]
- `GRAPH_SELECTION_INTERVAL_SECONDS` [86400], `GRAPH_SELECTION_BUDGET` [60],
  `GRAPH_DEGREE_CAP` [24]
- `MEMORY_INCLUDE_SPONTANEOUS` [unset] — set to 1 to restore the old pool

`.env.example` has not been updated: it carries unrelated uncommitted local
changes.

## State at the End of 2026-08-21

| Metric | Value |
|---|---|
| concepts | 167 |
| active_edges | 5172 |
| active_graph_density | 0.373 |
| cognitive_edges | 0 |
| decayed_edges / displaced_edges | 17 / 60 |
| top_label_share | 0.284 |
| grounded_concepts | 13 (7.8%) |
| open_inquiries | 961 |
| pending_predictions | 79 |
| expired / resolved predictions | 0 / 0 |
| prediction_brier_score | null |
| cognitive_cycles | 976 |

The first connection selection pass ran on production and matched the
simulation exactly: 17 decayed, 60 displaced, density 0.379 → 0.373.

## Emergence Criteria

Four measurable conditions, none met yet:

1. `prediction_brier_score` below 0.25 over at least 50 resolved predictions.
2. Active density falling while `cognitive_edges` rises.
3. `top_label_share` below 0.30.
4. A cycle accepts a relation between two concepts that never appeared
   together in any inquiry.

The binding constraint is grounding coverage, currently 7.8%. Structure
formation needs roughly 30%, i.e. about 50 grounded concepts. At one fragment
a week that is roughly a year; at five a week, roughly two months. Without
external input the loop has no error signal and the asymptote is the current
state minus the noise.

## Next Checks

- Confirm `cognitive_edges` leaves zero. Every gate is now open; a background
  watch was running when this file was written.
- 2026-08-28: first wave of prediction expiry, belief confidence should start
  to spread away from 1.00.
- Watch whether relations keep being proposed at `reasoning_effort=low`. If
  cycles keep returning empty relation lists, try `medium` with a larger
  `max_tokens` rather than medium alone.
- Telegram delivery resumes at 21:40 Asia/Chita. Insights for 17–20 August are
  permanently missing; the engine only handles the current day.
- Connection selection reaches the degree cap in roughly 58 days at the default
  budget, then settles at the floor of 668 edges.

## Working Tree

The repository still carries unrelated local changes that were deliberately
left untouched:

- `.env.example`
- `README.md`
- `frontend/src/views/ContemplationView.tsx`
- `scripts/mac-start.sh`
- `scripts/setup.sh`
- untracked `AGENTS.md`
- untracked `backups/`

Do not discard or overwrite those files without reviewing them with the user.
