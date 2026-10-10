"""Packaging smoke test for the limitful package."""

from importlib import import_module


def test_package_can_be_imported():
    """Verify the workspace package is importable."""
    package = import_module("limitful")
    assert package.__name__ == "limitful"
