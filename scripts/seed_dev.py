"""
Seed a dev user + session so you can test the web without Google OAuth.

Usage (from the jobseeker/ root):
    venv/bin/python scripts/seed_dev.py

Then open http://localhost:5173 — the cookie is printed below.
To inject it manually:
  Chrome DevTools → Application → Cookies → http://localhost:5173
  Add:  Name=session  Value=<token>  Domain=localhost  Path=/
"""

import os
import sys
import secrets
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
DB_PATH   = os.environ.get("DB_PATH", "data/jobseeker.db")
TOKEN     = "dev-session-juan"        # fixed token — easy to set in DevTools
EXPIRES   = "2099-12-31T23:59:59"    # won't expire

USER = {
    "google_id":  "dev-juan-azabal",
    "email":      "j.azabal@gmail.com",
    "name":       "Juan Azabal",
    "avatar_url": None,
    "profile_id": "juan",             # matches jobagent config/profiles/juan.yaml
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
print("🍪  Inyecta esta cookie en el navegador:")
print()
print(f"    Name:    session")
print(f"    Value:   {TOKEN}")
print(f"    Domain:  localhost")
print(f"    Path:    /")
print()
print("👉  Chrome DevTools → Application → Cookies → http://localhost:5173")
print("    → haz clic en la fila vacía del fondo y rellena los campos.")
print()
print("    O pégalo directamente en la consola del navegador:")
print(f'    document.cookie = "session={TOKEN}; path=/"')
print()
