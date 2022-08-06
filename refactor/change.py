import difflib
import os
from dataclasses import dataclass
from pathlib import Path

from refactor.ast import split_lines


@dataclass
class Change:
    """The result of a transformation in the bound file.

    Includes both the original source code, and the transformed
    variant.
    """

    file: Path
    original_source: str
    refactored_source: str

    def compute_diff(self) -> str:
        """Compute the line-based diff between original and the
        refactored source lines."""
        original_lines = split_lines(self.original_source)
        refactored_lines = split_lines(self.refactored_source)

        return "\n".join(
            difflib.unified_diff(
                original_lines,
                refactored_lines,
                os.fspath(self.file),
                os.fspath(self.file),
            )
        )

    def apply_diff(self) -> None:
        """Apply the transformed version to the bound file."""
        with open(self.file, "w") as stream:
            stream.write(self.refactored_source)
