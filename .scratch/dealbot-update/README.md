# Dealbot update: write to data/deals.json instead of Excel

Once `startup-tracker` is merged into `main`, the site reads its deals from
`data/deals.json`. The old dealbot scripts would break it:

- `publish.py` rebuilds the page from Excel and copies it over `index.html`, undoing the new page.
- `run.py` (through `score.py`) reads the deal list out of the page's HTML, which is no longer there, so it crashes.
- `review.py` writes approved deals to `Startup Activity.xlsx`, which the site no longer reads.

## What changes

Replace these three files in `/Users/sidkhetan/dealbot` with the ones in this folder:

| File | Change |
|---|---|
| `run.py` | Skips articles already in the live `data/deals.json`. No scoring (the page scores deals itself). |
| `review.py` | Same keep/skip questions. Approved deals go into `data/deals.json` through `scripts/add_deals.py`. If a city, round type, new sector or amount isn't recognised, it asks you to type it. Excel is no longer touched. |
| `publish.py` | Checks the data, then commits and pushes the data files only. No page rebuild. |

`weekly.sh`, `fetch_news.py` and `extract.py` stay as they are. `score.py`,
`refresh_dashboard.py` and the Excel file are no longer used.

## When to switch

Swap the files right after `startup-tracker` is merged into `main`, and before
the next weekly run. Before the merge the new scripts won't work, because
`data/deals.json` isn't on `main` yet. After it the old ones will break the site.

Make sure `/Users/sidkhetan/startup-tracker` is on `main` (`git checkout main && git pull`).

## Weekly routine (unchanged)

1. `weekly.sh` runs and tells you how many deals are ready.
2. `python review.py`: answer y/n for each deal, type any missing details it asks for, then say y to publish.

Adding deals by hand, e.g. ones Claude chat writes up: put them in a JSON list
with the same keys as `pending.json` and run, from the repo,
`python3 scripts/add_deals.py that-file.json`, then `python publish.py` from the dealbot folder.
