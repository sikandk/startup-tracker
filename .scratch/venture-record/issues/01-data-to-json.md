# 01 Move data out of the page into data/deals.json

Status: resolved

Migrate the embedded records to `data/deals.json` with taxonomy cleanup, company_id, dual-currency amounts, deduplication and flags. The page loads the JSON and computes the score. Validator and CI check.

## Answer

Done in "Move deal data out of the page into data/deals.json". 552 to 543 records (2 dropped, 7 merged). Records flagged `needs_review`: Tailscale 2026-03-18 (acquisition of Border0 recorded as a raise). Records with `region_unknown`: 8.
