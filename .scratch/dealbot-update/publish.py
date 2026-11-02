import subprocess, pathlib, sys
from datetime import datetime

REPO = pathlib.Path("/Users/sidkhetan/startup-tracker")
# Only the data changes now. The page (index.html) reads data/deals.json
# directly, so nothing is rebuilt and index.html is never touched here.
FILES = ["data/deals.json", "data/taxonomy.json", "data/fx_usdcad.csv"]


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0 and "nothing to commit" not in r.stdout:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def publish():
    # 1. check the data. The same check runs on GitHub after the push.
    r = subprocess.run([sys.executable, "scripts/validate.py"],
                       cwd=REPO, capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")
    if r.returncode != 0:
        raise RuntimeError("data check failed, nothing published:\n" + r.stdout)

    # 2. commit and push just the data files.
    run(["git", "add", *FILES], REPO)
    out = run(["git", "commit", "-m",
               f"Add deals {datetime.now():%Y-%m-%d}"], REPO)
    if "nothing to commit" in out:
        print("no changes to publish")
        return
    run(["git", "push"], REPO)
    print("pushed — live in ~1 min at "
          "https://sikandk.github.io/startup-tracker/")


if __name__ == "__main__":
    publish()
