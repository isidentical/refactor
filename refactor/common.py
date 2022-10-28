from __future__ import annotations

import ast
import copy
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import cache, singledispatch, wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

if TYPE_CHECKING:
    from refactor.context import Context

T = TypeVar("T")
C = TypeVar("C")
PositionType = tuple[int, int, int, int]


@dataclass
class _FileInfo:
    """Represents information regarding the source code (the
    file it was read from, the encoding, etc.)"""

    path: Path | None = None
    encoding: str | None = None

    def get_encoding(self) -> str:
        """Return the encoding for this file (if it doesn't exist,
        it returns the default encoding -- utf8)."""
        from refactor.ast import DEFAULT_ENCODING

        return self.encoding or DEFAULT_ENCODING


def clone(node: T) -> T:
    """Clone the given ``node``."""
    return copy.deepcopy(node)


def negate(node: ast.expr) -> ast.UnaryOp:
    """Negate the given ``node``."""
    return ast.UnaryOp(op=ast.Not(), operand=node)


def apply_condition(condition: bool, node: ast.expr) -> ast.expr:
    """Negate the given ``node`` if the given ``condition`` is
    a non-truthy value."""
    if condition:
        return node
    else:
        return negate(node)


def wrap_with_parens(text: str) -> str:
    """Wrap the given `text` with parens."""
    return "(" + text + ")"


_OPERATOR_MAP = {
    ast.Eq: True,
    ast.In: True,
    ast.Is: True,
    ast.NotEq: False,
    ast.NotIn: False,
    ast.IsNot: False,
}


def is_truthy(op: ast.cmpop) -> bool | None:
    """Return `True` for truth-based comparison
    operators (e.g `==`, `is`, `in`), `False` for
    falsity-based operators (e.g `!=`, `is not`, `not in`)
    and `None` for others."""
    return _OPERATOR_MAP.get(type(op))


def _type_checker(
    *types: type, binders: Iterable[Callable[[type], bool]] = ()
) -> Callable[[Any], bool]:
    binders = [getattr(binder, "fast_checker", binder) for binder in binders]

    @cache
    def checker(node_type: type) -> bool:
        result = issubclass(node_type, types)
        return result or any(binder(node_type) for binder in binders)

    def top_level_checker(node: Any) -> bool:
        return checker(type(node))  # type: ignore

    top_level_checker.fast_checker = checker

    return top_level_checker


