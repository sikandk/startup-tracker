# startup-tracker

A continuously expanding record of North American venture activity: every Canadian deal plus US raises of $50M or more, from January 2025 onward.

Live at https://sikandk.github.io/startup-tracker/

- `index.html` + `styles.css`: the site (static, served by GitHub Pages)
- `data/deals.json`: the deal records, the single source of truth (see `data/README.md`; CC BY 4.0)
- `scripts/validate.py`: checks the data against `data/taxonomy.json`; runs on every push
- `scripts/migrate_v1.py`: one-off migration from the old page-embedded data, kept for the record
