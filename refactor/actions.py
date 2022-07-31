from __future__ import annotations

import ast
import copy
import warnings
from contextlib import suppress
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from refactor.ast import split_lines
from refactor.common import _hint, find_indent
from refactor.context import Context

K = TypeVar("K")
T = TypeVar("T")
C = TypeVar("C")

__all__ = [
    "BaseAction",
    "InsertAfter",
    "LazyInsertAfter",
    "LazyReplace",
    "Replace",
]


class BaseAction:
    """A source code editing action."""

    def apply(self, context: Context, source: str) -> str:
        """Takes the source code for the module we are processing,
        as well as the current context and returns a modified version of it."""
        raise NotImplementedError


@dataclass
class _LazyActionMixin(Generic[K, T], BaseAction):
    node: K

    def build(self) -> T:
        """Create the replacement node."""
        raise NotImplementedError

    def branch(self) -> K:
        """Return a full copy of the original node."""
        return copy.deepcopy(self.node)


@_hint("deprecated_alias", "Action")
@dataclass
class LazyReplace(_LazyActionMixin[ast.AST, ast.AST]):
    """Replaces the code segment of the given
    node with the re-synthesized version of the
    built target (via build())."""

    def apply(self, context: Context, source: str) -> str:
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


@dataclass
class Action(LazyReplace):
    def __post_init__(self, *args, **kwargs):
        warnings.warn(
            f"{type(self).__name__!r} is deprecated, use"
            f" {type(self).__base__.__name__!r} instead",
            DeprecationWarning,
            stacklevel=3,
        )
        with suppress(AttributeError):
            super().__post_init__(*args, **kwargs)


@_hint("deprecated_alias", "ReplacementAction")
@dataclass
class Replace(LazyReplace):
    """Replaces the code segment of the given
    node with the re-synthesized version of the
    given target."""

    target: ast.AST

    def build(self) -> ast.AST:
        return self.target


@dataclass
class ReplacementAction(Replace):
    def __post_init__(self, *args, **kwargs):
        warnings.warn(
            f"{type(self).__name__!r} is deprecated, use"
            f" {type(self).__base__.__name__!r} instead",
            DeprecationWarning,
            stacklevel=3,
        )
        with suppress(AttributeError):
            super().__post_init__(*args, **kwargs)


@_hint("deprecated_alias", "NewStatementAction")
@dataclass
class LazyInsertAfter(_LazyActionMixin[ast.stmt, ast.stmt]):
    """Inserts the built target right
    after the given node."""

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


@dataclass
class NewStatementAction(LazyInsertAfter):
    def __post_init__(self, *args, **kwargs):
        warnings.warn(
            f"{type(self).__name__!r} is deprecated, use"
            f" {type(self).__base__.__name__!r} instead",
            DeprecationWarning,
            stacklevel=3,
        )
        with suppress(AttributeError):
            super().__post_init__(*args, **kwargs)


@_hint("deprecated_alias", "TargetedNewStatementAction")
@dataclass
class InsertAfter(LazyInsertAfter):
    """Inserts the given target right
    after the given node."""

    target: ast.stmt

    def build(self) -> ast.stmt:
        return self.target


@dataclass
class TargetedNewStatementAction(InsertAfter):
    def __post_init__(self, *args, **kwargs):
        warnings.warn(
            f"{type(self).__name__!r} is deprecated, use"
            f" {type(self).__base__.__name__!r} instead",
            DeprecationWarning,
            stacklevel=3,
        )
        with suppress(AttributeError):
            super().__post_init__(*args, **kwargs)
