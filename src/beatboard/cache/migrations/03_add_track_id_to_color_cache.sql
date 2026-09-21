-- Migration: add track_id to colors_cache for fast websocket track lookups
-- Enables O(1) track cache hits without prefix scan and avoids API + palette latency.
-- Backfills existing track_ entries and creates index for fast lookups.

ALTER TABLE colors_cache ADD COLUMN track_id TEXT;

-- Backfill track_id from existing track_ prefixed rows (legacy cache entries)
UPDATE colors_cache SET track_id = substr(name, 7) WHERE name LIKE 'track_%' AND (track_id IS NULL OR track_id = '');

-- Fast lookup by track_id (Spotify track IDs are 22-char base62)
CREATE INDEX IF NOT EXISTS idx_colors_cache_track_id ON colors_cache(track_id);

-- Partial index for non-null track_ids helps query planner; kept separate for clarity
-- (SQLite supports WHERE in CREATE INDEX)
CREATE INDEX IF NOT EXISTS idx_colors_cache_track_id_notnull ON colors_cache(track_id) WHERE track_id IS NOT NULL;
