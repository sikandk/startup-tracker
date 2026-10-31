"""Check data/deals.json against data/taxonomy.json. Exits non-zero on any problem.

Usage: python3 scripts/validate.py
"""
import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

REQUIRED = ["id", "date", "type", "name", "company_id", "stage", "sector", "sector_group",
            "region", "subdivision", "country", "roundsize", "amount_usd_m", "amount_cad_m",
            "fx_usdcad", "fx_date", "note", "sources", "flags"]
FLAGS = {"below_us_threshold", "region_unknown", "needs_review"}


def validate(deals, tax):
    errs = []
    regions = {(r["region"], r["subdivision"], r["country"]) for r in tax["regions"]}
    ids = set()
    for d in deals:
        who = d.get("id", d.get("name", "?"))
        def bad(msg):
            errs.append(f"{who}: {msg}")

        missing = [k for k in REQUIRED if k not in d]
        if missing:
            bad(f"missing {missing}")
            continue
        if d["id"] in ids:
            bad("duplicate id")
        ids.add(d["id"])
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["date"]):
            bad(f"bad date {d['date']!r}")
        if d["type"] not in tax["types"]:
            bad(f"unknown type {d['type']!r}")
        if d["stage"] not in tax["stages"]:
            bad(f"unknown stage {d['stage']!r}")
        if d["sector_group"] not in tax["sector_groups"]:
            bad(f"unknown sector_group {d['sector_group']!r}")
        if (d["region"], d["subdivision"], d["country"]) not in regions:
            bad(f"region not in taxonomy: {(d['region'], d['subdivision'], d['country'])}")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", d["company_id"]):
            bad(f"bad company_id {d['company_id']!r}")
        if not all(isinstance(u, str) and u.startswith("http") for u in d["sources"]):
            bad("sources must be URLs")
        if set(d["flags"]) - FLAGS:
            bad(f"unknown flags {set(d['flags']) - FLAGS}")
        usd, cad, fx = d["amount_usd_m"], d["amount_cad_m"], d["fx_usdcad"]
        if (usd is None) != (cad is None) or (usd is None) != (fx is None):
            bad("amount_usd_m, amount_cad_m and fx_usdcad must all be set or all be null")
        elif usd is not None and abs(usd * fx - cad) > max(0.02, 0.01 * cad):
            bad(f"USD {usd} x {fx} != CAD {cad}")
    return errs


if __name__ == "__main__":
    deals = json.loads((DATA / "deals.json").read_text())
    tax = json.loads((DATA / "taxonomy.json").read_text())
    errs = validate(deals, tax)
    for e in errs:
        print(e)
    print(f"{len(deals)} deals, {len(errs)} problems")
    sys.exit(1 if errs else 0)
