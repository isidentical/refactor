import ast
import tokenize
from functools import singledispatch
from itertools import chain
from typing import Callable, Iterator, Optional, Union

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
    identifier_field: str,
    context: Context,
) -> Optional[common.PositionType]:
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
    node: Union[ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef],
    identifier_field: str,
    context: Context,
) -> Optional[common.PositionType]:
    lines = split_lines(context.source)[node.lineno - 1 : node.end_lineno]
    tokens = _ignore_space(tokenize.generate_tokens(_line_wrapper(lines)))

    def _next_token(
        expected_type: int, expected_str: str
    ) -> Optional[tokenize.TokenInfo]:
        if (
            (next_token := next(tokens, None))  # type: ignore
            and next_token.exact_type == expected_type  # type: ignore
            and next_token.string == expected_str  # type: ignore
        ):
            return next_token

    next_token = None
    for name in chain(EXPECTED_KEYWORDS[type(node)], [node.name]):
        next_token = _next_token(tokenize.NAME, name)
        if next_token is None:
            return None

    assert next_token is not None
    lineno, col_offset = next_token.start
    end_lineno, end_col_offset = next_token.end
    return (
        node.lineno + lineno - 1,
        col_offset,
        node.lineno + end_lineno - 1,
        end_col_offset,
    )
