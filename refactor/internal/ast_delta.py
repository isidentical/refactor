from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum, auto
from functools import cache, partial
from typing import Any, cast

_MISSING = object()
_CONSTANT_FIELDS: dict[type[ast.AST], list[str]] = {ast.Constant: ["value"]}
if hasattr(ast, "MatchSingleton"):
    _CONSTANT_FIELDS[ast.MatchSingleton] = ["value"]


class _Continue(Exception):
    pass


class IncompleteASTError(Exception):
    pass


class ChangeType(Enum):
    FULL = auto()

    FIELD_ADDITION = auto()
    FIELD_REMOVAL = auto()

    ITEM_VALUE = auto()
    FIELD_VALUE = auto()
    FIELD_SIZE = auto()

    UNINFERRABLE = auto()


@dataclass
class ChangeSet:
    change_type: ChangeType
    original_node: Any
    new_node: Any
    on_field: str | None = None
    on_index: int | None = None


@cache
def _is_constant(node_type: type[ast.AST], field: str) -> bool:
    return field in _CONSTANT_FIELDS.get(node_type, [])


def _incomplete_if(condition: bool) -> None:
    if condition:
        raise IncompleteASTError


def _change_if(condition: bool, *args: Any, **kwargs: Any) -> Iterator[ChangeSet]:
    if condition:
        yield ChangeSet(*args, **kwargs)
        raise _Continue


def ast_delta(baseline: ast.AST, new_node: ast.AST) -> Iterator[ChangeSet]:
    baseline_type = type(baseline)
    if baseline_type is not type(new_node):
        yield ChangeSet(ChangeType.FULL, baseline, new_node)
        return None

    for field in baseline_type._fields:
        with suppress(_Continue):
            # There are 3 AST field types:
            #   - lists
            #   - AST nodes (or None)
            #   - atomic Python types (int, str, bytes, None, etc.)
            #
            # For the same type, if a field on a node is one of these
            # the same has to be true for the other node.

            baseline_value, new_value = getattr(baseline, field), getattr(
                new_node, field, _MISSING
            )
            _incomplete_if(new_value is _MISSING)

            _field_change_if = partial(
                _change_if,
                original_node=baseline,
                new_node=new_node,
                on_field=field,
            )

            if not _is_constant(baseline_type, field):  # type: ignore
                if baseline_value is None:
                    yield from _field_change_if(
                        new_value is not None, ChangeType.FIELD_ADDITION
                    )
                else:
                    yield from _field_change_if(
                        new_value is None, ChangeType.FIELD_REMOVAL
                    )

            if isinstance(baseline_value, ast.AST):
                _incomplete_if(not isinstance(new_value, ast.AST))
                yield from ast_delta(baseline_value, cast(ast.AST, new_value))
            elif isinstance(baseline_value, list):
                _incomplete_if(not isinstance(new_value, list))
                yield from _ast_sequence_delta(baseline, new_node, field)
            else:
                yield from _field_change_if(
                    baseline_value != new_value, ChangeType.FIELD_VALUE
                )


def _ast_sequence_delta(
    baseline: ast.AST,
    new_node: ast.AST,
    field: str,
) -> Iterator[ChangeSet]:
    base_sequence: list[Any] = getattr(baseline, field)
    new_sequence: list[Any] = getattr(new_node, field)

    # TODO: distinguish insertions to the start and the end
    if len(base_sequence) != len(new_sequence):
        yield ChangeSet(ChangeType.FIELD_SIZE, baseline, new_node, on_field=field)
        return None

    for index, (base_item, new_item) in enumerate(zip(base_sequence, new_sequence)):
        _item_change_if = partial(
            _change_if,
            original_node=baseline,
            new_node=new_node,
            on_field=field,
            on_index=index,
        )
        with suppress(_Continue):
            if isinstance(base_item, ast.AST) or base_item is None:
                if new_item is None or base_item is None:
                    yield from _item_change_if(
                        new_item is not base_item, ChangeType.FULL
                    )
                else:
                    _incomplete_if(not isinstance(new_item, ast.AST))
                    yield from ast_delta(base_item, new_item)
            else:
                yield from _item_change_if(new_item != base_item, ChangeType.ITEM_VALUE)
