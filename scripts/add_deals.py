"""Add new deals to data/deals.json.

Takes deals in the dealbot's pending.json format (the keys review.py shows:
Date, Type, Name, Roundsize (usd), Round Type, Sector, Region, Note, Source)
and fills in what deals.json needs: id, company_id, stage, sector_group,
region/subdivision/country, USD and CAD amounts, flags. A report of a deal
we already have is merged into it instead of added twice. The result is
checked with validate.py before it is saved.

Command line (adds every row it can, lists the ones it can't):
    python3 scripts/add_deals.py pending.json

From Python (review.py uses this):
    from add_deals import prepare, add
    record, problems = prepare(row)   # problems: {field: message}; empty when ready
    add([record, ...])                # writes deals.json, returns a line per deal

Fixing a problem: change that field in the row and call prepare() again.
- Region: a known city ("Toronto"), or a new one as "City, SUB, CC"
  e.g. "Kelowna, BC, CA" or "Lisbon, , PT". New ones are added to taxonomy.json.
- Round Type: one of the stages in taxonomy.json.
- Sector Group: one of the sector groups in taxonomy.json (asked only for a
  sector the tracker hasn't seen before).
- Roundsize (usd): an amount it can read, e.g. "USD 12 mil" or "CAD 3.5 mil".
"""
import csv
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import migrate_v1 as m  # region names, slugs, FX lookup, same-deal rule
from validate import validate

DATA = m.DATA
DEALS = DATA / "deals.json"
TAX = DATA / "taxonomy.json"
FX = DATA / "fx_usdcad.csv"

TYPES = {**m.TYPE_MAP, "raise": "raise", "ma": "ma", "fund": "fund", "ipo": "ipo",
         "Acquisition": "ma", "IPO": "ipo"}

STAGE_WORDS = [  # (pattern, stage), first match wins
    (r"pre-?seed", "Pre-Seed"),
    (r"\bseed\b", "Seed"),
    (r"series\s*([a-h])\b", None),  # -> "Series X"
    (r"\bgrowth\b", "Growth"),
    (r"debt|credit|loan", "Debt"),
    (r"private equity", "Private Equity"),
    (r"strategic", "Strategic"),
    (r"acqui|merger", "Acquisition"),
    (r"\bipo\b", "IPO"),
    (r"\bfund\b", "Fund"),
    (r"bridge", "Bridge"),
    (r"grant|government", "Grant / Government"),
    (r"reverse takeover|\brto\b", "Reverse Takeover"),
    (r"^\s*$|undisclosed|unknown|n/?a", "Undisclosed"),
]


def load():
    return json.loads(DEALS.read_text()), json.loads(TAX.read_text())


def known_sources(deals=None):
    """Every article URL already in the tracker."""
    deals = deals if deals is not None else load()[0]
    return {u for d in deals for u in d["sources"]}


# ---------- field mapping ----------

def map_stage(text, tax):
    t = (text or "").strip()
    for s in tax["stages"]:
        if t.lower() == s.lower():
            return s
    for pat, stage in STAGE_WORDS:
        hit = re.search(pat, t.lower())
        if hit:
            return stage or f"Series {hit.group(1).upper()}"
    return None


def map_sector_group(sector, given, deals, tax):
    groups = {g.lower(): g for g in tax["sector_groups"]}
    if given and given.strip().lower() in groups:
        return groups[given.strip().lower()]
    seen = {d["sector"].lower(): d["sector_group"] for d in deals if d["sector"]}
    return seen.get((sector or "").strip().lower())


def map_region(text, tax):
    """(region, subdivision, country, is_new) or None."""
    t = (text or "").strip()
    if t in m.R:
        return (*m.R[t], False)
    for r in tax["regions"]:
        if t.lower() == r["region"].lower():
            return r["region"], r["subdivision"], r["country"], False
    parts = [p.strip() for p in t.split(",")]
    if len(parts) == 3 and parts[0] and re.fullmatch(r"[A-Za-z]{2}", parts[2]):
        return parts[0], parts[1].upper() or None, parts[2].upper(), True
    return None


NUM = r"(\d[\d,]*(?:\.\d+)?)\s*-?\s*(billion|bil|b\b|million|mil|m\b|k\b|thousand)?"


