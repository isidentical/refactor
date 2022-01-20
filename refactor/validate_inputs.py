from argparse import Namespace
from pathlib import Path

_DEFAULT_FILES = [Path("refactors.py"), Path(".refactors/__init__.py")]


def validate_main_inputs(options: Namespace) -> None:
    """Validates options parsed from `main` runner.

    Note
    ----
    In the case where no ``--refactor-file`` is passed and a default file is
    matched, ``options.refactor_file`` will be set to that value.
    """
    if refactor_file := options.refactor_file:
        if not refactor_file.exists():
            raise ValueError(
                f"Given --refactor-file '{refactor_file!s}' doesn't exist"
            )
    else:
        for refactor_file in _DEFAULT_FILES:
            if refactor_file.exists():
                options.refactor_file = refactor_file
                break
        else:
            raise ValueError(
                "Either provide a file using --refactor-file or ensure one of "
                "these directories exist: "
                + ", ".join(map(str, _DEFAULT_FILES))
            )
