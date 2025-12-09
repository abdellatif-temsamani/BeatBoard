import pytest

from beatboard.args import parser


@pytest.mark.parametrize(
    "args, expected_follow, expected_debug, expected_hardware",
    [
        ([], False, False, ["g213"]),
        (["--follow"], True, False, ["g213"]),
        (["--debug"], False, True, ["g213"]),
        (["--follow", "--debug"], True, True, ["g213"]),
        (["--hardware", "g213"], False, False, ["g213"]),
        (["--hardware", "g213", "g213"], False, False, ["g213", "g213"]),
    ],
)
def test_parser_various_args(args, expected_follow, expected_debug, expected_hardware):
    parsed = parser.parse_args(args)
    assert parsed.follow == expected_follow
    assert parsed.debug == expected_debug
    assert parsed.hardware == expected_hardware


def test_parser_invalid_hardware():
    with pytest.raises(SystemExit):
        parser.parse_args(["--hardware", "invalid"])


def test_parser_help_output(capsys):
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])
    captured = capsys.readouterr()
    assert "BeatBoard" in captured.out
    assert "Change your hardware RGB" in captured.out
