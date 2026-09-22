from pathlib import Path

import pytest

from beatboard.globs import Globs, get_cache_db


def test_default_cache_path_is_in_user_state_directory() -> None:
    assert get_cache_db() == str(
        Path.home() / ".local" / "state" / "beatboard" / "cache.db"
    )


def test_globs_singleton():
    g1 = Globs()
    g2 = Globs()
    assert g1 is g2


@pytest.mark.parametrize(
    "attr, value",
    [
        ("hardware", ["g213"]),
        (
            "debug",
            {
                "command": False,
                "palette": False,
                "cache": False,
                "perf": False,
                "api": False,
                "plugins": False,
                "all": False,
            },
        ),
    ],
)
def test_globs_defaults(attr, value):
    g = Globs()
    assert getattr(g, attr) == value


@pytest.mark.parametrize(
    "attr, value",
    [
        ("hardware", ["g213"]),
        (
            "debug",
            {
                "command": True,
                "palette": False,
                "cache": False,
                "perf": False,
                "api": False,
                "plugins": False,
                "all": False,
            },
        ),
    ],
)
def test_globs_modify(attr, value):
    g = Globs()
    setattr(g, attr, value)
    assert getattr(g, attr) == value


def test_globs_independent_instances():
    # Since it's singleton, instances should be the same
    g1 = Globs()
    g2 = Globs()
    g1.debug = {
        "command": True,
        "palette": False,
        "cache": False,
        "perf": False,
        "api": False,
        "plugins": False,
        "all": False,
    }
    assert g2.debug == {
        "command": True,
        "palette": False,
        "cache": False,
        "perf": False,
        "api": False,
        "plugins": False,
        "all": False,
    }  # Shared state
