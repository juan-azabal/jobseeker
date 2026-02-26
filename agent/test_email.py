"""
Test script: re-score last run with new scorer and send email digest.
- Loads jobs from most recent output JSON (already parsed, skips scraping/parsing)
- Re-scores with gpt-4o-mini using full CV context
- Sends email via SMTP
- Does NOT update seen_ids (test mode)

Usage:
  python test_email.py              # use most recent output file, default profile
  python test_email.py --profile juan
  python test_email.py output/jobs_20260220_152226.json
"""

import json
import sys
import glob
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── resolve profile ──────────────────────────────────────────────────────────
from user_config import load_profile, list_profiles

profile_id = None
input_file = None

for arg in sys.argv[1:]:
    if arg == "--profile":
        pass  # handled next iteration
    elif sys.argv[sys.argv.index(arg) - 1] == "--profile" if arg and sys.argv.index(arg) > 0 else False:
        profile_id = arg
    elif arg.endswith(".json"):
        input_file = arg

# Simpler arg parse
args = sys.argv[1:]
if "--profile" in args:
    idx = args.index("--profile")
    if idx + 1 < len(args):
        profile_id = args[idx + 1]
# First positional arg that looks like a path
for arg in args:
    if arg.endswith(".json") or "/" in arg:
        input_file = arg
        break

if not profile_id:
    profile_id = list_profiles()[0]

profile = load_profile(profile_id)
print(f"Profile: {profile_id} ({profile['user']['name']})")

# ── find input file ──────────────────────────────────────────────────────────
if not input_file:
    files = sorted(glob.glob("output/jobs_*.json"), reverse=True)
    if not files:
        print("ERROR: No output files found in output/. Run main.py first.")
        sys.exit(1)
    input_file = files[0]

print(f"Loading: {input_file}")
with open(input_file) as f:
    jobs = json.load(f)

# Restore internal _salary_eur / _fit_score fields stripped by save_results
# (they'll be recomputed by ranked_jobs / notifier anyway — just need parsed)
parsed_jobs = [j for j in jobs if j.get("parsed")]
print(f"Jobs loaded: {len(jobs)} total, {len(parsed_jobs)} with parsed data")

# Clear any existing rag_score so we force a fresh score
for j in parsed_jobs:
    j.pop("rag_score", None)
    j.pop("rag_error", None)

# ── score with new scorer ────────────────────────────────────────────────────
from scorer import score_all, load_cv_text

cv_text = load_cv_text(profile)
print(f"CV loaded: {len(cv_text):,} chars")

start = time.time()
scored_jobs = score_all(parsed_jobs, profile=profile, cv_text=cv_text)
duration_score = int(time.time() - start)

n_scored = sum(1 for j in scored_jobs if j.get("rag_score"))
print(f"Scored {n_scored}/{len(scored_jobs)} jobs in {duration_score}s")

# ── send email ───────────────────────────────────────────────────────────────
from notifier import send_digest

# Fake prefilter stats (we're not running the full pipeline)
prefilter_stats = {
    "total": len(jobs),
    "passed": len(parsed_jobs),
    "already_seen": 0,
    "already_applied": 0,
    "not_interested": 0,
    "us_only": 0,
    "no_pm_keyword": 0,
    "deal_breaker": 0,
    "title_excluded": 0,
    "excluded_company": 0,
    "aggregator": 0,
    "wrong_language": 0,
}

run_meta = {
    "duration_s": duration_score,
    "cost_usd": round(n_scored * 0.002, 3),
    "n_searches": 0,
    "n_watchlist": 0,
    "date": datetime.now().strftime("%d %b %Y"),
}

print("\nSending email digest (test mode — seen_ids NOT updated)...")
ok = send_digest(scored_jobs, prefilter_stats, run_meta, profile=profile)
if ok:
    print("✅ Email sent successfully")
else:
    print("❌ Email failed — check GMAIL_ADDRESS / GMAIL_APP_PASSWORD in .env")
