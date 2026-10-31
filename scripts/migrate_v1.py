"""One-off migration: pull the deals embedded in the old index.html into data/deals.json.

Run once from the repo root:  python3 scripts/migrate_v1.py <path-to-old-index.html>

Kept in the repo so the cleanup rules are on record. It is not part of the daily job.
"""
import csv
import json
import re
import sys
import unicodedata
from bisect import bisect_right
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

US_THRESHOLD_USD_M = 50

TYPE_MAP = {
    "Startup Raising": "raise",
    "Startup Raising + Acquiring": "raise",
    "Startup Raising + M&A": "raise",
    "M&A": "ma",
    "M&A - SPAC": "ma",
    "Fund": "fund",
    "New Fund": "fund",
    "Startup IPO": "ipo",
}
# Not one of the four record types, or not a deal in the tracked period.
DROP = {
    ("Govt Contract", "Telesat / MDA Space"): "procurement contract, not a venture deal",
    ("Startup to watch", "KiXCare"): "profile of a 2021 round, not a deal in the tracked period",
}
# Hand fixes for records whose stored values are wrong.
FIXES = {
    "Seedcamp": {"amount_usd_m": 320.0, "roundsize": "USD 220 mil (fund VII) + USD 100 mil (Select Fund II)"},
}
NEEDS_REVIEW = {
    ("Tailscale", "2026-03-18"): "article is about Tailscale acquiring Border0 (2026-03-18); the $160M raise is from April 2025",
}

# Raw region text -> (display, subdivision, ISO country). Multi-location entries use the first-listed place.
R = {}
def reg(display, sub, country, *raws):
    for r in raws:
        R[r] = (display, sub, country)

reg("Toronto", "ON", "CA", "Toronto", "Toronto / Montréal", "Toronto / Kitchener-Waterloo", "Toronto + Germany", "Toronto + NYC", "Toronto / NYC")
reg("Montréal", "QC", "CA", "Montréal", "Montreal", "Montreal / SF", "Montreal + NYC")
reg("Vancouver", "BC", "CA", "Vancouver", "Vancouver and Toronto")
reg("Calgary", "AB", "CA", "Calgary", "Calgary and Toronto", "Calgary and Saskatoon")
reg("Kitchener-Waterloo", "ON", "CA", "Kitchener-Waterloo", "Kitchner/Waterloo", "Waterloo", "Kitchner + Phily")
reg("Ottawa", "ON", "CA", "Ottawa", "Ottawa / Brampton")
reg("Halifax", "NS", "CA", "Halifax")
reg("Saskatoon", "SK", "CA", "Saskatoon")
reg("St. John's", "NL", "CA", "St. John's")
reg("Edmonton", "AB", "CA", "Edmonton")
reg("Winnipeg", "MB", "CA", "Winnipeg")
reg("British Columbia", "BC", "CA", "BC")
reg("Richmond", "BC", "CA", "Richmond, BC", "Richmond")
reg("Fredericton", "NB", "CA", "Fredericton, NB", "Fredericton, New Brunswick")
reg("Québec", "QC", "CA", "Quebec")
reg("Québec City", "QC", "CA", "Québec City")
reg("New Minas", "NS", "CA", "New Minas, NS")
reg("Regina", "SK", "CA", "Regina")
reg("Victoria", "BC", "CA", "Victoria")
reg("Laval", "QC", "CA", "Laval")
reg("Sherbrooke", "QC", "CA", "Sherbrooke")
reg("Raymond", "AB", "CA", "Raymond")
reg("Hamilton", "ON", "CA", "Hamilton")
reg("Kingston", "ON", "CA", "Kingston")
reg("Dartmouth", "NS", "CA", "Dartmouth")
reg("Salmon Arm", "BC", "CA", "Salmon Arm")
reg("Guelph", "ON", "CA", "Guelph", "Guelph, Ont. / Irvine, Calif.")
reg("Burnaby", "BC", "CA", "Burnaby")
reg("Saint John", "NB", "CA", "Saint John")
reg("Delta", "BC", "CA", "Delta")
reg("Aurora", "ON", "CA", "Aurora")
reg("Brampton", "ON", "CA", "Brampton")
reg("Cambridge", "ON", "CA", "Cambridge")
reg("Canada", None, "CA", "Canada")

