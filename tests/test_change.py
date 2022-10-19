import os
import textwrap
from pathlib import Path

from refactor import common
from refactor.change import Change


def test_change_compute_diff(tmp_path):
    file_info = common._FileInfo(path=Path(tmp_path / "test.py"))
    change = Change(
        file_info,
        textwrap.dedent(
            """
        if (
            something
            and something_else
            and something_else
        ):
            ...

        def unchanged():
            return 2 + 2
        """
        ),
        textwrap.dedent(
            """
        if (
            something
            or something_else
            or something_different
        ):
            ...

        def unchanged():
            return 2 + 2
        """
        ),
    )

    assert change.compute_diff().splitlines() == [
        f"--- {os.fspath(file_info.path)}",
        f"+++ {os.fspath(file_info.path)}",
        "@@ -1,8 +1,8 @@",
        " ",
        " if (",
        "     something",
        "-    and something_else",
        "-    and something_else",
        "+    or something_else",
        "+    or something_different",
        " ):",
        "     ...",
        " ",
    ]
