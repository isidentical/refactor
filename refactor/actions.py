from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import cast

from refactor.ast import split_lines
from refactor.common import find_indent
from refactor.context import Context

__all__ = [
    "Action",
    "ReplacementAction",
    "NewStatementAction",
    "TargetedNewStatementAction",
]


@dataclass
class Action:
    """Base class for all actions.

    Override the `build()` method to programmatically build
    the replacement nodes.
    """

    node: ast.AST

    def apply(self, context: Context, source: str) -> str:
        """Refactor a source segment in the given string."""
        lines = split_lines(source)
        view = slice(self.node.lineno - 1, self.node.end_lineno)

        target_lines = lines[view]
        indentation, start_prefix = find_indent(
            target_lines[0][: self.node.col_offset]
        )
        end_prefix = target_lines[-1][self.node.end_col_offset :]

        replacement = split_lines(context.unparse(self.build()))
        replacement.apply_indentation(
            indentation, start_prefix=start_prefix, end_suffix=end_prefix
        )

        lines[view] = replacement
        return lines.join()

    def build(self) -> ast.AST:
        """Create the replacement node."""
        raise NotImplementedError

    def branch(self) -> ast.AST:
        """Return a copy view of the original node."""
        return copy.deepcopy(self.node)


@dataclass
class ReplacementAction(Action):
    """An action for replacing the `node` with
    the given `target` node."""

    node: ast.AST
    target: ast.AST

    def build(self) -> ast.AST:
        return self.target


class NewStatementAction(Action):
    """An action base for adding a new statement right after
    the given `node`."""

    def apply(self, context: Context, source: str) -> str:
        lines = split_lines(source)

        start_line = lines[self.node.lineno - 1]
        indentation, start_prefix = find_indent(
            start_line[: self.node.col_offset]
        )

        replacement = split_lines(context.unparse(self.build()))
        replacement.apply_indentation(indentation, start_prefix=start_prefix)

        end_line = cast(int, self.node.end_lineno)
        for line in reversed(replacement):
            lines.insert(end_line, line)

        return lines.join()


class TargetedNewStatementAction(ReplacementAction, NewStatementAction):
    """An action for appending the given `target` node
    right after the `node`."""