is_comprehension = _type_checker(
    ast.SetComp, ast.ListComp, ast.DictComp, ast.GeneratorExp
)
is_function = _type_checker(ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
is_contextful = _type_checker(
    ast.Module, ast.ClassDef, binders=[is_function, is_comprehension]
)


def compare_ast(left: ast.AST, right: ast.AST, /) -> bool:
    """Compare 2 AST nodes."""
    return ast.dump(left) == ast.dump(right)


def _guarded(exc_type: type[BaseException], /, default: Any = None) -> Any:
    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exc_type:
                return default

        return inner

    return outer


def _get_known_location_from_source(source: str, location: PositionType) -> str | None:
    start_line, start_col, end_line, end_col = location
    # Python AST line numbers are 1-indexed
    start_line -= 1
    end_line -= 1

    lines = source.splitlines()
    if len(lines) < end_line + 1:
        return None

    if start_line == end_line:
        return lines[start_line][start_col:end_col]

    start, *middle, end = lines[start_line : end_line + 1]
    new_lines = (start[start_col:], *middle, end[:end_col])
    return "\n".join(new_lines)


@_guarded(Exception)
def get_source_segment(source: str, node: ast.AST) -> str | None:
    """Faster (and less-precise) implementation of
    ast.get_source_segment"""

    try:
        node_position = position_for(node)
    except AttributeError:
        return None
    else:
        return _get_known_location_from_source(source, node_position)


def pascal_to_snake(name: str) -> str:
    """Convert the given ``name`` from pascal case to
    snake case."""

    new_string = ""
    for is_tail, part in enumerate(name):
        if is_tail and part.isupper():
            new_string += "_"
        new_string += part

    return new_string.lower()


def find_indent(source: str) -> tuple[str, str]:
    """Split the given line into the current indentation
    and the remaining characters."""
    index = 0
    for index, char in enumerate(source, 1):
        if not char.isspace():
            index -= 1
            break
    return source[:index], source[index:]


def find_closest(node: ast.AST, *targets: ast.AST) -> ast.AST:
    """Find the closest node to the given ``node`` from the given
    sequence of ``targets`` (uses absolute distance from starting points)."""
    if not len(targets) >= 1:
        raise ValueError("condition failed: len(targets) >= 1")

    node_positions = position_for(node)

    def closest(target: ast.AST) -> tuple[int, ...]:
        target_positions = position_for(target)
        return tuple(
            abs(target_position - node_position)
            for target_position, node_position in zip(target_positions, node_positions)
        )

    sorted_targets = sorted(targets, key=closest)
    return sorted_targets[0]


def extract_from_text(text: str) -> ast.AST:
    """Extract the first AST node from the given ``text``'s
    parsed AST."""
    return ast.parse(text).body[0]


_POSITIONAL_ATTRIBUTES = (
    "lineno",
    "col_offset",
    "end_lineno",
    "end_col_offset",
)
_POSITIONAL_ATTRIBUTES_SET = frozenset(_POSITIONAL_ATTRIBUTES)


@cache  # type: ignore
def has_positions(node_type: type[ast.AST]) -> bool:
    """Return `True` if the given ``node_type`` tracks
    source positions."""
    return _POSITIONAL_ATTRIBUTES_SET.issubset(node_type._attributes)


def position_for(node: ast.AST) -> PositionType:
    """Return a 4-item tuple of positions for the given ``node``."""
    positions = tuple(getattr(node, attribute) for attribute in _POSITIONAL_ATTRIBUTES)
    return cast(PositionType, positions)


def unpack_lhs(node: ast.AST) -> Iterator[str]:
    """Unpack assignment targets to individual identifiers"""
    if isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            yield from unpack_lhs(element)
    else:
        yield ast.unparse(node)


def next_statement_of(node: ast.stmt, context: Context) -> ast.stmt | None:
    """Get the statement that follows ``node`` in the same syntactical block."""
    parent_field, parent = context.ancestry.infer(node)
    if not parent_field is not None:
        raise ValueError("condition failed: parent_field is not None")
    if not parent is not None:
        raise ValueError("condition failed: parent is not None")
    parent_field_val = getattr(parent, parent_field)
    if not isinstance(parent_field_val, list):
        return None

    index = parent_field_val.index(node)
    try:
        return parent_field_val[index + 1]
    except IndexError:
        return None


def walk_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Like regular :py:func:`ast.walk` but only walks within the
    current scope."""
    todo = deque(_walker(node))
    while todo:
        node = todo.popleft()
        todo.extend(_walker(node, top_level=True))
        yield node


@singledispatch
def _walker(node: ast.AST, top_level: bool = False) -> Iterator[ast.AST]:
    yield from ast.iter_child_nodes(node)


# TODO: Symbol table leaks assignment expressions to
# the next suitable context if they are used within
# comprehensions.
@_walker.register(ast.Module)
@_walker.register(ast.SetComp)
@_walker.register(ast.ListComp)
@_walker.register(ast.DictComp)
@_walker.register(ast.GeneratorExp)
def _walk_ignore(node: ast.AST, top_level: bool = False) -> Iterator[ast.AST]:
    if not top_level:
        yield from ast.iter_child_nodes(node)


@_walker.register(ast.FunctionDef)
@_walker.register(ast.AsyncFunctionDef)
def _walk_func(node: ast.AST, top_level: bool = False) -> Iterator[ast.AST]:
    if top_level:
        yield from node.decorator_list
        yield from node.args.defaults
        yield from _walk_optional_list(node.args.kw_defaults)
        yield from _walk_optional(node.returns)
    else:
        yield from _walk_args(node.args)
        yield from node.body


@_walker.register(ast.Lambda)
def _walk_lambda(node: ast.AST, top_level: bool = False) -> Iterator[ast.AST]:
    if top_level:
        yield from node.args.defaults
        yield from _walk_optional_list(node.args.kw_defaults)
    else:
        yield from _walk_args(node.args)
        yield node.body


@_walker.register(ast.ClassDef)
def _walk_class(node: ast.AST, top_level: bool = False) -> Iterator[ast.AST]:
    if top_level:
        yield from node.decorator_list
        yield from node.bases
        yield from node.keywords
    else:
        yield from node.body


def _walk_args(node: ast.arguments) -> list[ast.arg]:
    args = node.posonlyargs + node.args + node.kwonlyargs
    if node.vararg:
        args.append(node.vararg)
    if node.kwarg:
        args.append(node.kwarg)
    return args


def _walk_optional_list(nodes: list[ast.AST | None]) -> Iterator[ast.AST]:
    for node in nodes:
        yield from _walk_optional(node)


def _walk_optional(node: ast.AST | None) -> Iterator[ast.AST]:
    if node:
        yield node


class _Singleton:
    def __init_subclass__(cls) -> None:
        cls._instances: dict[tuple[Any, ...], _Singleton] = {}  # type: ignore

    def __new__(cls, *args: Any) -> _Singleton:
        if not cls._instances.get(args):
            cls._instances[args] = super().__new__(cls)
        return cls._instances[args]


def _hint(handler: str, *args: Any, **kwargs: Any) -> Callable[[C], C]:
    """Internal hint function for global refactors."""

    def wrapper(obj: C) -> C:
        return obj

    return wrapper


def _allow_asserts(func: Callable[..., T]) -> Callable[..., T]:
    """Internal function to allow 'real' asserts in the Refactor core (so that even
    if there are AssertionError's, they won't be hidden)."""

    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AssertionError as exc:
            raise RuntimeError(
                "An internal problem occurred in the Refactor core. "
                "Please report this on the issue tracker."
            ) from exc

    return inner
