from __future__ import annotations

import difflib
import os
import argparse
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

    def apply_diff(self, dry_run: bool = False) -> None:
        """Apply the transformed version to the bound file."""
        if dry_run:
            diff = self.compute_diff()
            print(diff)
        else:
            raw_source = self.refactored_source.encode(self.file_info.get_encoding())
            with open(self.file, "wb") as stream:
                stream.write(raw_source)

    @property
    def file(self) -> Path:
        """Returns the bound file."""
        if self.file_info.path is None:
            raise ValueError("Change expects a valid file")
        return self.file_info.path


def refactor_file(file_path, dry_run=False):
    # Perform the refactoring logic here and get the refactored_source
    original_source = open(file_path).read()
    # Assume refactored_source is obtained somehow in the refactoring process

    change = Change(file_info=_FileInfo(path=Path(file_path)), original_source=original_source, refactored_source=refactored_source)
    change.apply_diff(dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refactor code.")
    parser.add_argument("file_path", help="Path to the file to be refactored.")
    parser.add_argument("--diff", action="store_true", help="Perform a dry-run and show the diff.")
    parser.add_argument("--fail-on-change", action="store_true", help="Exit with 1 if there are any changes without refactoring.")

    args = parser.parse_args()

    refactor_file(args.file_path, dry_run=args.diff)

    if args.fail_on_change and args.diff:
        print("Exiting with code 1 due to changes without refactoring.")
        exit(1)
