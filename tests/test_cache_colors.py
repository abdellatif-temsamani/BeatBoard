import sqlite3
from unittest.mock import MagicMock, patch

from beatboard.cache.colors import (
    cache_colors,
    compress_colors,
    decompress_colors,
    get_cached_colors,
)


class TestCompressDecompressColors:
    def test_compress_decompress_round_trip(self):
        """Test that compressing and decompressing colors preserves data."""
        original_colors = ["ff0000", "00ff00", "0000ff", "ffffff"]
        compressed = compress_colors(original_colors)
        decompressed = decompress_colors(compressed)
        assert decompressed == original_colors

    def test_compress_decompress_empty_list(self):
        """Test compression/decompression with empty color list."""
        original_colors = []
        compressed = compress_colors(original_colors)
        decompressed = decompress_colors(compressed)
        assert decompressed == original_colors

    def test_compress_decompress_single_color(self):
        """Test compression/decompression with single color."""
        original_colors = ["123456"]
        compressed = compress_colors(original_colors)
        decompressed = decompress_colors(compressed)
        assert decompressed == original_colors


class TestColorsCache:
    def setup_method(self):
        """Set up in-memory database with colors_cache table."""
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""
            CREATE TABLE colors_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                colors TEXT NOT NULL
            )
        """)
        self.db.execute(
            "CREATE UNIQUE INDEX idx_colors_cache_name ON colors_cache (name)"
        )
        self.db.commit()

    def teardown_method(self):
        """Clean up database."""
        self.db.close()

    @patch("beatboard.cache.colors.get_connection")
    @patch("beatboard.logs.Globs")
    def test_colors_cache_inserts_new_entry(self, mock_globs, mock_get_conn):
        """Test caching colors inserts a new entry."""
        mock_globs.return_value.debug = {"cache": False}
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = self.db
        mock_conn.__exit__.return_value = None
        mock_get_conn.return_value = mock_conn

        cache_colors("test_art", ["ff0000", "00ff00"])

        # Check inserted
        cursor = self.db.execute(
            "SELECT name, colors FROM colors_cache WHERE name = ?", ("test_art",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "test_art"
        decompressed = decompress_colors(row[1])
        assert decompressed == ["ff0000", "00ff00"]

    @patch("beatboard.cache.colors.get_connection")
    @patch("beatboard.logs.Globs")
    def test_colors_cache_updates_existing(self, mock_globs, mock_get_conn):
        """Test caching colors updates existing entry."""
        mock_globs.return_value.debug = {"cache": False}
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = self.db
        mock_conn.__exit__.return_value = None
        mock_get_conn.return_value = mock_conn

        # Insert initial
        compressed = compress_colors(["old_color"])
        self.db.execute(
            "INSERT INTO colors_cache (name, colors) VALUES (?, ?)",
            ("test_art", compressed),
        )
        self.db.commit()

        cache_colors("test_art", ["new_color"])

        # Check updated
        cursor = self.db.execute(
            "SELECT colors FROM colors_cache WHERE name = ?", ("test_art",)
        )
        row = cursor.fetchone()
        decompressed = decompress_colors(row[0])
        assert decompressed == ["new_color"]


class TestGetCachedColors:
    def setup_method(self):
        """Set up in-memory database with colors_cache table."""
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""
            CREATE TABLE colors_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                colors TEXT NOT NULL
            )
        """)
        self.db.execute(
            "CREATE UNIQUE INDEX idx_colors_cache_name ON colors_cache (name)"
        )
        self.db.commit()

    def teardown_method(self):
        """Clean up database."""
        self.db.close()

    @patch("beatboard.cache.colors.get_connection")
    @patch("beatboard.logs.Globs")
    def test_get_cached_colors_hit(self, mock_globs, mock_get_conn):
        """Test retrieving cached colors when entry exists."""
        mock_globs.return_value.debug = {"cache": False}
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = self.db
        mock_conn.__exit__.return_value = None
        mock_get_conn.return_value = mock_conn

        # Insert entry
        compressed = compress_colors(["cached_color"])
        self.db.execute(
            "INSERT INTO colors_cache (name, colors) VALUES (?, ?)",
            ("test_art", compressed),
        )
        self.db.commit()

        result = get_cached_colors("test_art")
        assert result == ["cached_color"]

    @patch("beatboard.cache.colors.get_connection")
    @patch("beatboard.logs.Globs")
    def test_get_cached_colors_miss(self, mock_globs, mock_get_conn):
        """Test retrieving cached colors when entry does not exist."""
        mock_globs.return_value.debug = {"cache": False}
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = self.db
        mock_conn.__exit__.return_value = None
        mock_get_conn.return_value = mock_conn

        result = get_cached_colors("nonexistent")
        assert result is None

    @patch("beatboard.cache.colors.get_connection")
    @patch("beatboard.logs.Globs")
    def test_get_cached_colors_none_name(self, mock_globs, mock_get_conn):
        """Test retrieving cached colors with None name."""
        mock_globs.return_value.debug = {"cache": False}
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = self.db
        mock_conn.__exit__.return_value = None
        mock_get_conn.return_value = mock_conn

        result = get_cached_colors(None)
        assert result is None
