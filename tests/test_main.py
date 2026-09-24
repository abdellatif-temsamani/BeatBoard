from argparse import Namespace
from collections.abc import Generator
from pathlib import Path

import pytest

import beatboard
from beatboard.globs import Globs


@pytest.fixture
def restore_hardware() -> Generator[None, None, None]:
    globs = Globs()
    previous = globs.hardware
    previous_debug = globs.debug
    previous_cache_path = globs.cache_path
    yield
    globs.hardware = previous
    globs.debug = previous_debug
    globs.cache_path = previous_cache_path


@pytest.mark.asyncio
async def test_main_uses_user_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text(
        'debug:\n  - cache\ncache_path: /tmp/beatboard.db\n',
        encoding='utf-8',
    )

    async def watch_playerctl(once: bool) -> None:
        return None

    monkeypatch.setattr(
        beatboard.parser,
        'parse_args',
        lambda: Namespace(hardware=None, debug=[], once=True, refresh_hardware=False),
    )
    monkeypatch.setattr(
        beatboard,
        'get_cached_hardware',
        lambda: ['g213'],
    )
    monkeypatch.setattr(beatboard, 'set_cached_hardware', lambda x: None)
    monkeypatch.setattr(
        beatboard,
        'detect_hardware',
        lambda: pytest.fail('Cached hardware must bypass detection'),
    )
    monkeypatch.setattr(beatboard, 'check_spotify_available', lambda: True)
    monkeypatch.setattr(beatboard, 'source_migrations', lambda: None)
    monkeypatch.setattr(beatboard, 'watch_playerctl', watch_playerctl)

    await beatboard.beatboard_main(config_path)

    globs = Globs()
    assert globs.hardware == ['g213']
    assert globs.debug['cache'] is True
    assert globs.cache_path == '/tmp/beatboard.db'


@pytest.mark.asyncio
async def test_main_reports_invalid_user_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('debug:\n  - noisy\n', encoding='utf-8')
    monkeypatch.setattr(
        beatboard.parser,
        'parse_args',
        lambda: Namespace(hardware=None, debug=[], once=False, refresh_hardware=False),
    )
    monkeypatch.setattr(
        beatboard,
        'detect_hardware',
        lambda: pytest.fail('Invalid config must stop startup'),
    )

    await beatboard.beatboard_main(config_path)

    output = capsys.readouterr().out
    assert 'Invalid configuration' in output
    assert str(config_path) in output


