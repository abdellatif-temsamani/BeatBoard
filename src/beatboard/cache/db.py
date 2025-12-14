import sqlite3
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Cursor

from ..globs import Globs
from ..logs import log


@contextmanager
def get_connection():
    db = sqlite3.connect(Globs().cache_path)
    yield db
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
