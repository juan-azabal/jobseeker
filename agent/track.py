"""
Track applied and not-interested jobs using digest position numbers.

Usage (numbers match the digest output from the last run):

  python track.py applied 1 5 17        # mark jobs as applied (by company, 90d expiry)
  python track.py skip 3 8 12           # mark jobs as not interested (by ID)
  python track.py list                  # show current applied.yaml contents

Examples:
  After running main.py and seeing job #1 is Believe AdTech:
    python track.py applied 1

  To mark several noise jobs as not-interesting:
    python track.py skip 41 42 43

The script loads the latest output JSON, sorts it in the same order as the
digest (using main.py's ranked_jobs), then maps position numbers → job records.
"""

import json
import os
import sys
import glob
from datetime import date

import yaml


APPLIED_YAML = "config/applied.yaml"


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_latest_jobs():
    files = sorted(glob.glob("output/jobs_*.json"), reverse=True)
    files = [f for f in files if "rejected" not in f]
    if not files:
        print("❌  No output JSON found. Run main.py first.")
        sys.exit(1)
    with open(files[0]) as f:
        jobs = json.load(f)
    return jobs, files[0]


def _ranked_list(jobs):
    """Return jobs in digest order (same as main.py's ranked_jobs)."""
    # Import here to avoid circular deps; main.py has no side-effects at import
    from main import ranked_jobs
    tier_a, tier_b, tier_c = ranked_jobs(jobs)
    return tier_a + tier_b + tier_c


def _load_yaml():
    if not os.path.exists(APPLIED_YAML):
        return {"applied": {"companies": [], "ids": []}, "not_interested": {"ids": [], "titles": []}}
    with open(APPLIED_YAML) as f:
        data = yaml.safe_load(f) or {}
    # Ensure all expected keys exist
    data.setdefault("applied", {})
    data["applied"].setdefault("companies", [])
    data["applied"].setdefault("ids", [])
    data.setdefault("not_interested", {})
    data["not_interested"].setdefault("ids", [])
    data["not_interested"].setdefault("titles", [])
    return data


def _save_yaml(data):
    # Preserve the header comment by reading the raw file first
    header = ""
    if os.path.exists(APPLIED_YAML):
        with open(APPLIED_YAML) as f:
            lines = f.readlines()
        comment_lines = []
        for line in lines:
            if line.startswith("#") or line.strip() == "":
                comment_lines.append(line)
            else:
                break
        header = "".join(comment_lines)

    with open(APPLIED_YAML, "w") as f:
        if header:
            f.write(header)
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _existing_company_names(data):
    """Return set of lowercased company names already in applied.companies."""
    return {
        (e.get("name") or e).lower() if isinstance(e, dict) else str(e).lower()
        for e in (data["applied"].get("companies") or [])
    }


def _existing_skip_ids(data):
    return {
        (e.get("id") or e) if isinstance(e, dict) else str(e)
        for e in (data["not_interested"].get("ids") or [])
    }


def _existing_applied_ids(data):
    return {
        (e.get("id") or e) if isinstance(e, dict) else str(e)
        for e in (data["applied"].get("ids") or [])
    }


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_applied(positions):
    jobs, src = _load_latest_jobs()
    ranked = _ranked_list(jobs)
    today = date.today().isoformat()
    data = _load_yaml()
    existing = _existing_company_names(data)

    added = []
    skipped = []

    for pos in positions:
        idx = pos - 1
        if idx < 0 or idx >= len(ranked):
            print(f"  ⚠  #{pos} out of range (digest has {len(ranked)} jobs)")
            continue
        job = ranked[idx]
        company = job["company"]
        if company.lower() in existing:
            skipped.append(f"#{pos} {company} (already in list)")
            continue
        data["applied"]["companies"].append({"name": company, "date": today})
        existing.add(company.lower())
        added.append(f"#{pos} {job['title'][:45]} @ {company}")

    if added:
        _save_yaml(data)
        print(f"✅  Marked as applied ({today}):")
        for a in added:
            print(f"   {a}")
    if skipped:
        print(f"ℹ️   Already tracked:")
        for s in skipped:
            print(f"   {s}")

    print(f"\n   These companies will be filtered for 90 days.")


