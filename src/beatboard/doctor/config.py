"""Config diagnostics – path, YAML validity, required keys."""

from __future__ import annotations

import os
from pathlib import Path


def diagnose_config(config_path: Path | None = None) -> list[dict[str, str]]:
    """Check config file health."""
    results: list[dict[str, str]] = []
    try:
        from beatboard.config import get_config_path
    except Exception as exc:
        results.append(
            {
                'check': 'Config module',
                'status': 'fail',
                'detail': f'import failed: {exc}',
                'hint': 'Reinstall BeatBoard',
            }
        )
        return results

    if config_path is None:
        try:
            config_path = get_config_path()
        except Exception as exc:
            results.append(
                {
                    'check': 'Config path',
                    'status': 'fail',
                    'detail': str(exc),
                    'hint': '',
                }
            )
            return results

    results.append(
        {
            'check': 'Config path',
            'status': 'ok',
            'detail': str(config_path),
            'hint': '',
        }
    )

    # Existence
    exists = config_path.exists()
    if not exists:
        results.append(
            {
                'check': 'Config file exists',
                'status': 'warn',
                'detail': 'not found – will be created on next run',
                'hint': f'Run beatboard once or create {config_path}',
            }
        )
        return results
    results.append(
        {
            'check': 'Config file exists',
            'status': 'ok',
            'detail': 'found',
            'hint': '',
        }
    )

    # Readable
    try:
        data_text = config_path.read_text(encoding='utf-8')
        results.append(
            {
                'check': 'Config readable',
                'status': 'ok',
                'detail': f'{len(data_text)} bytes',
                'hint': '',
            }
        )
    except OSError as exc:
        results.append(
            {
                'check': 'Config readable',
                'status': 'fail',
                'detail': str(exc),
                'hint': f'chmod 644 {config_path} or check parent permissions',
            }
        )
        return results

    # Writable
    try:
        writable = os.access(config_path, os.W_OK)
        results.append(
            {
                'check': 'Config writable',
                'status': 'ok' if writable else 'warn',
                'detail': 'writable' if writable else 'read-only',
                'hint': '' if writable else f'chmod u+w {config_path}',
            }
        )
    except Exception:
        pass

    # YAML parse + load_config
    try:
        import yaml

        loaded = yaml.safe_load(data_text)
        if loaded is None:
            loaded = {}
        if not isinstance(loaded, dict):
            results.append(
                {
                    'check': 'Config YAML',
                    'status': 'fail',
                    'detail': 'top level must be a mapping',
                    'hint': 'Fix YAML structure – see docs/config.md',
                }
            )
            return results
        results.append(
            {
                'check': 'Config YAML',
                'status': 'ok',
                'detail': f'{len(loaded)} keys',
                'hint': '',
            }
        )
    except Exception as exc:
        results.append(
            {
                'check': 'Config YAML',
                'status': 'fail',
                'detail': f'invalid YAML: {exc}',
                'hint': "Validate with `python -c 'import yaml; yaml.safe_load(open(...))'`",
            }
        )
        return results

    # Validate via load_config (strict)
    try:
        from beatboard.config import ConfigError, load_config

        # load_config may heal file – use a temp copy semantics? Call directly
        # It will auto-heal missing keys on disk, so we check before heal
        cfg = load_config(config_path)
        results.append(
            {
                'check': 'Config validation',
                'status': 'ok',
                'detail': f'debug={cfg.debug} cache_path={cfg.cache_path} hardware={cfg.hardware}',
                'hint': '',
            }
        )
        # Check expected keys
        from beatboard.config import DEFAULT_CONFIG

        missing = [k for k in DEFAULT_CONFIG if k not in loaded]
        if missing:
            results.append(
                {
                    'check': 'Missing config keys',
                    'status': 'warn',
                    'detail': f'auto-filled: {", ".join(missing)}',
                    'hint': 'Defaults were written to disk',
                }
            )
        else:
            results.append(
                {
                    'check': 'Config keys',
                    'status': 'ok',
                    'detail': 'all defaults present',
                    'hint': '',
                }
            )
        # Check spotify keys presence
        has_token = bool(cfg.spotify_token)
        has_refresh = bool(cfg.spotify_refresh_token)
        has_id = bool(cfg.spotify_client_id)
        has_secret = bool(cfg.spotify_client_secret)
        detail = f'token={"yes" if has_token else "no"} refresh={"yes" if has_refresh else "no"} client_id={"yes" if has_id else "no"} secret={"yes" if has_secret else "no"}'
        status = 'ok' if (has_token or (has_id and has_secret)) else 'warn'
        results.append(
            {
                'check': 'Spotify credentials',
                'status': status,
                'detail': detail,
                'hint': ''
                if status == 'ok'
                else 'Set spotify_token or client_id/secret for --api',
            }
        )
    except Exception as exc:
        # ConfigError
        try:
            from beatboard.config import ConfigError

            if isinstance(exc, ConfigError):
                results.append(
                    {
                        'check': 'Config validation',
                        'status': 'fail',
                        'detail': str(exc),
                        'hint': 'Fix config.yaml – see docs/config.md',
                    }
                )
                return results
        except Exception:
            pass
        results.append(
            {
                'check': 'Config validation',
                'status': 'fail',
                'detail': str(exc),
                'hint': 'See error above',
            }
        )
    return results
