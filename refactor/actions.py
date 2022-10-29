from __future__ import annotations

import ast
import warnings
from contextlib import suppress
from dataclasses import dataclass, field, replace
from typing import Generic, TypeVar, cast

from refactor.ast import split_lines
from refactor.common import PositionType, _hint, clone, find_indent, position_for
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
    "Erase",
    "EraseOrReplace",
    "InvalidActionError",
]


class InvalidActionError(ValueError):
    """An improper usage of an action."""


class BaseAction:
    """A source code transformation action."""

    def apply(self, context: Context, source: str) -> str:
        """Takes the bound :py:class:`refactor.context.Context` and
        the source code of the current module and returns the transformed
        version."""
        raise NotImplementedError

    def _stack_effect(self) -> tuple[ast.AST, int]:
        """Return the stack effect of this action (relative to the node it returns.)"""
        raise NotImplementedError("This action can't be chained, yet.")

    def _replace_input(self, node: ast.AST) -> BaseAction:
        """Replace the input node (source anchor) with the given node."""
        raise NotImplementedError("This action can't be chained, yet.")


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
        """Create the new node."""
        raise NotImplementedError

    def branch(self) -> K:
        """Return a full copy of the original node."""
        return clone(self.node)

    def _replace_input(self, node: ast.AST) -> _LazyActionMixin[K, T]:
        return replace(self, node=node)


class _ReplaceCodeSegmentAction(BaseAction):
    def apply(self, context: Context, source: str) -> str:
        lines = split_lines(source, encoding=context.file_info.get_encoding())
        (
            lineno,
            col_offset,
            end_lineno,
            end_col_offset,
        ) = self._get_segment_span(context)

        view = slice(lineno - 1, end_lineno)
        source_lines = lines[view]

        indentation, start_prefix = find_indent(source_lines[0][:col_offset])
        end_suffix = source_lines[-1][end_col_offset:]
        replacement = split_lines(self._resynthesize(context))
        replacement.apply_indentation(
            indentation, start_prefix=start_prefix, end_suffix=end_suffix
        )

        lines[view] = replacement
        return lines.join()

    def _get_segment_span(self, context: Context) -> PositionType:
        raise NotImplementedError

    def _resynthesize(self, context: Context) -> str:
        raise NotImplementedError


@_hint("deprecated_alias", "Action")
@dataclass
class LazyReplace(_ReplaceCodeSegmentAction, _LazyActionMixin[ast.AST, ast.AST]):
    """Transforms the code segment of the given `node` with
    the re-synthesized version :py:meth:`LazyReplace.build`'s
    output.

    .. note::
        Subclasses of :py:class:`LazyReplace` must override
        :py:meth:`LazyReplace.build`.
    """

    def _get_segment_span(self, context: Context) -> PositionType:
        return position_for(self.node)

    def _resynthesize(self, context: Context) -> str:
        return context.unparse(self.build())

    def _stack_effect(self) -> tuple[ast.AST, int]:
        # Replacing a statement with another one won't cause any shifts
        # in the block.
        return (self.node, 0)


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
        lines = split_lines(source, encoding=context.file_info.get_encoding())
        indentation, start_prefix = find_indent(
            lines[self.node.lineno - 1][: self.node.col_offset]
        )

        replacement = split_lines(context.unparse(self.build()))
        replacement.apply_indentation(indentation, start_prefix=start_prefix)

        original_node_end = cast(int, self.node.end_lineno) - 1
        if lines[original_node_end].endswith(lines._newline_type):
            replacement[-1] += lines._newline_type
        else:
            # If the original anchor's last line doesn't end with a newline,
            # then we need to also prevent our new source from ending with
            # a newline.
            replacement[0] = lines._newline_type + replacement[0]

        for line in reversed(replacement):
            lines.insert(original_node_end + 1, line)

        return lines.join()

    def _stack_effect(self) -> tuple[ast.AST, int]:
        # Adding a statement right after the node will need to be reflected
        # in the block.
        return (self.node, 1)


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


@dataclass
class _Rename(Replace):
    identifier_span: PositionType

    def _get_segment_span(self, context: Context) -> PositionType:
        return self.identifier_span

    def _resynthesize(self, context: Context) -> str:
        return self.target.name


@dataclass
class Erase(_ReplaceCodeSegmentAction):
    """Erases the given `node` statement from source code. Be careful when
    using this action, as it can't remove required statements (e.g. if the `node`
    is the only child statement of the parent node).

    .. note::
        If you want to quickly get rid of a statement without doing your own analysis
        first (in order to determine whether it is required or not), you can use the
        :py:class:`EraseOrReplace`.
    """

    node: ast.stmt

    def is_critical_node(self, context: Context) -> bool:
        parent_field, parent_node = context.ancestry.infer(self.node)
        if parent_field is None or parent_node is None:
            if isinstance(self.node, ast.Module):
                raise ValueError("Can't erase ast.Module")
            else:
                raise RuntimeError(f"Couldn't find the parent of {self.node}.")

        parent_field_value = getattr(parent_node, parent_field)
        return isinstance(parent_field_value, list) and len(parent_field_value) == 1

    def _get_segment_span(self, context: Context) -> PositionType:
        return position_for(self.node)

    def _resynthesize(self, context: Context) -> str:
        if self.is_critical_node(context):
            raise InvalidActionError(
                "Erasing the following statement will end up with an empty"
                " block. Consider using the erase_or_replace function"
                f" instead.\nTarget node: {self.node} @"
                f" {context.file or '<string>'}:{self.node.lineno}"
            )
        else:
            return ""

    def _stack_effect(self) -> tuple[ast.AST, int]:
        # Erasing a single node mean positions of all the followinng statements will
        # need to reduced by 1.
        return (self.node, -1)

    def _replace_input(self, node: ast.AST) -> Erase:
        return replace(self, node=node)


@dataclass
class EraseOrReplace(Erase):
    """Erases the given `node` statement if it is not required (e.g. if it is not the
    only child statement of the parent node). Otherwise replaces it with the re-synthesized
    version of the given `target` statement (by default, it is ``pass``).
    """

    target: ast.stmt = field(default_factory=ast.Pass)

    def _resynthesize(self, context: Context) -> str:
        if self.is_critical_node(context):
            return context.unparse(self.target)
        else:
            return ""

    def _stack_effect(self) -> tuple[ast.AST, int]:
        raise NotImplementedError("EraseOrReplace doesn't support chained actions.")