@pytest.mark.asyncio
async def test_main_uses_detected_hardware(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    watched: list[bool] = []

    async def watch_playerctl(once: bool) -> None:
        watched.append(once)

    monkeypatch.setattr(
        beatboard.parser,
        'parse_args',
        lambda: Namespace(hardware=None, debug=[], once=True, refresh_hardware=False),
    )
    monkeypatch.setattr(beatboard, 'get_cached_hardware', lambda: [])
    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(
        beatboard, 'set_cached_hardware', lambda hw: captured.update({'hw': hw})
    )
    monkeypatch.setattr(beatboard, 'detect_hardware', lambda: ['g213', 'razer'])
    monkeypatch.setattr(beatboard, 'check_spotify_available', lambda: True)
    monkeypatch.setattr(beatboard, 'source_migrations', lambda: None)
    monkeypatch.setattr(beatboard, 'watch_playerctl', watch_playerctl)

    await beatboard.beatboard_main(tmp_path / 'config.yaml')

    assert Globs().hardware == ['g213', 'razer']
    assert watched == [True]
    assert 'Detected hardware: g213, razer' in capsys.readouterr().out
    assert captured.get('hw') == ['g213', 'razer']


@pytest.mark.asyncio
async def test_main_stops_when_no_hardware_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # No hardware is no longer a hard error — it continues with empty hardware
    async def watch_playerctl(once: bool) -> None:
        return None

    monkeypatch.setattr(
        beatboard.parser,
        'parse_args',
        lambda: Namespace(
            hardware=None,
            debug=[],
            once=False,
            refresh_hardware=False,
            reset_cache=False,
            api=False,
        ),
    )
    monkeypatch.setattr(beatboard, 'get_cached_hardware', lambda: [])
    monkeypatch.setattr(beatboard, 'detect_hardware', lambda: [])
    monkeypatch.setattr(beatboard, 'check_spotify_available', lambda: True)
    monkeypatch.setattr(beatboard, 'source_migrations', lambda: None)
    monkeypatch.setattr(beatboard, 'watch_playerctl', watch_playerctl)

    await beatboard.beatboard_main(tmp_path / 'config.yaml')

    assert Globs().hardware == []
    output = capsys.readouterr().out
    assert 'No supported hardware detected' not in output


@pytest.mark.asyncio
async def test_main_keeps_explicit_hardware_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('debug: []\n', encoding='utf-8')

    async def watch_playerctl(once: bool) -> None:
        return None

    monkeypatch.setattr(
        beatboard.parser,
        'parse_args',
        lambda: Namespace(
            hardware=['g213'], debug=[], once=False, refresh_hardware=False
        ),
    )
    monkeypatch.setattr(
        beatboard,
        'get_cached_hardware',
        lambda: pytest.fail('Explicit hardware must bypass cache read'),
    )
    monkeypatch.setattr(
        beatboard,
        'detect_hardware',
        lambda: pytest.fail('Explicit hardware must bypass detection'),
    )
    monkeypatch.setattr(beatboard, 'check_spotify_available', lambda: True)
    monkeypatch.setattr(beatboard, 'source_migrations', lambda: None)
    monkeypatch.setattr(beatboard, 'watch_playerctl', watch_playerctl)

    await beatboard.beatboard_main(config_path)

    assert Globs().hardware == ['g213']


@pytest.mark.asyncio
async def test_main_refresh_hardware_forces_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def watch_playerctl(once: bool) -> None:
        return None

    monkeypatch.setattr(
        beatboard.parser,
        'parse_args',
        lambda: Namespace(hardware=None, debug=[], once=True, refresh_hardware=True),
    )
    # cached hardware exists but should be ignored when refresh is True
    monkeypatch.setattr(beatboard, 'get_cached_hardware', lambda: ['razer'])
    detected = ['g213']
    monkeypatch.setattr(beatboard, 'detect_hardware', lambda: detected)
    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(
        beatboard, 'set_cached_hardware', lambda hw: captured.update({'hw': hw})
    )
    monkeypatch.setattr(beatboard, 'check_spotify_available', lambda: True)
    monkeypatch.setattr(beatboard, 'source_migrations', lambda: None)
    monkeypatch.setattr(beatboard, 'watch_playerctl', watch_playerctl)

    await beatboard.beatboard_main(tmp_path / 'config.yaml')

    assert Globs().hardware == ['g213']
    assert captured.get('hw') == ['g213']
    assert 'Detected hardware: g213' in capsys.readouterr().out


@pytest.mark.asyncio
async def test_main_uses_cached_hardware_without_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
) -> None:
    async def watch_playerctl(once: bool) -> None:
        return None

    monkeypatch.setattr(
        beatboard.parser,
        'parse_args',
        lambda: Namespace(hardware=None, debug=[], once=True, refresh_hardware=False),
    )
    monkeypatch.setattr(beatboard, 'get_cached_hardware', lambda: ['asus'])
    monkeypatch.setattr(
        beatboard,
        'detect_hardware',
        lambda: pytest.fail('Cached hardware should bypass detection'),
    )
    monkeypatch.setattr(beatboard, 'check_spotify_available', lambda: True)
    monkeypatch.setattr(beatboard, 'source_migrations', lambda: None)
    monkeypatch.setattr(beatboard, 'watch_playerctl', watch_playerctl)

    await beatboard.beatboard_main(tmp_path / 'config.yaml')

    assert Globs().hardware == ['asus']
