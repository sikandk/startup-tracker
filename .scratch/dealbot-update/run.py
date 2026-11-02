from email.utils import parsedate_to_datetime
import json, pathlib
import requests
from fetch_news import get_articles, looks_like_funding
from extract import extract

PENDING = pathlib.Path("pending.json")
SEEN = pathlib.Path("seen.json")

# The tracker's deal data. Every deal lists its source articles in "sources".
DEALS_URL = "https://sikandk.github.io/startup-tracker/data/deals.json"


def existing_sources():
    """URLs already in the live tracker, plus ones we've already processed."""
    deals = requests.get(DEALS_URL, timeout=20).json()
    urls = {u for d in deals for u in d["sources"]}

    if SEEN.exists():
        urls |= set(json.loads(SEEN.read_text()))
    return urls


def main():
    seen = existing_sources()
    arts = [a for a in get_articles(60) if looks_like_funding(a)]

    new = [a for a in arts if a["link"] not in seen]
    print(f"{len(arts)} candidates, {len(new)} not seen before\n")

    rows, skipped = [], []
    tok_in = tok_out = 0

    for a in new:
        r, usage = extract(a)
        tok_in += usage.input_tokens
        tok_out += usage.output_tokens
        seen.add(a["link"])

        if r.get("skip"):
            skipped.append((a["title"], r.get("why", "")))
            continue

        rows.append({
            "Date": parsedate_to_datetime(a["published"]).date().isoformat(),
            "Type": r["type"],
            "Name": r["name"],
            "Roundsize (usd)": r["roundsize"],
            "Round Type": r["round_type"],
            "Sector": r["sector"],
            "Fund Names": r.get("fund_names", ""),
            "Region": r["region"],
            "Note": r["note"],
            "Source": a["link"],
        })
        print(" +", r["name"], "|", r["roundsize"])

    PENDING.write_text(json.dumps(rows, indent=2))
    SEEN.write_text(json.dumps(sorted(seen)))

    print(f"\n{len(rows)} deals -> pending.json")
    print(f"{len(skipped)} skipped:")
    for t, w in skipped:
        print(f" - {t[:55]} ({w[:40]})")
    print(f"\ncost ${tok_in/1e6*0.10 + tok_out/1e6*0.50:.4f}")


if __name__ == "__main__":
    main()
