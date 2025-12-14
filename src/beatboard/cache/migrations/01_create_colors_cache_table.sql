CREATE TABLE colors_cache (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  colors TEXT NOT NULL
);

CREATE UNIQUE INDEX idx_colors_cache_name ON colors_cache (name);
