# IMPLUS: Current Context

Updated: 2026-07-30, Asia/Chita

## Production

- Server: `194.87.54.245`
- SSH port: `13471`
- Application directory: `/opt/impplus`
- Service: `impplus.service`
- Public URL: `https://pockily-trimorphic-hiroko.ngrok-free.dev/`
- Production commit: `00ad044 Add one evidence-based daily insight`
- Secrets and access credentials are stored outside Git.

## Latest Release

The Stream view now has two sub-tabs:

- `Поток`: the existing event stream.
- `Итог дня`: one resulting insight for each local calendar day.

The daily insight always starts with:

`Сегодня за день я понял, что...`

The implementation is centered in:

- `backend/daily_insight_engine.py`
- `backend/digest.py`
- `backend/db.py`
- `frontend/src/components/DailyInsightPanel.tsx`
- `frontend/src/views/StreamView.tsx`

## Daily Insight Algorithm

1. Use the `Asia/Chita` local calendar day unless `MIND_TIMEZONE` overrides it.
2. Collect reliable events, cognitive cycles, beliefs, and predictions from that day.
3. Generate one candidate conclusion from the selected evidence.
4. Run a separate critic pass to check grounding and conclusion quality.
5. Remove evidence identifiers that do not exist in the selected source records.
6. Normalize the required opening phrase.
7. Save the result atomically in `daily_insights` and `thought_stream`.
8. Enforce one result per day through the unique `local_date`.
9. Send only the insight text to Telegram and record `sent_at`.
10. Skip all later delivery attempts when `sent_at` is already present.

Generation can start after 21:00 local time. Telegram delivery attempts run at:

- 21:40 Asia/Chita
- 21:55 Asia/Chita
- 22:10 Asia/Chita

The retries are idempotent.

## Database

Schema version: `3`

The `daily_insights` table stores:

- local date and content
- confidence
- source event and cycle identifiers
- generation metadata
- matching stream event
- creation and Telegram delivery timestamps

Pre-release backup:

- `/opt/impplus/backups/mind-20260729-120854.db`
- SHA-256: `7484cd90fd6e28864b32cdaf4051ce48af501fd171d7c87505b33d27dfa403d3`

The backup was checked before migration:

- 172 concepts
- 13,381 concept connections
- 34,806 thought stream records
- 90 cognitive cycles
- FTS record count matched the thought stream
- SQLite `quick_check`: `ok`
- Cognitive invariants: valid

Automatic database backups are managed by the existing systemd timer.

## Release Verification

- Backend unit tests: 7 passed.
- Frontend TypeScript and Vite production build: passed.
- Production database migration: passed.
- Production SQLite `quick_check`: `ok`.
- Production cognitive invariants: valid.
- Public frontend: HTTP 200.
- Public `/mind/daily-insights` endpoint: working.
- First insight for 2026-07-29 was generated and sent once.

## Telegram Behavior

The previous graph, statistics, event list, image, and observer summary are no longer
sent by the current digest implementation. Telegram receives only the daily insight.

The installed crontab is sourced from:

`deploy/impplus-digest.cron`

## Working Tree

Before this context file was added, the repository already contained unrelated local
changes that were intentionally left untouched:

- `.env.example`
- `README.md`
- `frontend/src/views/ContemplationView.tsx`
- `scripts/mac-start.sh`
- `scripts/setup.sh`
- untracked `AGENTS.md`
- untracked `backups/`

Do not discard or overwrite those files without reviewing them with the user.

## Next Checks

- Confirm that a new daily insight appears after 21:00 for each subsequent day.
- Watch whether critic confidence remains meaningful instead of repeatedly becoming zero.
- Review the language quality of conclusions and reduce unnecessary internal event IDs in
  user-facing text if they make the insight harder to read.
- Confirm that Telegram retries remain silent after a successful first delivery.
