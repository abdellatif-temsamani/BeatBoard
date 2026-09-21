from argparse import Namespace
from collections.abc import Generator

import pytest

import beatboard
from beatboard.globs import Globs


@pytest.fixture
def restore_hardware() -> Generator[None, None, None]:
    globs = Globs()
    previous = globs.hardware
    yield
    globs.hardware = previous


@pytest.mark.asyncio
async def test_main_uses_detected_hardware(
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    watched: list[bool] = []

    async def watch_playerctl(once: bool) -> None:
        watched.append(once)

    monkeypatch.setattr(
        beatboard.parser,
        "parse_args",
        lambda: Namespace(hardware=None, debug=[], once=True),
    )
    monkeypatch.setattr(beatboard, "detect_hardware", lambda: ["g213", "razer"])
    monkeypatch.setattr(beatboard, "check_spotify_available", lambda: True)
    monkeypatch.setattr(beatboard, "source_migrations", lambda: None)
    monkeypatch.setattr(beatboard, "watch_playerctl", watch_playerctl)

    await beatboard.beatboard_main()

    assert Globs().hardware == ["g213", "razer"]
    assert watched == [True]
    assert "Detected hardware: g213, razer" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_main_stops_when_no_hardware_is_detected(
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        beatboard.parser,
        "parse_args",
        lambda: Namespace(hardware=None, debug=[], once=False),
    )
    monkeypatch.setattr(beatboard, "detect_hardware", lambda: [])
    monkeypatch.setattr(
        beatboard,
        "check_spotify_available",
        lambda: pytest.fail("Spotify should not be checked without hardware"),
    )

    await beatboard.beatboard_main()

    output = capsys.readouterr().out
    assert "No supported hardware detected" in output
    assert "--hardware" in output


@pytest.mark.asyncio
async def test_main_keeps_explicit_hardware_selection(
    monkeypatch: pytest.MonkeyPatch,
    restore_hardware: None,
) -> None:
    async def watch_playerctl(once: bool) -> None:
        return None

    monkeypatch.setattr(
        beatboard.parser,
        "parse_args",
        lambda: Namespace(hardware=["g213"], debug=[], once=False),
    )
    monkeypatch.setattr(
        beatboard,
        "detect_hardware",
        lambda: pytest.fail("Explicit hardware must bypass detection"),
    )
    monkeypatch.setattr(beatboard, "check_spotify_available", lambda: True)
    monkeypatch.setattr(beatboard, "source_migrations", lambda: None)
    monkeypatch.setattr(beatboard, "watch_playerctl", watch_playerctl)

    await beatboard.beatboard_main()

    assert Globs().hardware == ["g213"]
