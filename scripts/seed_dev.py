"""
Seed a dev user + session so you can test the web without Google OAuth.

Usage (from the jobseeker/ root):
    venv/bin/python scripts/seed_dev.py

Then open http://localhost:5173 and paste the cookie command shown below.
"""

import os
import sys
from pathlib import Path

# ── make sure we can import api modules ──────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # so relative DB_PATH works

from dotenv import load_dotenv
load_dotenv()

from api.db.init import init_db
from api.db.queries import upsert_user, create_session

# ── config ───────────────────────────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "data/jobseeker.db")
TOKEN   = "dev-jsk-juan"          # fixed token — easy to type in DevTools
EXPIRES = "2099-12-31T23:59:59"   # never expires in dev

USER = {
    "google_id":  "dev-juan-azabal",
    "email":      "j.azabal@gmail.com",
    "name":       "Juan Azabal",
    "avatar_url": None,
    "profile_id": "juan",         # matches jobagent config/profiles/juan.yaml
}

# ── seed ─────────────────────────────────────────────────────────────────────
Path("data").mkdir(exist_ok=True)
init_db(DB_PATH)

user = upsert_user(DB_PATH, USER)
create_session(DB_PATH, TOKEN, user["id"], EXPIRES)

print()
print("✅  Dev user seeded")
print(f"    DB:      {DB_PATH}")
print(f"    user id: {user['id']}")
print(f"    email:   {user['email']}")
print(f"    profile: {user['profile_id']}")
print()
print("🍪  Pega esto en la consola del navegador (http://localhost:5173):")
print()
print(f'    document.cookie = "jsk={TOKEN}; path=/"')
print()
print("    Luego recarga la página → entras como Juan Azabal.")
print()
