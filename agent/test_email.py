"""
Test script: fetch today's jobs from API and send email digest.
- Calls GET /api/digest/{profile_id} via Railway URL
- No local scoring — uses same code path as web app
- Does NOT update seen_ids (test mode)

Usage:
  python test_email.py              # default profile
  python test_email.py --profile juan

Manual checklist after running:
  [ ] Subject: "JobSeeker · N nuevos roles · ..."
  [ ] Preheader visible in inbox preview
  [ ] Header: violet dashboard button works
  [ ] Tier A: "Ver en JobSeeker →" primary CTA → opens platform job detail
  [ ] Tier A: "Oferta original →" secondary → opens external URL
  [ ] Tier A: NO strength/gap text
  [ ] Tier B/C: links go to platform
  [ ] Footer: "JobSeeker — Know your fit before you apply" + LinkedIn
  [ ] PARITY: scores match web "today" filter exactly
  [ ] PARITY: same jobs appear in same tiers as web
  [ ] PARITY: tier counts in email match web sidebar counts
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Default APP_BASE_URL if not in .env
if not os.getenv("APP_BASE_URL"):
    os.environ["APP_BASE_URL"] = "https://jobseeker-production.up.railway.app"

# ── resolve profile ──────────────────────────────────────────────────────────
from user_config import load_profile, list_profiles

profile_id = None
args = sys.argv[1:]
if "--profile" in args:
    idx = args.index("--profile")
    if idx + 1 < len(args):
        profile_id = args[idx + 1]

if not profile_id:
    profile_id = list_profiles()[0]

profile = load_profile(profile_id)
print(f"Profile: {profile_id} ({profile['user']['name']})")

# ── check env vars ────────────────────────────────────────────────────────────
railway_url = os.environ.get("RAILWAY_URL", "")
ingest_key = os.environ.get("INGEST_API_KEY", "")
if not railway_url or not ingest_key:
    print("ERROR: RAILWAY_URL and INGEST_API_KEY must be set in .env")
    sys.exit(1)

# ── send email ────────────────────────────────────────────────────────────────
from notifier import send_digest

prefilter_stats = {
    "total": 0,
    "passed": 0,
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
    "duration_s": 0,
    "cost_usd": 0.0,
    "n_searches": 0,
    "n_watchlist": 0,
    "date": datetime.now().strftime("%d %b %Y"),
}

print(f"\nFetching digest from: {railway_url}/api/digest/{profile_id}")
print("Sending email digest (test mode — seen_ids NOT updated)...")

ok = send_digest(
    railway_url=railway_url,
    profile_id=profile_id,
    ingest_key=ingest_key,
    rejected_stats=prefilter_stats,
    run_meta=run_meta,
    profile=profile,
)

if ok:
    print("✅ Email sent successfully")
else:
    print("❌ Email failed — check GMAIL_ADDRESS / GMAIL_APP_PASSWORD in .env")
    print("   Also verify RAILWAY_URL and INGEST_API_KEY are correct")
