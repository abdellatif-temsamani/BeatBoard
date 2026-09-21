import sqlite3
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Cursor

from ..globs import Globs
from ..logs import log


@contextmanager
def get_connection():
    # Always use the path from config via Globs (no :memory: fallback).
    cache_path = Path(Globs().cache_path).expanduser()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False allows use via asyncio.to_thread
    db = sqlite3.connect(str(cache_path), check_same_thread=False, timeout=5.0)
    # Perf pragmas – safe for cache workload (WAL + NORMAL gives ~3x write throughput)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("PRAGMA cache_size=-20000")  # ~20MB
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA foreign_keys=ON")
    except sqlite3.Error:
        pass
    try:
        yield db
    finally:
        db.close()


def get_migrations() -> list[str]:
    """Get a sorted list of migration SQL file paths.

    Returns:
        List of file paths to migration SQL files, sorted by version number.
    """
    from pathlib import Path

    migrations_dir = Path(__file__).parent / "migrations"
    files = list(migrations_dir.glob("*.sql"))

    files.sort(key=lambda p: int(p.stem.split("_")[0]))
    return [str(p) for p in files]


def read_sql_file(file_path: str) -> str:
    """Read SQL script from file."""
    with open(file_path, "r") as f:
        return f.read()


def source_file(cursor: Cursor, file: str, file_name: str):
    """Execute a SQL migration script and record it in the migrations table.

    Args:
        cursor: Database cursor to execute the script.
        file: Path to the SQL file.
        file_name: Name of the migration file for recording.
    """
    sql_script = read_sql_file(file)

    log("cache", f"sourcing '{file_name}'")
    cursor.executescript(sql_script)

    cursor.execute(
        "INSERT INTO migrations (file_name, status) VALUES (?, ?)",
        (
            file_name,
            "ran",
        ),
    )


def source_migrations():
    """Run all pending database migrations.

    Checks which migrations have already been run and executes only the new ones.
    """
    migrations_files = get_migrations()

    with get_connection() as db:
        cursor = db.cursor()

        # Check if migrations table exists once
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
        )
        migration_table_exists = cursor.fetchone()

        for file in migrations_files:
            file_name = Path(file).name

            if not migration_table_exists:
                # migrations table doesn't exist, run the migration
                source_file(cursor, file, file_name)
            else:
                cursor.execute(
                    "SELECT 1 FROM migrations WHERE file_name = ?", (file_name,)
                )
                exists = cursor.fetchone()
                if not exists:
                    source_file(cursor, file, file_name)

        db.commit()


def get_cached_hardware() -> list[str]:
    """Return hardware list cached in the database.

    Returns:
        List of hardware names stored in the ``hardware`` table,
        ordered by insertion. Empty list if table missing or no rows.
    """
    with get_connection() as db:
        cursor = db.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hardware'"
        )
        if not cursor.fetchone():
            return []
        cursor.execute("SELECT name FROM hardware ORDER BY id")
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def set_cached_hardware(hardware: list[str]) -> None:
    """Persist ``hardware`` list to the cache database.

    Replaces any previously cached hardware. Creates the table if
    migrations have not yet created it.
    """
    with get_connection() as db:
        cursor = db.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hardware'"
        )
        if not cursor.fetchone():
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS hardware (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)"
            )
        cursor.execute("DELETE FROM hardware")
        for name in hardware:
            cursor.execute("INSERT INTO hardware (name) VALUES (?)", (name,))
        db.commit()
