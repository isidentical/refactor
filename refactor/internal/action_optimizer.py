import ast
from contextlib import suppress
from typing import Callable, List, Optional

from refactor import common
from refactor.actions import BaseAction, Replace, _Rename
from refactor.context import Context
from refactor.internal.ast_delta import ChangeType, ast_delta
from refactor.internal.position_provider import infer_identifier_position

OptimizerType = Callable[[BaseAction, Context], Optional[BaseAction]]

_OPTIMIZATIONS: List[OptimizerType] = []

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


@register_optimizer
def replace_optimizer(
    action: BaseAction, context: Context
) -> Optional[BaseAction]:
    assert isinstance(action, Replace)

    change_provider = ast_delta(action.node, action.target)
    assert (change := next(change_provider, None))

    # We only want to deal with a single change. So if this
    # advances one more, we'll give up.
    assert not next(change_provider, None)

    if change.change_type is ChangeType.FULL:
        return Replace(change.original_node, change.new_node)
    elif change.change_type is ChangeType.FIELD_VALUE:
        # We only support renaming of definitions for now,
        # since they are the most needed case.
        if is_named_node(change.original_node) and change.on_field == "name":
            identifier_span = infer_identifier_position(
                change.original_node, change.original_node.name, context
            )
            assert identifier_span is not None
            return _Rename(
                change.original_node, change.new_node, identifier_span
            )