reg("San Francisco", "CA", "US", "San Francisco", "SF", "San Francisco, CA", "San Francisco / Toronto", "SF (Canadian founders)",
    "SF / Toronto / Miami", "San Francisco, CA / Tel Aviv, Israel")
reg("South San Francisco", "CA", "US", "South SF", "South San Francisco, CA")
reg("New York", "NY", "US", "New York", "NYC", "New York City", "New York, NY", "NYC (Canadian founders)", "New York, NY / Israel")
reg("Brooklyn", "NY", "US", "Brooklyn, NY")
reg("San Jose", "CA", "US", "San Jose", "San Jose, CA")
reg("Miami", "FL", "US", "Miami")
reg("Austin", "TX", "US", "Austin", "Austin, TX")
reg("Texas", "TX", "US", "Texas", "Texas + SF")
reg("California", "CA", "US", "California", "Cali", "California, US")
reg("Boston", "MA", "US", "Boston", "Boston, MA")
reg("Cambridge", "MA", "US", "Cambridge, Mass.", "Cambridge, MA")
reg("Massachusetts", "MA", "US", "Massachusetts")
reg("United States", None, "US", "USA", "US", "United States")
reg("Idaho", "ID", "US", "Idaho, US")
reg("Colorado", "CO", "US", "Colorado, US")
reg("North Carolina", "NC", "US", "North Carolina, US")
reg("Santa Fe Springs", "CA", "US", "Santa Fe Springs, Cali")
reg("Huntington Beach", "CA", "US", "Huntington Beach, CA")
reg("Independence", "OH", "US", "Independence, OH")
reg("South Pasadena", "CA", "US", "South Pasadena, CA")
reg("Houston", "TX", "US", "Houston, TX")
reg("Palo Alto", "CA", "US", "Palo Alto, CA")
reg("Seattle", "WA", "US", "Seattle, WA")
reg("Los Angeles", "CA", "US", "Los Angeles, CA")
reg("San Mateo", "CA", "US", "San Mateo, CA")
reg("Alameda", "CA", "US", "Alameda, CA")
reg("Silicon Valley", "CA", "US", "Silicon Valley, CA")
reg("Washington", "DC", "US", "Washington, DC", "Washington, D.C.")
reg("San Diego", "CA", "US", "San Diego, CA")
reg("Orlando", "FL", "US", "Orlando, FL")
reg("Santa Clara", "CA", "US", "Santa Clara, CA", "Santa Clara")
reg("Walnut Creek", "CA", "US", "Walnut Creek, CA")
reg("Illinois", "IL", "US", "Illinois")
reg("Torrance", "CA", "US", "Torrance, CA")
reg("Mountain View", "CA", "US", "Mountain View, CA")
reg("Rhode Island", "RI", "US", "Rhode Island")
reg("Incline Village", "NV", "US", "Incline Village, NV")
reg("Sunnyvale", "CA", "US", "Sunnyvale, CA", "Sunnyvale")
reg("Nashville", "TN", "US", "Nashville, TN")
reg("Kent", "WA", "US", "Kent, WA")
reg("Norcross", "GA", "US", "Norcross, GA")
reg("Laguna Beach", "CA", "US", "Laguna Beach, CA")
reg("Bastrop", "TX", "US", "Bastrop, TX")
reg("Reno", "NV", "US", "Reno, NV")
reg("Bellevue", "WA", "US", "Bellevue, WA")
reg("Redondo Beach", "CA", "US", "Redondo Beach, CA")
reg("Denver", "CO", "US", "Denver, CO")
reg("Ann Arbor", "MI", "US", "Ann Arbor", "Ann Arbor, MI")
reg("Wayne", "PA", "US", "Wayne, PA")
reg("Boulder", "CO", "US", "Boulder, CO")
reg("Dallas", "TX", "US", "Dallas, TX")
reg("El Segundo", "CA", "US", "El Segundo, CA")
reg("Longmont", "CO", "US", "Longmont")
reg("Columbus", "OH", "US", "Columbus, Ohio")
reg("New Haven", "CT", "US", "New Haven")

