from __future__ import annotations

import ast
import io
import tokenize
from collections import UserList
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from typing import (
    Any,
    Generator,
    Iterator,
    List,
    Optional,
    Protocol,
    Tuple,
    Union,
)

from refactor import common


def precise_parse(source: str) -> ast.Module:
    tree = ast.parse(source)
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.stmt)]
    # TO-DO: non-standalone comments should probably handle
    # the indentation better.
    comments = _get_comments(source)

    for comment in comments:
        closest = common.find_closest(comment, *nodes)
        closest.__dict__.setdefault("comments", []).append(comment)

    return tree


@dataclass
class Lines(UserList):

    lines: List[str]
    trailing_newline: bool = False

    def __post_init__(self) -> None:
        super().__init__(self.lines)
        self.lines = self.data

    def join(self) -> str:
        source = "\n".join(self.data)
        if self.trailing_newline:
            source += "\n"
        return source

    def apply_indentation(
        self, indentation: str, *, start_prefix: str = "", end_suffix: str = ""
    ) -> None:
        for index, line in enumerate(self.data):
            if index == 0:
                self.data[index] = indentation + start_prefix + line
            else:
                self.data[index] = indentation + line

        if len(self.data) >= 1:
            self.data[-1] += end_suffix


def split_lines(source: str) -> Lines:
    # TODO: https://github.com/python/cpython/blob/83d1430ee5b8008631e7f2a75447e740eed065c1/Lib/ast.py#L299-L321
    trailing_newline = False
    if len(source) >= 1:
        trailing_newline = source[-1] == "\n"

    return Lines(source.splitlines(), trailing_newline)


class Unparser(Protocol):
    def __init__(self, source: str, *args: Any, **kwargs: Any) -> None:
        ...  # pragma: no cover

    def unparse(self, node: ast.AST) -> str:
        ...  # pragma: no cover


class BaseUnparser(ast._Unparser):  # type: ignore
    # Normally ast._Unparser is a private API
    # though since it doesn't tend to change
    # often, we could simply have a base class
    # which will act like a wrapper for backwards
    # incompatible changes and let the refactor
    # users to override it.

    source: Optional[str]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.source = kwargs.pop("source", None)
        super().__init__(*args, **kwargs)

    def unparse(self, node: ast.AST) -> str:
        return self.visit(node)

    @cached_property
    def tokens(self) -> Tuple[tokenize.TokenInfo, ...]:
        buffer = io.StringIO(self.source)
        token_stream = tokenize.generate_tokens(buffer.readline)
        return tuple(token_stream)

    @contextmanager
    def indented(self) -> Generator[None, None, None]:
        self._indent += 1
        yield
        self._indent -= 1


class PreciseUnparser(BaseUnparser):
    """
    Try to locate precise textual versions of child nodes by
    bi-directional AST equivalence with the versions that exist
    on the source.
    """

    def traverse(self, node: Union[List[ast.AST], ast.AST]) -> None:
        if isinstance(node, list) or self.source is None:
            return super().traverse(node)

        if isinstance(node, ast.stmt):
            before, sticked, after = _group_comments(node)
            for comment in before:
                self.fill()
                self.write(comment.value)

        did_retrieve = self.maybe_retrieve(node)
        if not did_retrieve:
            super().traverse(node)

        if isinstance(node, ast.stmt):
            if sticked:
                self.write(sticked.value)

            for comment in after:
                self.fill()
                self.write(comment.value)

    def maybe_retrieve(self, node: ast.AST) -> bool:
        # Process:
        #   - Check whether the unparser has access to the
        #     current source code.
        #   - Check whether the given node is an expression
        #     or statement.
        #   - Try retrieving the source segment
        #   - If that succeeds, try parsing that segment
        #   - Ensure the ASTs are identical
        #   - Write-off the original source

        if self.source is None:
            return False

        if not isinstance(node, (ast.stmt, ast.expr)):
            return False

        segment = common.get_source_segment(self.source, node)
        if segment is None:
            return False

        if isinstance(node, ast.expr):
            source_revision = common.wrap_with_parens(segment)
        else:
            source_revision = segment

        try:
            tree = ast.parse(source_revision)
        except SyntaxError:
            return False

        if len(tree.body) != 1:
            return False

        retrieved_node: ast.AST
        [retrieved_node] = tree.body

        # If this is a pure expression, then unpack
        # the actual value.
        if isinstance(node, ast.expr) and isinstance(retrieved_node, ast.Expr):
            retrieved_node = retrieved_node.value

        if is_same_ast := common.compare_ast(retrieved_node, node):
            self.retrieve_segment(node, segment)

        return is_same_ast

    def retrieve_segment(self, node: ast.AST, segment: str) -> None:
        if isinstance(node, ast.stmt):
            self.fill()

        self.write(segment)


UNPARSER_BACKENDS = {"fast": BaseUnparser, "precise": PreciseUnparser}

# Since AST does not preserve individual comments, it is really
# tricky to allow full-statement refactors without losing a bit
# of information. To get around this, we introduce the ast.Comment
# which is like a regular statement and gets unparsed into a single
# line comment.


def _patch_ast(cls):
    setattr(ast, cls.__name__, cls)
    return cls


@_patch_ast
class whitespace(ast.AST):
    """whitespace = Comment(string value)"""

    _attributes = (
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
    )


@_patch_ast
class Comment(whitespace):
    """Comment(string value, bool is_standalone)"""

    _fields = ("value", "is_standalone")


def _get_comments(source: str) -> Iterator[Comment]:
    buffer = io.StringIO(source)

    for token_info in tokenize.generate_tokens(buffer.readline):
        if token_info.type != tokenize.COMMENT:
            continue

        is_standalone = token_info.string.strip() == token_info.line.strip()
        yield Comment(
            token_info.string,
            is_standalone,
            lineno=token_info.start[0],
            col_offset=token_info.start[1],
            end_lineno=token_info.end[0],
            end_col_offset=token_info.end[1],
        )


def _group_comments(
    node: ast.stmt,
) -> Tuple[List[Comment], Optional[Comment], List[Comment]]:
    before, sticked, after = [], None, []

    comments = getattr(node, "comments", [])
    for comment in comments:
        if comment.lineno < node.lineno:
            before.append(comment)
        elif comment.lineno == node.lineno:
            sticked = comment
        else:
            after.append(comment)

    return before, sticked, after
