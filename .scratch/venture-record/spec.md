# Venture record: spec

A free, mostly self-running public record of North American venture activity, grown from the existing tracker.

## Decisions

**Audience and ambition.** People following the ecosystem (founders, operators, journalists). Solo side project: no paid data sources, free hosting, only a few dollars a month of Claude API spend.

**Scope.** Every Canadian deal, plus US raises of USD 50M or more. US raises already recorded under $50M stay, flagged `below_us_threshold`. Four record types: `raise`, `ma`, `fund`, `ipo`. Forward-only from Jan 2025 (backfilling earlier years can come later with the same pipeline).

**Data.** `data/deals.json` is the single source of truth (the Excel workbook `Startup Activity.xlsx` is retired), licensed CC BY 4.0. Field reference: `data/README.md`.
- One record per deal with a `sources` list. Two reports are the same deal when company and type match and: M&A or IPO, at any distance in time; raise or fund, within 30 days with amounts within 15%. Uncertain matches go to review.
- Stable `company_id` links every deal for one company.
- `stage`, `sector_group` and region (`region`/`subdivision`/`country`) must come from `data/taxonomy.json`; `scripts/validate.py` enforces it. `sector` stays free text (353 distinct values; a fixed list would be the same as `sector_group`).
- Amounts are stored in both USD and CAD at the announcement-day rate; the source's own currency is kept exact.

**Score.** Not stored; computed on page load. It is the average of size (percentile among same-stage raises, needs at least 15 to compare) and momentum (the sector's share of raises in the 90 days before the deal vs the 90 days before that). "medium" means both signals were available, "partial" means one.

**Page.** A USD/CAD switcher (default USD, remembered per visitor) changes amounts, totals and charts. Filters and currency are kept in the URL; each deal has a link. Each deal has a "Report a correction" link that opens a prefilled GitHub issue.

**Pipeline.** A daily GitHub Actions job reads BetaKit (RSS/WordPress API) and Crunchbase News (RSS, funding posts only, US raises of $50M or more), extracts with the Claude API (`claude-haiku-5-5`), and stops after 50 articles a day. Confident records are committed straight to `main`; uncertain ones go into a PR. If no new records arrive for 3 days, it opens an issue automatically. The bot only touches `data/`. Code work happens on `startup-tracker` and is merged into `main` by hand.

**Hosting.** GitHub Pages from `main` (already live at sikandk.github.io/startup-tracker).

## Owner setup

- Repo secret `ANTHROPIC_API_KEY`; monthly spend limit (~$10) on the Anthropic account.
