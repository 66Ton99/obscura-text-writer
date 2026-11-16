-- WAITLIST-001: one row per address; a repeated sign-up changes nothing (ON CONFLICT DO NOTHING).
CREATE TABLE IF NOT EXISTS waitlist (
  email TEXT PRIMARY KEY,
  lang TEXT NOT NULL CHECK (lang IN ('uk','en')),
  privacy_edition TEXT NOT NULL,
  created_at TEXT NOT NULL
);
