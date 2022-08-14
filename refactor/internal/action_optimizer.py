import ast
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial
from typing import Any, Iterator, List, Optional, cast

_MISSING = object()


class _Continue(Exception):
    pass


class IncompleteASTError(Exception):
    pass


class ChangeType(Enum):
    FULL = auto()

    FIELD_ADDITION = auto()
    FIELD_REMOVAL = auto()

    FIELD_VALUE = auto()
    FIELD_SIZE = auto()

    UNINFERRABLE = auto()


@dataclass
class ChangeSet:
    change_type: ChangeType
    original_value: Any
    new_value: Any
    on_field: Optional[str] = None


def _incomplete_if(condition: bool) -> None:
    if condition:
        raise IncompleteASTError


def _change_if(
    condition: bool, *args: Any, **kwargs: Any
) -> Iterator[ChangeSet]:
    if condition:
        yield ChangeSet(*args, **kwargs)
        raise _Continue


def ast_diff(baseline: ast.AST, new_node: ast.AST) -> Iterator[ChangeSet]:
    if type(baseline) is not type(new_node):
        yield ChangeSet(ChangeType.FULL, baseline, new_node)
        return None

    for field in type(baseline)._fields:
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
                original_value=baseline_value,
                new_value=new_value,
                on_field=field,
            )

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
                yield from ast_diff(baseline_value, cast(ast.AST, new_value))
            elif isinstance(baseline_value, list):
                _incomplete_if(not isinstance(new_value, list))
                yield from _sequence_diff(
                    field, baseline_value, cast(list, new_value)
                )
            else:
                yield from _field_change_if(
                    baseline_value != new_value, ChangeType.FIELD_VALUE
                )


def _sequence_diff(
    field: str, base_sequence: List[Any], new_sequence: List[Any]
) -> Iterator[ChangeSet]:
    # TODO: distinguish insertions to the start and the end
    if len(base_sequence) != len(new_sequence):
        yield ChangeSet(
            ChangeType.FIELD_SIZE, base_sequence, new_sequence, field
        )
        return None

    for base_item, new_item in zip(base_sequence, new_sequence):
        if not isinstance(base_item, ast.AST) or not isinstance(
            new_item, ast.AST
        ):
            yield ChangeSet(
                ChangeType.UNINFERRABLE, base_sequence, new_sequence, field
            )
            return None

        yield from ast_diff(base_item, new_item)
