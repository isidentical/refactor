from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import suppress
from typing import Callable, Optional

from refactor import common
from refactor.actions import BaseAction, Replace, _Rename
from refactor.context import Context
from refactor.internal.ast_delta import (
    ChangeSet,
    ChangeType,
    IncompleteASTError,
    ast_delta,
)
from refactor.internal.position_provider import infer_identifier_position

OptimizerType = Callable[[BaseAction, Context], Optional[BaseAction]]

_OPTIMIZATIONS: list[OptimizerType] = []

is_named_node = common._type_checker(
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef
)


def register_optimizer(func: OptimizerType) -> OptimizerType:
    _OPTIMIZATIONS.append(func)
    return func


def optimize(action: BaseAction, context: Context) -> BaseAction:
    # TODO: this is currently a single-pass optimizer, we might
    # want to do something more sophisticated later.
    for func in _OPTIMIZATIONS:
        with suppress(AssertionError):
            if optimized_action := func(action, context):
                action = optimized_action
    return action


def expect_changes(
    baseline: ast.AST, new_node: ast.AST, *, max_changes: int
) -> Iterator[ChangeSet]:
    change_generator = ast_delta(baseline, new_node)
    for _ in range(max_changes):
        assert (next_change := next(change_generator, None))
        yield next_change

    assert not next(change_generator, None)


@register_optimizer
@common._guarded(IncompleteASTError)
def rename_optimizer(action: BaseAction, context: Context) -> BaseAction | None:
    assert isinstance(action, Replace)
    assert is_named_node(action.node) and is_named_node(action.target)
    assert action.node.name != action.target.name

    [change] = expect_changes(action.node, action.target, max_changes=1)
    assert change.change_type is ChangeType.FIELD_VALUE
    assert change.original_node is action.node
    assert change.new_node is action.target
    assert change.on_field == "name"

    identifier_span = infer_identifier_position(
        change.original_node, change.original_node.name, context
    )
    assert identifier_span is not None
    return _Rename(change.original_node, change.new_node, identifier_span)
