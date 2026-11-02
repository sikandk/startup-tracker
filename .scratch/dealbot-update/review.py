import json, pathlib, subprocess, sys

REPO = pathlib.Path("/Users/sidkhetan/startup-tracker")
PENDING = pathlib.Path("pending.json")

sys.path.insert(0, str(REPO / "scripts"))
from add_deals import prepare, add  # noqa: E402  (lives in the repo)


def pull():
    """Get the latest data before adding to it, so the push doesn't clash."""
    r = subprocess.run(["git", "pull", "--ff-only"], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        print("git pull failed — sort this out in the repo first:\n" + r.stdout + r.stderr)
        sys.exit(1)


def fix(row):
    """Build the record, asking for anything the tracker can't work out."""
    while True:
        rec, problems = prepare(row)
        if not problems:
            return rec
        for field, msg in problems.items():
            print(f"\n  {field}: {msg}")
            val = input(f"  {field} (blank = drop this deal): ").strip()
            if not val:
                return None
            row[field] = val


def main():
    rows = json.loads(PENDING.read_text())
    if not rows:
        print("Nothing pending.")
        return

    keep = []
    for i, r in enumerate(rows, 1):
        print(f"\n{'='*60}\n[{i}/{len(rows)}] {r['Name']}")
        print(f" {r['Type']} | {r['Round Type']} | {r['Roundsize (usd)']}")
        print(f" {r['Sector']} | {r['Region']} | {r['Date']}")
        print(f" {r['Note'][:200]}")
        print(f" {r['Source'][:70]}")

        ans = input("\n keep? [y/n/a=accept rest/q] ").strip().lower()
        if ans == "q":
            print("stopped — nothing written")
            return
        if ans == "a":
            keep.extend(rows[i-1:])
            print(f" accepted remaining {len(rows)-i+1}")
            break
        if ans == "y":
            keep.append(r)

    print(f"\n{len(keep)} approved, {len(rows)-len(keep)} rejected")
    if not keep:
        PENDING.write_text("[]")
        return

    pull()
    records = []
    for r in keep:
        rec = fix(r)
        if rec is None:
            print(f"  dropped {r['Name']}")
        else:
            records.append(rec)

    if records:
        for line in add(records):
            print(" ", line)
    PENDING.write_text("[]")

    if records and input("\npublish to site? [y/n] ").strip().lower() == "y":
        from publish import publish
        publish()


if __name__ == "__main__":
    main()
