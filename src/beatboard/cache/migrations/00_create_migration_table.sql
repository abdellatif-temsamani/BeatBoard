-- sqlite
CREATE TABLE IF NOT EXISTS migrations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime ('now')),
  status TEXT NOT NULL CHECK (status IN ('pending', 'ran'))
);
