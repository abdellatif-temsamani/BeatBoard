def test_beatboard_import():
    """Test that beatboard package can be imported."""
    import beatboard

    assert beatboard is not None


def test_beatboard_args_import():
    """Test that beatboard.args can be imported."""
    import beatboard.args

    assert beatboard.args is not None
    assert hasattr(beatboard.args, "parser")


def test_beatboard_globs_import():
    """Test that beatboard.globs can be imported."""
    import beatboard.globs

    assert beatboard.globs is not None
    assert hasattr(beatboard.globs, "Globs")


def test_beatboard_hardware_import():
    """Test that beatboard.hardware can be imported."""
    import beatboard.hardware

    assert beatboard.hardware is not None
    assert hasattr(beatboard.hardware, "get_command")


def test_main_import():
    """Test that main function can be imported."""
    from beatboard import main

    assert main is not None