reg("United Kingdom", None, "GB", "UK", "United Kingdom")
reg("London", None, "GB", "London, UK")
reg("Oxford", None, "GB", "Oxford")
reg("Manchester", None, "GB", "Manchester")
reg("Tokyo", None, "JP", "Tokyo")
reg("Amsterdam", None, "NL", "Amsterdam")
reg("New Zealand", None, "NZ", "New Zealand")
reg("Finland", None, "FI", "Finland")
reg("Helsinki", None, "FI", "Helsinki, Finland")
reg("France", None, "FR", "France")
reg("Paris", None, "FR", "Paris, France", "Paris/Cali")
reg("Sydney", None, "AU", "Sydney")
reg("Copenhagen", None, "DK", "Copenhagen, Denmark")
reg("Sweden", None, "SE", "Swedish")
reg("Stockholm", None, "SE", "Stockholm, Sweden")
reg("Metzingen", None, "DE", "Metzingen, Germany")
reg("Munich", None, "DE", "Munich, Germany")
reg("Prague", None, "CZ", "Prague")
reg("Shanghai", None, "CN", "Shanghai / California")

reg("Undisclosed", None, None, "Undisclosed", "Global (Canadian co-founded)", "Grafton")


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_fx():
    rows = list(csv.DictReader(open(DATA / "fx_usdcad.csv")))
    return [r["date"] for r in rows], [float(r["usdcad"]) for r in rows]


FX_DATES, FX_RATES = load_fx()


def fx_on(d):
    """Rate on the date, or the most recent earlier business day."""
    i = bisect_right(FX_DATES, d) - 1
    if i < 0:
        raise ValueError(f"no FX rate on or before {d}")
    return FX_RATES[i], FX_DATES[i]


NUM = r"(\d[\d,]*(?:\.\d+)?)\s*-?\s*(bil|billion|b\b|mil|million|m\b)"


def parse_cad(roundsize):
    """CAD amount in millions when the round size is stated in CAD first, else None."""
    t = (roundsize or "").lower()
    m = re.search(r"cad\s*\$?\s*" + NUM, t) or re.search(r"\$?" + NUM + r"\s*cad", t)
    if not m or t.find("usd") != -1 and t.find("usd") < t.find("cad"):
        return None
    n = float(m.group(1).replace(",", ""))
    return n * 1000 if m.group(2).startswith("b") else n


# Distinct deals that the rules below would otherwise merge.
KEEP_APART = {("maritime-launch-services", "2025-10-31", "2025-11-03")}
# Same deal, but the amounts look different because one report omits the currency.
FORCE_MERGE = {("liora", "2025-08-06", "2025-08-07")}


def same_deal(a, b):
    """Is b (later) another report of deal a?

    M&A and IPOs happen once per company, so any later report is the same deal.
    Raises and funds must be within 30 days with compatible amounts.
    """
    if a["company_id"] != b["company_id"] or a["type"] != b["type"]:
        return False
    if (a["company_id"], a["date"], b["date"]) in KEEP_APART:
        return False
    if (a["company_id"], a["date"], b["date"]) in FORCE_MERGE:
        return True
    if a["type"] in ("ma", "ipo"):
        return True
    if date.fromisoformat(b["date"]) - date.fromisoformat(a["date"]) > timedelta(days=30):
        return False
    x, y = a["amount_usd_m"], b["amount_usd_m"]
    return x is None or y is None or abs(x - y) <= 0.15 * max(x, y)


