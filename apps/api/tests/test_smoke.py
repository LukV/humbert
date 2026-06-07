"""Skeleton smoke test — proves the package imports and the gates run.

Replaced by real tests as features land.
"""

from humbert import __version__


def test_version_is_a_string() -> None:
    assert isinstance(__version__, str)
    assert __version__
