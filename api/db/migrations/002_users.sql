CREATE TABLE IF NOT EXISTS users (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  google_id  TEXT UNIQUE NOT NULL,
  email      TEXT,
  name       TEXT,
  avatar_url TEXT,
  profile_id TEXT,
  created_at TEXT,
  last_login TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  token      TEXT PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL
);
