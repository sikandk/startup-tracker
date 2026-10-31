# Deal data

`deals.json` is the single source of truth for the tracker. The page loads it directly; nothing else needs rebuilding.

## License

The data in this folder is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Reuse it freely with credit to the Startup Tracker (https://sikandk.github.io/startup-tracker/). Summaries and classifications are our own; source articles are linked, never copied.

## Scope

- Every Canadian deal, plus US raises of USD 50M or more. Older US raises under that line stay but carry the `below_us_threshold` flag.
- Four record types: `raise`, `ma`, `fund`, `ipo`.
- From January 2025 onward.

## Fields

| Field | Meaning |
|---|---|
| `id` | Stable ID: `<date>-<company_id>-<type>` |
| `date` | Announcement date (first report) |
| `type` | `raise`, `ma`, `fund` or `ipo` |
| `name` | Company, target or fund name |
| `company_id` | Stable slug linking every deal for the same company |
| `stage` | From `taxonomy.json` → `stages` |
| `sector` | Free-text sub-sector, e.g. "Legal Tech" |
| `sector_group` | From `taxonomy.json` → `sector_groups` |
| `region`, `subdivision`, `country` | Headquarters. Must match an entry in `taxonomy.json` → `regions`. Multi-city companies use the first-listed city. `country` is ISO 3166-1 alpha-2 or null if unknown |
| `roundsize` | Amount as the source wrote it |
| `amount_usd_m`, `amount_cad_m` | Amount in millions in each currency. Whichever currency the source used is kept exact; the other is converted at `fx_usdcad` |
| `fx_usdcad`, `fx_date` | CAD per USD used for the conversion, and the rate's date (announcement date or the business day before) |
| `note` | Two-sentence summary we wrote |
| `sources` | Every article reporting this deal, earliest first |
| `flags` | `below_us_threshold`, `region_unknown`, `needs_review` |

Scores are not stored. The page calculates them from this file on every load.

## Other files

- `taxonomy.json`: the allowed values. `scripts/validate.py` rejects anything not listed.
- `fx_usdcad.csv`: daily USD/CAD rates used for conversions (US Federal Reserve H.10 series, via github.com/datasets/exchange-rates).
