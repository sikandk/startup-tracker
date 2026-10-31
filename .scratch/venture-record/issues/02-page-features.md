# 02 Currency switcher, shareable URLs, deal links, correction links

Status: ready-for-agent
Blocked by: 01

- USD/CAD switcher: default USD, saved in localStorage (wrapped in try/catch), changes cards, table, modal, KPIs and charts together.
- Filters and currency in the URL query string; `#<deal id>` opens that deal.
- "Report a correction" in the deal modal opens `https://github.com/sikandk/startup-tracker/issues/new` with title and body prefilled with the deal id.
- Company history: in the modal, list other deals with the same `company_id`.
