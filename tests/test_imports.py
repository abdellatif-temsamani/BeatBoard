def test_src_import():
    """Test that src package can be imported."""
    import src

    assert src is not None


def test_src_args_import():
    """Test that src.args can be imported."""
    import src.args

    assert src.args is not None
    assert hasattr(src.args, "parser")


def test_src_globs_import():
    """Test that src.globs can be imported."""
    import src.globs

    assert src.globs is not None
    assert hasattr(src.globs, "Globs")


def test_src_hardware_import():
    """Test that src.hardware can be imported."""
    import src.hardware

    assert src.hardware is not None
    assert hasattr(src.hardware, "get_command")


def test_main_import():
    """Test that main module can be imported."""
    import main

    assert main is not None
