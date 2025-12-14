import sqlite3
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Cursor

from rich import print

from ..globs import Globs


@contextmanager
def get_connection():
    db = sqlite3.connect(Globs().cache_path)
    yield db
    db.close()


def get_migrations() -> list[str]:
    from pathlib import Path

    migrations_dir = Path(__file__).parent / "migrations"
    files = list(migrations_dir.glob("*.sql"))

    files.sort(key=lambda p: int(p.stem.split("_")[0]))
    return [str(p) for p in files]


def source_file(cursor: Cursor, file: str, file_name: str):
    with open(file, "r") as f:
        sql_script = f.read()

    if Globs().debug["cache"]:
        print(f"sourcing '{file_name}'")
    cursor.executescript(sql_script)

    cursor.execute(
        "INSERT INTO migrations (file_name, status) VALUES (?, ?)",
        (
            file_name,
            "ran",
        ),
    )


def source_migrations():
    migrations_files = get_migrations()

    with get_connection() as db:
        cursor = db.cursor()

        for file in migrations_files:
            file_name = Path(file).name

            # Check if migrations table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
            )
            table_exists = cursor.fetchone()

            if not table_exists:
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
