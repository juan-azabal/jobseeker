-- Migration 015: Waitlist table for landing page sign-ups.
CREATE TABLE IF NOT EXISTS waitlist (
    id         INTEGER PRIMARY KEY,
    email      TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
