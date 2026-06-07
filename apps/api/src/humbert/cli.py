"""Entry point stub.

The real commands — ``init`` / ``connect`` / ``start`` — land in the CLI pitch.
For now this only resolves the ``humbert`` console script and prints the version,
so the entry point exists and the build is wired end to end.
"""

from humbert import __version__


def main() -> None:
    print(f"humbert {__version__}")