def main(old_index):
    s = Path(old_index).read_text()
    i = s.find("const RAW = ") + len("const RAW = ")
    raw, _ = json.JSONDecoder().raw_decode(s[i:])

    out, dropped, used_regions = [], [], set()
    for x in raw:
        if (x["type"], x["name"]) in DROP:
            dropped.append((x["name"], DROP[(x["type"], x["name"])]))
            continue
        t = TYPE_MAP[x["type"]]
        display, sub, country = R[x["region"]]
        used_regions.add((display, sub, country))
        fix = FIXES.get(x["name"], {})
        roundsize = fix.get("roundsize", x["roundsize"])

        rate, rate_date = fx_on(x["date"])
        usd = fix.get("amount_usd_m", x["amount_m"])
        cad = None
        cad_stated = parse_cad(roundsize)
        if cad_stated is not None and usd and 1.15 < cad_stated / usd < 1.65:
            # Stated in CAD: keep the CAD figure, re-derive USD at the day's rate.
            cad = cad_stated
            usd = cad / rate
        elif usd is not None:
            cad = usd * rate

        flags = []
        if (x["name"], x["date"]) in NEEDS_REVIEW:
            flags.append("needs_review")
        if country == "US" and t == "raise" and (usd is None or usd < US_THRESHOLD_USD_M):
            flags.append("below_us_threshold")
        if country is None:
            flags.append("region_unknown")

        out.append({
            "date": x["date"],
            "type": t,
            "name": x["name"],
            "company_id": slug(x["name"]),
            "stage": x["stage"],
            "sector": x["sector"],
            "sector_group": x["sector_group"],
            "region": display,
            "subdivision": sub,
            "country": country,
            "roundsize": roundsize,
            "amount_usd_m": None if usd is None else round(usd, 2),
            "amount_cad_m": None if cad is None else round(cad, 2),
            "fx_usdcad": rate if usd is not None else None,
            "fx_date": rate_date if usd is not None else None,
            "note": x["note"],
            "sources": [x["source"]] if x["source"] else [],
            "flags": flags,
        })

    out.sort(key=lambda r: (r["date"], r["name"]))
    merged = []
    for r in out:
        prev = next((m for m in reversed(merged) if same_deal(m, r)), None)
        if prev:
            prev["sources"] += [u for u in r["sources"] if u not in prev["sources"]]
            for k in ("amount_usd_m", "amount_cad_m", "fx_usdcad", "fx_date", "roundsize"):
                if prev[k] is None and r[k] is not None:
                    prev[k] = r[k]
            prev.setdefault("_merged", []).append(r["date"])
            continue
        merged.append(r)

    seen_ids = {}
    for r in merged:
        base = f'{r["date"]}-{r["company_id"]}-{r["type"]}'
        n = seen_ids.get(base, 0)
        seen_ids[base] = n + 1
        r["id"] = base if n == 0 else f"{base}-{n + 1}"
        merged_dates = r.pop("_merged", None)
        if merged_dates:
            print("merged:", r["id"], "<-", merged_dates)

    keyed = [{"id": r.pop("id"), **r} for r in merged]
    (DATA / "deals.json").write_text(json.dumps(keyed, indent=1, ensure_ascii=False) + "\n")

    regions = sorted(({"region": d, "subdivision": s, "country": c} for d, s, c in used_regions),
                     key=lambda r: (r["country"] or "~", r["subdivision"] or "", r["region"]))
    tax = json.loads((DATA / "taxonomy.json").read_text())
    tax["regions"] = regions
    (DATA / "taxonomy.json").write_text(json.dumps(tax, indent=1, ensure_ascii=False) + "\n")

    print(len(raw), "in ->", len(keyed), "out;", len(dropped), "dropped;", len(out) - len(merged), "merged")
    for n, why in dropped:
        print("dropped:", n, "-", why)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "index.html")
