import pytest

from beatboard.args import parser


@pytest.mark.parametrize(
    'args, expected_once, expected_debug, expected_hardware',
    [
        ([], False, [], None),
        (['--once'], True, [], None),
        (['--debug', 'command'], False, ['command'], None),
        (
            ['--once', '--debug', 'command', 'cache'],
            True,
            ['command', 'cache'],
            None,
        ),
        (['--hardware', 'g213'], False, [], ['g213']),
        (['--hardware', 'g213', 'g213'], False, [], ['g213', 'g213']),
    ],
)
def test_parser_various_args(args, expected_once, expected_debug, expected_hardware):
    parsed = parser.parse_args(args)
    assert parsed.once == expected_once
    assert parsed.debug == expected_debug
    assert parsed.hardware == expected_hardware


def test_parser_invalid_hardware():
    # Hardware validation is deferred until after plugins are loaded (so parser accepts any value)
    parsed = parser.parse_args(['--hardware', 'invalid'])
    assert parsed.hardware == ['invalid']
    from beatboard.args import _validate_hardware_or_exit

    with pytest.raises(SystemExit):
        _validate_hardware_or_exit(parsed.hardware)


def test_parser_invalid_debug():
    with pytest.raises(SystemExit):
        parser.parse_args(['--debug', 'invalid'])


def test_parser_help_output(capsys):
    with pytest.raises(SystemExit):
        parser.parse_args(['--help'])
    captured = capsys.readouterr()
    assert 'BeatBoard' in captured.out
    assert 'Change your hardware RGB' in captured.out