def to_millions(n, unit):
    n = float(n.replace(",", ""))
    unit = (unit or "").lower()
    if unit.startswith("b"):
        return n * 1000
    if unit.startswith("m"):
        return n
    if unit in ("k", "thousand"):
        return n / 1000
    return n / 1e6 if n >= 1000 else n  # "$190,000" is a plain figure; "$12" means millions


def parse_amount(roundsize):
    """("USD" | "CAD", millions) for the amount as written, None if undisclosed.

    Raises ValueError when there is a number it can't read safely.
    No currency stated counts as USD, as in the existing data.
    """
    t = (roundsize or "").strip().lower()
    if not t or "undisclosed" in t or not re.search(r"\d", t):
        return None
    if re.search(r"pound|£|euro|€|gbp|eur\b|yen|¥", t) and not re.search(r"usd|cad", t):
        raise ValueError(f"amount isn't in USD or CAD: {roundsize!r}")
    cad = m.parse_cad(roundsize)
    if cad is not None:
        return "CAD", cad
    hit = re.search(r"usd\s*\$?\s*" + NUM, t) or re.search(r"\$?\s*" + NUM, t)
    if not hit:
        raise ValueError(f"can't read amount {roundsize!r}")
    return "USD", to_millions(hit.group(1), hit.group(2))


# ---------- exchange rates ----------

_fx_tried = False


def ensure_fx(upto):
    """Make sure fx_usdcad.csv covers the date, fetching Bank of Canada rates if needed."""
    global _fx_tried
    if _fx_tried or (m.FX_DATES and m.FX_DATES[-1] >= upto):
        return
    _fx_tried = True
    start = m.FX_DATES[-1] if m.FX_DATES else "2025-01-01"
    url = f"https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?start_date={start}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            obs = json.load(r)["observations"]
    except Exception as e:  # offline, blocked, or format change: fall back to the last rate
        print(f"  note: couldn't fetch new USD/CAD rates ({e.__class__.__name__}); "
              f"using the latest stored rate ({start})")
        return
    new = [(o["d"], o["FXUSDCAD"]["v"]) for o in obs if o["d"] > start and o.get("FXUSDCAD")]
    if not new:
        return
    with open(FX, "a", newline="") as f:
        w = csv.writer(f)
        for d, v in new:
            w.writerow([d, f"{float(v):.4f}", "boc-valet"])
    m.FX_DATES, m.FX_RATES = m.load_fx()


# ---------- building a record ----------