def cmd_skip(positions):
    jobs, src = _load_latest_jobs()
    ranked = _ranked_list(jobs)
    data = _load_yaml()
    existing = _existing_skip_ids(data)

    added = []
    skipped = []

    for pos in positions:
        idx = pos - 1
        if idx < 0 or idx >= len(ranked):
            print(f"  ⚠  #{pos} out of range (digest has {len(ranked)} jobs)")
            continue
        job = ranked[idx]
        job_id = job["id"]
        if job_id in existing:
            skipped.append(f"#{pos} {job['title'][:45]} @ {job['company']} (already skipped)")
            continue
        note = f"{job['title'][:40]} @ {job['company']}"
        data["not_interested"]["ids"].append({"id": job_id, "note": note})
        existing.add(job_id)
        added.append(f"#{pos} {note}")

    if added:
        _save_yaml(data)
        print(f"✅  Marked as not interested:")
        for a in added:
            print(f"   {a}")
    if skipped:
        print(f"ℹ️   Already tracked:")
        for s in skipped:
            print(f"   {s}")

    print(f"\n   These jobs will be filtered from future runs.")


def cmd_list():
    if not os.path.exists(APPLIED_YAML):
        print("No applied.yaml found.")
        return

    data = _load_yaml()
    today = date.today()

    companies = data["applied"].get("companies") or []
    app_ids = data["applied"].get("ids") or []
    skip_ids = data["not_interested"].get("ids") or []
    skip_titles = data["not_interested"].get("titles") or []

    print("\n── APPLIED ──────────────────────────────────────────")
    if companies:
        for e in companies:
            if isinstance(e, dict):
                name = e.get("name", "?")
                d = e.get("date", "?")
                try:
                    from datetime import datetime
                    age = (today - datetime.strptime(d, "%Y-%m-%d").date()).days
                    expires_in = 90 - age
                    status = f"expires in {expires_in}d" if expires_in > 0 else "⚠ expired"
                except Exception:
                    status = d
                print(f"   {name:30} {d}  ({status})")
            else:
                print(f"   {e}")
    else:
        print("   (none)")

    if app_ids:
        print("\n   Applied by ID:")
        for e in app_ids:
            if isinstance(e, dict):
                print(f"   {e.get('id')}  {e.get('note', '')}")
            else:
                print(f"   {e}")

    print("\n── NOT INTERESTED ───────────────────────────────────")
    if skip_ids:
        for e in skip_ids:
            if isinstance(e, dict):
                print(f"   {e.get('id')}  {e.get('note', '')}")
            else:
                print(f"   {e}")
    else:
        print("   (none)")

    if skip_titles:
        print("\n   Title patterns:")
        for t in skip_titles:
            print(f"   \"{t}\"")


def cmd_help():
    print(__doc__)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        cmd_help()
        return

    command = args[0].lower()
    rest = args[1:]

    if command == "list":
        cmd_list()

    elif command == "applied":
        if not rest:
            print("Usage: python track.py applied <number> [number ...]")
            sys.exit(1)
        try:
            positions = [int(x) for x in rest]
        except ValueError:
            print("❌  Positions must be integers, e.g.: python track.py applied 1 5 17")
            sys.exit(1)
        cmd_applied(positions)

    elif command == "skip":
        if not rest:
            print("Usage: python track.py skip <number> [number ...]")
            sys.exit(1)
        try:
            positions = [int(x) for x in rest]
        except ValueError:
            print("❌  Positions must be integers, e.g.: python track.py skip 3 8 12")
            sys.exit(1)
        cmd_skip(positions)

    else:
        print(f"❌  Unknown command: '{command}'")
        print("Commands: applied, skip, list")
        sys.exit(1)


if __name__ == "__main__":
    main()
