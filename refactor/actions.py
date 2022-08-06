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
    """A source code transformation action."""

    def apply(self, context: Context, source: str) -> str:
        """Takes the bound :py:class:`refactor.context.Context` and
        the source code of the current module and returns the transformed
        version."""
        raise NotImplementedError


class _DeprecatedAliasMixin:
    def __post_init__(self, *args, **kwargs):
        warnings.warn(
            f"{type(self).__name__!r} is deprecated, use"
            f" {type(self).__base__.__name__!r} instead",
            DeprecationWarning,
            stacklevel=3,
        )
        with suppress(AttributeError):
            super().__post_init__(*args, **kwargs)


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
    """Transforms the code segment of the given `node` with
    the re-synthesized version :py:meth:`LazyReplace.build`'s
    output.

    .. note::
        Subclasses of :py:class:`LazyReplace` must override
        :py:meth:`LazyReplace.build`.
    """

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
class Action(LazyReplace, _DeprecatedAliasMixin):
    ...


@_hint("deprecated_alias", "ReplacementAction")
@dataclass
class Replace(LazyReplace):
    """Transforms the code segment of the given `node` with
    the re-synthesized version of `target`."""

    target: ast.AST

    def build(self) -> ast.AST:
        return self.target


@dataclass
class ReplacementAction(Replace, _DeprecatedAliasMixin):
    ...


@_hint("deprecated_alias", "NewStatementAction")
@dataclass
class LazyInsertAfter(_LazyActionMixin[ast.stmt, ast.stmt]):
    """Inserts the re-synthesized version :py:meth:`LazyInsertAfter.build`'s
    output right after the given `node`.

    .. note::
        Subclasses of :py:class:`LazyInsertAfter` must override
        :py:meth:`LazyInsertAfter.build`.

    .. note::
        This action requires both the `node` and the built target to be statements.
    """

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
class NewStatementAction(LazyInsertAfter, _DeprecatedAliasMixin):
    ...


@_hint("deprecated_alias", "TargetedNewStatementAction")
@dataclass
class InsertAfter(LazyInsertAfter):
    """Inserts the re-synthesized version of given `target` right after
    the given `node`.

    .. note::
        This action requires both the `node` and `target` to be a statements.
    """

    target: ast.stmt

    def build(self) -> ast.stmt:
        return self.target


@dataclass
class TargetedNewStatementAction(InsertAfter, _DeprecatedAliasMixin):
    ...
