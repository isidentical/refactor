from __future__ import annotations

import ast
from functools import lru_cache
from typing import Any, Dict, Tuple, Type


def negate(node: ast.expr) -> ast.UnaryOp:
    """Negate the given `node`."""
    return ast.UnaryOp(op=ast.Not(), operand=node)


def apply_condition(condition: bool, node: ast.expr) -> ast.expr:
    """Negate the node if `condition` is a falsy value."""
    if condition:
        return node
    else:
        return negate(node)


def is_truthy(op: ast.cmpop) -> bool:
    """Return `True` for comparison operators that
    depend on truthness (`==`, `is`, `in`), `False`
    for others."""
    return isinstance(op, (ast.Eq, ast.In, ast.Is))


def is_contextful(node: ast.AST) -> bool:
    """Check if the node is a context starter (e.g
    a function definition)."""
    return isinstance(
        node,
        (
            ast.Module,
            ast.ClassDef,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.Lambda,
        ),
    )


def pascal_to_snake(name: str) -> str:
    """Convert a name written in pascal case notation to
    snake case."""

    new_string = str()
    for is_tail, part in enumerate(name):
        if is_tail and part.isupper():
            new_string += "_"
        new_string += part

    return new_string.lower()


def find_closest(node: ast.AST, *targets: ast.AST) -> ast.AST:
    """Find the closest node against given sequence
    of targets (absolute distance from starting points)."""
    assert len(targets) >= 0

    def closest(target):
        return (
            abs(target.lineno - node.lineno),
            abs(target.col_offset - node.col_offset),
        )

    sorted_targets = sorted(targets, key=closest)
    return sorted_targets[0]


_POSITIONAL_ATTRIBUTES = (
    "lineno",
    "col_offset",
    "end_lineno",
    "end_col_offset",
)
_POSITIONAL_ATTRIBUTES_SET = frozenset(_POSITIONAL_ATTRIBUTES)


@lru_cache(512)
def has_positions(node_type: Type[ast.AST]) -> bool:
    """Return `True` if the given `node_type` tracks
    source positions."""
    return _POSITIONAL_ATTRIBUTES_SET.issubset(node_type._attributes)


def position_for(node):
    return tuple(
        getattr(node, attribute) for attribute in _POSITIONAL_ATTRIBUTES
    )


class Singleton:
    def __init_subclass__(cls) -> None:
        cls._instances: Dict[Tuple[Any, ...], Singleton] = {}  # type: ignore

    def __new__(cls, *args: Any) -> Singleton:
        if not cls._instances.get(args):
            cls._instances[args] = super().__new__(cls)
        return cls._instances[args]
