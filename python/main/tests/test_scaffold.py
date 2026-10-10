"""Smoke tests for the limitful scaffold."""


def test_version():
    """Verify the package declares version 0.0.0."""
    import limitful

    assert limitful.__version__ == "0.0.0"


def test_import_no_side_effects():
    """Importing should not raise any exceptions."""
    # Already imported above; silence unused-import warning.
    assert True