def prepare(row, deals=None, tax=None):
    """Turn one pending.json row into a deals.json record.

    Returns (record, problems). The record is only usable when problems is empty.
    """
    if deals is None or tax is None:
        deals, tax = load()
    problems = {}

    d = str(row.get("Date", ""))[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        problems["Date"] = f"needs a YYYY-MM-DD date, got {row.get('Date')!r}"

    t = TYPES.get(str(row.get("Type", "")).strip())
    if not t:
        problems["Type"] = (f"unknown type {row.get('Type')!r}; use one of: "
                            "Startup Raising, M&A, Fund, Startup IPO")

    name = str(row.get("Name", "")).strip()
    if not name:
        problems["Name"] = "missing company name"

    stage = map_stage(row.get("Round Type"), tax)
    if stage is None:
        problems["Round Type"] = (f"unknown round type {row.get('Round Type')!r}; "
                                  f"use one of: {', '.join(tax['stages'])}")

    sector = str(row.get("Sector", "")).strip() or "Unknown"
    group = map_sector_group(sector, row.get("Sector Group"), deals, tax)
    if group is None:
        problems["Sector Group"] = (f"new sector {sector!r}; pick its group: "
                                    f"{', '.join(tax['sector_groups'])}")

    reg = map_region(row.get("Region"), tax)
    if reg is None:
        problems["Region"] = (f"unknown region {row.get('Region')!r}; type a known city, "
                              "or a new one as 'City, SUB, CC' (e.g. 'Kelowna, BC, CA')")
        reg = (None, None, None, False)
    region, sub, country, new_region = reg

    roundsize = str(row.get("Roundsize (usd)", "") or "").strip() or "Undisclosed"
    try:
        amt = parse_amount(roundsize)
    except ValueError as e:
        problems["Roundsize (usd)"] = f"{e}; type it as e.g. 'USD 12 mil' or 'CAD 3.5 mil'"
        amt = None

    usd = cad = rate = rate_date = None
    if amt and "Date" not in problems:
        ensure_fx(d)
        rate, rate_date = m.fx_on(d)
        cur, n = amt
        usd, cad = (n, n * rate) if cur == "USD" else (n / rate, n)

    source = str(row.get("Source", "")).strip()
    if source and not source.startswith("http"):
        problems["Source"] = f"source must be a URL, got {source!r}"

    flags = []
    if t == "raise" and country == "US" and (usd is None or usd < m.US_THRESHOLD_USD_M):
        flags.append("below_us_threshold")
    if region is not None and country is None:
        flags.append("region_unknown")

    rec = {
        "date": d,
        "type": t,
        "name": name,
        "company_id": m.slug(name),
        "stage": stage,
        "sector": sector,
        "sector_group": group,
        "region": region,
        "subdivision": sub,
        "country": country,
        "roundsize": roundsize,
        "amount_usd_m": None if usd is None else round(usd, 2),
        "amount_cad_m": None if cad is None else round(cad, 2),
        "fx_usdcad": rate if usd is not None else None,
        "fx_date": rate_date if usd is not None else None,
        "note": str(row.get("Note", "")).strip(),
        "sources": [source] if source else [],
        "flags": flags,
    }
    if new_region:
        rec["_new_region"] = True
    return rec, problems


# ---------- saving ----------

def add(records):
    """Add prepared records to deals.json. Returns a line of text per record."""
    deals, tax = load()
    before_deals, before_tax = DEALS.read_text(), TAX.read_text()
    have = known_sources(deals)
    ids = {d["id"] for d in deals}
    report = []

    for r in records:
        r = dict(r)
        if r.pop("_new_region", False):
            key = {"region": r["region"], "subdivision": r["subdivision"], "country": r["country"]}
            if key not in tax["regions"]:
                tax["regions"].append(key)
                report.append(f"new region added: {r['region']}, {r['subdivision'] or ''}, {r['country']}")

        if r["sources"] and set(r["sources"]) & have:
            report.append(f"skipped {r['name']}: article already in the tracker")
            continue

        # Another report of a deal we already have? (rules in migrate_v1.same_deal)
        earlier = [d for d in deals if d["date"] <= r["date"] and m.same_deal(d, r)]
        later = [d for d in deals if d["date"] > r["date"] and m.same_deal(r, d)]
        match = (earlier or later or [None])[-1]
        if match:
            match["sources"] += [u for u in r["sources"] if u not in match["sources"]]
            for k in ("amount_usd_m", "amount_cad_m", "fx_usdcad", "fx_date", "roundsize"):
                if match[k] is None or (k == "roundsize" and match[k] == "Undisclosed"):
                    match[k] = r[k]
            have |= set(r["sources"])
            report.append(f"merged {r['name']} into existing deal {match['id']}")
            continue

        base = f"{r['date']}-{r['company_id']}-{r['type']}"
        n, rid = 1, base
        while rid in ids:
            n += 1
            rid = f"{base}-{n}"
        ids.add(rid)
        have |= set(r["sources"])
        deals.append({"id": rid, **r})
        report.append(f"added {rid}")

    deals.sort(key=lambda x: (x["date"], x["name"]))
    tax["regions"].sort(key=lambda x: (x["country"] or "~", x["subdivision"] or "", x["region"]))
    errs = validate(deals, tax)
    if errs:
        DEALS.write_text(before_deals)
        TAX.write_text(before_tax)
        raise ValueError("not saved, the data didn't pass validate.py:\n  " + "\n  ".join(errs))
    DEALS.write_text(json.dumps(deals, indent=1, ensure_ascii=False) + "\n")
    TAX.write_text(json.dumps(tax, indent=1, ensure_ascii=False) + "\n")
    return report


def main(path):
    rows = json.loads(Path(path).read_text())
    deals, tax = load()
    ready, stuck = [], []
    for row in rows:
        rec, problems = prepare(row, deals, tax)
        (stuck if problems else ready).append((row, rec, problems))
    for line in add([rec for _, rec, _ in ready]) if ready else []:
        print(line)
    for row, _, problems in stuck:
        print(f"NOT ADDED {row.get('Name')!r}:")
        for field, msg in problems.items():
            print(f"  {field}: {msg}")
    return 1 if stuck else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
