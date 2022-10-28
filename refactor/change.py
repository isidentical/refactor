from __future__ import annotations

import difflib
import os
from dataclasses import dataclass
from pathlib import Path

from refactor.ast import split_lines
from refactor.common import _FileInfo


@dataclass
class Change:
    """The result of a transformation in the bound file.

    Includes both the original source code, and the transformed
    variant.
    """

    file_info: _FileInfo
    original_source: str
    refactored_source: str

    def __post_init__(self):
        if self.file_info.path is None:
            raise ValueError("Can't apply a change to a string")

    def compute_diff(self) -> str:
        """Compute the line-based diff between original and the
        refactored source lines."""
        original_lines = split_lines(self.original_source)
        refactored_lines = split_lines(self.refactored_source)

        return "".join(
            difflib.unified_diff(
                original_lines,
                refactored_lines,
                os.fspath(self.file),
                os.fspath(self.file),
            )
        )

    def apply_diff(self) -> None:
        """Apply the transformed version to the bound file."""
        raw_source = self.refactored_source.encode(self.file_info.get_encoding())

        with open(self.file, "wb") as stream:
            stream.write(raw_source)

    @property
    def file(self) -> Path:
        """Returns the bound file."""
        if self.file_info.path is None:
            raise ValueError("Change expects a valid file")
        return self.file_info.path
