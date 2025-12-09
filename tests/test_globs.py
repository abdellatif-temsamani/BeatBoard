import pytest
from beatboard.globs import Globs


def test_globs_singleton():
    g1 = Globs()
    g2 = Globs()
    assert g1 is g2


@pytest.mark.parametrize(
    "attr, expected",
    [
        ("hardware", ["g213"]),
        ("debug", False),
    ],
)
def test_globs_defaults(attr, expected):
    g = Globs()
    assert getattr(g, attr) == expected


@pytest.mark.parametrize(
    "attr, value",
    [
        ("hardware", ["g213"]),
        ("debug", True),
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
    g1.debug = True
    assert g2.debug is True  # Shared state
