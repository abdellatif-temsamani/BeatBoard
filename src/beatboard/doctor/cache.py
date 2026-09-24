"""Cache diagnostics – path, file, SQLite health."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def diagnose_cache(cache_path_str: str | None = None) -> list[dict[str, str]]:
    """Check cache DB health."""
    results: list[dict[str, str]] = []
    # Resolve path
    if cache_path_str is None:
        try:
            from beatboard.globs import Globs

            cache_path_str = Globs().cache_path
        except Exception:
            try:
                from beatboard.globs import get_cache_db

                cache_path_str = get_cache_db()
            except Exception as exc:
                results.append(
                    {
                        'check': 'Cache path',
                        'status': 'fail',
                        'detail': str(exc),
                        'hint': 'Check globs.get_cache_db',
                    }
                )
                return results
    # Also try to get from config if Globs not set
    if not cache_path_str:
        try:
            from beatboard.globs import get_cache_db

            cache_path_str = get_cache_db()
        except Exception:
            cache_path_str = '~/.local/state/beatboard/cache.db'

    expanded = str(Path(cache_path_str).expanduser())
    results.append(
        {
            'check': 'Cache path',
            'status': 'ok',
            'detail': expanded,
            'hint': '',
        }
    )
    cache_path = Path(expanded)

    # Parent dir
    parent = cache_path.parent
    results.append(
        {
            'check': 'Cache directory',
            'status': 'ok' if parent.exists() else 'warn',
            'detail': str(parent)
            + (' exists' if parent.exists() else ' missing – will be created'),
            'hint': '' if parent.exists() else f'mkdir -p {parent}',
        }
    )
    if parent.exists():
        writable = os.access(parent, os.W_OK)
        results.append(
            {
                'check': 'Cache dir writable',
                'status': 'ok' if writable else 'fail',
                'detail': 'writable' if writable else 'not writable',
                'hint': '' if writable else f'chmod u+w {parent} or chown',
            }
        )

    # File exists
    if not cache_path.is_file():
        results.append(
            {
                'check': 'Cache file',
                'status': 'warn',
                'detail': 'not found – will be created on next run',
                'hint': 'Run beatboard once to init DB (source_migrations)',
            }
        )
        return results

    # File size
    try:
        size = cache_path.stat().st_size
        # Human readable
        hr = f'{size} bytes'
        if size > 1024:
            hr = f'{size / 1024:.1f} KB'
        if size > 1024 * 1024:
            hr = f'{size / 1024 / 1024:.1f} MB'
        results.append(
            {
                'check': 'Cache file size',
                'status': 'ok',
                'detail': hr,
                'hint': 'Use --reset-cache to clear colors (keeps hardware)',
            }
        )
    except OSError as exc:
        results.append(
            {
                'check': 'Cache file size',
                'status': 'warn',
                'detail': str(exc),
                'hint': '',
            }
        )

    # Readable
    try:
        readable = os.access(cache_path, os.R_OK)
        results.append(
            {
                'check': 'Cache readable',
                'status': 'ok' if readable else 'fail',
                'detail': 'readable' if readable else 'not readable',
                'hint': '' if readable else f'chmod 644 {cache_path}',
            }
        )
    except Exception:
        pass

    # Writable
    try:
        writable = os.access(cache_path, os.W_OK)
        results.append(
            {
                'check': 'Cache writable',
                'status': 'ok' if writable else 'fail',
                'detail': 'writable' if writable else 'read-only',
                'hint': '' if writable else f'chmod u+w {cache_path}',
            }
        )
    except Exception:
        pass

    # SQLite connect + pragmas
    try:
        conn = sqlite3.connect(str(cache_path), timeout=5.0)
        try:
            cur = conn.cursor()
            # Check migrations table
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
            )
            has_mig = cur.fetchone() is not None
            results.append(
                {
                    'check': 'Migrations table',
                    'status': 'ok' if has_mig else 'warn',
                    'detail': 'present'
                    if has_mig
                    else 'missing – run source_migrations',
                    'hint': '' if has_mig else 'Start beatboard to run migrations',
                }
            )
            if has_mig:
                cur.execute(
                    'SELECT file_name, status FROM migrations ORDER BY file_name'
                )
                rows = cur.fetchall()
                detail = (
                    ', '.join(f'{r[0]}:{r[1]}' for r in rows) if rows else 'no rows'
                )
                results.append(
                    {
                        'check': 'Applied migrations',
                        'status': 'ok' if rows else 'warn',
                        'detail': detail,
                        'hint': '',
                    }
                )
            # colors_cache
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='colors_cache'"
            )
            has_colors = cur.fetchone() is not None
            if has_colors:
                cur.execute('SELECT COUNT(*) FROM colors_cache')
                count = cur.fetchone()[0]
                # check track_id column
                try:
                    cur.execute('PRAGMA table_info(colors_cache)')
                    cols = [r[1] for r in cur.fetchall()]
                    has_track = 'track_id' in cols
                except Exception:
                    has_track = False
                results.append(
                    {
                        'check': 'colors_cache',
                        'status': 'ok',
                        'detail': f'{count} rows, track_id={"yes" if has_track else "no"}',
                        'hint': '',
                    }
                )
            else:
                results.append(
                    {
                        'check': 'colors_cache',
                        'status': 'warn',
                        'detail': 'missing – will be created via migrations',
                        'hint': '',
                    }
                )
            # hardware table
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='hardware'"
            )
            has_hw = cur.fetchone() is not None
            if has_hw:
                cur.execute('SELECT name FROM hardware ORDER BY id')
                hw_rows = [r[0] for r in cur.fetchall()]
                detail = ', '.join(hw_rows) if hw_rows else 'empty (no cached hardware)'
                results.append(
                    {
                        'check': 'hardware cache',
                        'status': 'ok' if hw_rows else 'warn',
                        'detail': detail,
                        'hint': ''
                        if hw_rows
                        else 'Run without --hardware to auto-detect',
                    }
                )
            else:
                results.append(
                    {
                        'check': 'hardware cache',
                        'status': 'warn',
                        'detail': 'missing – will be created via migrations',
                        'hint': '',
                    }
                )
            # Integrity check quick
            try:
                cur.execute('PRAGMA integrity_check')
                chk = cur.fetchone()
                ok = chk and chk[0] == 'ok'
                results.append(
                    {
                        'check': 'SQLite integrity',
                        'status': 'ok' if ok else 'fail',
                        'detail': chk[0] if chk else 'unknown',
                        'hint': '' if ok else 'Restore or delete cache file',
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        'check': 'SQLite integrity',
                        'status': 'warn',
                        'detail': str(exc),
                        'hint': '',
                    }
                )

            # journal mode
            try:
                cur.execute('PRAGMA journal_mode')
                jm = cur.fetchone()
                if jm:
                    results.append(
                        {
                            'check': 'Journal mode',
                            'status': 'ok',
                            'detail': jm[0],
                            'hint': '',
                        }
                    )
            except Exception:
                pass
        finally:
            conn.close()
    except sqlite3.Error as exc:
        results.append(
            {
                'check': 'SQLite connect',
                'status': 'fail',
                'detail': f'cannot open DB: {exc}',
                'hint': 'Check permissions or delete corrupted cache',
            }
        )
    return results
