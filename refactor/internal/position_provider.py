from __future__ import annotations

import ast
import tokenize
from collections.abc import Iterator
from functools import singledispatch
from itertools import chain
from typing import Callable

from refactor import common
from refactor.ast import Lines, split_lines
from refactor.context import Context


def _line_wrapper(lines: Lines) -> Callable[[], str]:
    line_iterator = iter(lines)

    def read_line() -> str:
        return next(line_iterator, "")

    return read_line


_SPACE_TOKENS = frozenset(
    (
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.COMMENT,
        tokenize.INDENT,
        tokenize.DEDENT,
    )
)


def _ignore_space(
    token_iterator: Iterator[tokenize.TokenInfo],
) -> Iterator[tokenize.TokenInfo]:
    for token in token_iterator:
        if token.type not in _SPACE_TOKENS:
            yield token


@singledispatch
def infer_identifier_position(
    node: ast.AST,
    identifier_value: str,
    context: Context,
) -> common.PositionType | None:
    ...


EXPECTED_KEYWORDS = {
    ast.FunctionDef: ["def"],
    ast.AsyncFunctionDef: ["async", "def"],
    ast.ClassDef: ["class"],
}


@infer_identifier_position.register(ast.ClassDef)
@infer_identifier_position.register(ast.FunctionDef)
@infer_identifier_position.register(ast.AsyncFunctionDef)
def infer_definition_name(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    identifier_value: str,
    context: Context,
) -> common.PositionType | None:
    source_segment = common.get_source_segment(context.source, node)
    if source_segment is None:
        return None

    lines = split_lines(source_segment)
    tokens = _ignore_space(tokenize.generate_tokens(_line_wrapper(lines)))

    def _next_token() -> tokenize.TokenInfo | None:
        try:
            return next(tokens, None)
        except (SyntaxError, tokenize.TokenError):
            return None

    def _expect_token(
        expected_type: int, expected_str: str
    ) -> tokenize.TokenInfo | None:
        if (
            (next_token := _next_token())
            and next_token.exact_type == expected_type
            and next_token.string == expected_str
        ):
            return next_token

    next_token = None
    for name in chain(EXPECTED_KEYWORDS[type(node)], [identifier_value]):
        next_token = _expect_token(tokenize.NAME, name)
        if next_token is None:
            return None

    assert next_token is not None
    lineno, col_offset = next_token.start
    end_lineno, end_col_offset = next_token.end
    start_line, start_col = node.lineno - 1, node.col_offset
    return (
        start_line + lineno,
        start_col + col_offset,
        start_line + end_lineno,
        start_col + end_col_offset,
    )
