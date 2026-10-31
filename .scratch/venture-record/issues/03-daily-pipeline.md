# 03 Daily ingestion job

Status: ready-for-agent
Blocked by: 01

Port the dealbot scripts (fetch_news.py, wp_fetch.py, extract.py, run.py, from the owner's Drive) into `pipeline/`, writing to `data/deals.json` instead of Excel.
- Sources: BetaKit RSS; Crunchbase News RSS (funding posts; keep US raises of $50M or more).
- Extraction must output taxonomy values; anything off-list goes to review.
- Region/sector/stage normalisation: rebuild from `scripts/migrate_v1.py` (the original `refresh_dashboard.py` was not available).
- FX: Bank of Canada Valet FXUSDCAD, appended to `data/fx_usdcad.csv`.
- Dedup per the spec rules; uncertain matches go to review.
- `seen.json` equivalent kept in `data/` so articles are never processed twice.
- Workflow: daily cron, 50-article cap, confident records commit to `main`, others open a PR, auto-issue after 3 days with no new records.
