from refactor.context import Configuration, Context, Representative
from refactor.core import (
    Action,
    NewStatementAction,
    ReplacementAction,
    Rule,
    Session,
)
from refactor.runner import run


def _check_asserts():
    import sys
    import warnings

    if sys.flags.optimize >= 1:
        warnings.warn(
            "Both the core source as well as the "
            "rules written with 'refactor' depend on "
            "assert statements, but the current session "
            "effectively disables them with -O/-OO options.",
            stacklevel=3,
        )


_check_asserts()
