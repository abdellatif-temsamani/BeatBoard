import sqlite3
from pathlib import Path
from unittest.mock import patch

from beatboard.cache.db import (
    get_connection,
    get_migrations,
    source_file,
    source_migrations,
)


class TestGetConnection:
    @patch("beatboard.cache.db.Globs")
    def test_get_connection_yields_connection(self, mock_globs):
        mock_globs.return_value.cache_path = ":memory:"
        with get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)


class TestGetMigrations:
    def test_get_migrations_returns_sorted_list(self):
        migrations = get_migrations()
        assert isinstance(migrations, list)
        assert all(isinstance(m, str) for m in migrations)
        # Check if sorted by number
        stems = [Path(m).stem for m in migrations]
        numbers = [int(stem.split("_")[0]) for stem in stems]
        assert numbers == sorted(numbers)


class TestSourceFile:
    @patch("beatboard.cache.db.Globs")
    def test_source_file_executes_script_and_inserts(self, mock_globs, tmp_path):
        mock_globs.return_value.debug = {"cache": False}
        # Create a temp sql file
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("CREATE TABLE test (id INTEGER);")

        db = sqlite3.connect(":memory:")
        cursor = db.cursor()
        # Create migrations table
        cursor.execute("""
            CREATE TABLE migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                status TEXT NOT NULL CHECK (status IN ('pending', 'ran'))
            );
        """)

        source_file(cursor, str(sql_file), "test.sql")

        # Check table created
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test'"
        )
        assert cursor.fetchone()

        # Check migration inserted
        cursor.execute(
            "SELECT file_name, status FROM migrations WHERE file_name='test.sql'"
        )
        row = cursor.fetchone()
        assert row == ("test.sql", "ran")

        db.close()


class TestSourceMigrations:
    @patch("beatboard.cache.db.Globs")
    def test_source_migrations_runs_new_migrations(self, mock_globs, tmp_path):
        # Set cache_path to temp file
        cache_db = tmp_path / "cache.db"
        mock_globs.return_value.cache_path = str(cache_db)
        mock_globs.return_value.debug = {"cache": False}

        # Run source_migrations
        source_migrations()

        # Check db created and table exists
        conn = sqlite3.connect(str(cache_db))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
        )
        assert cursor.fetchone()

        # Check migration ran
        cursor.execute("SELECT file_name FROM migrations ORDER BY file_name")
        migrations = cursor.fetchall()
        assert len(migrations) == 2
        assert migrations[0][0] == "00_create_migration_table.sql"
        assert migrations[1][0] == "01_create_colors_cache_table.sql"

        conn.close()

    @patch("beatboard.cache.db.Globs")
    def test_source_migrations_skips_existing(self, mock_globs, tmp_path):
        cache_db = tmp_path / "cache.db"
        mock_globs.return_value.cache_path = str(cache_db)
        mock_globs.return_value.debug = {"cache": False}

        # Run twice
        source_migrations()
        source_migrations()

        conn = sqlite3.connect(str(cache_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM migrations")
        count = cursor.fetchone()[0]
        assert count == 2  # Two migrations, run only once each

        conn.close()
