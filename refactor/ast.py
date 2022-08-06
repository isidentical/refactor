import ast
import io
import tokenize
from collections import UserList
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from functools import cached_property
from typing import (
    Any,
    ContextManager,
    Generator,
    Iterator,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    Union,
    cast,
)

from refactor import common


@dataclass
class Lines(UserList):
    lines: List[str]
    trailing_newline: bool = False

    def __post_init__(self) -> None:
        super().__init__(self.lines)
        self.lines = self.data

    def join(self) -> str:
        """Return the combined source code."""
        source = "\n".join(self.data)
        if self.trailing_newline:
            source += "\n"
        return source

    def apply_indentation(
        self,
        indentation: str,
        *,
        start_prefix: str = "",
        end_suffix: str = "",
    ) -> None:
        """Apply the given indentation, optionally with start and end prefixes
        to the bound source lines."""

        for index, line in enumerate(self.data):
            if index == 0:
                self.data[index] = indentation + start_prefix + line
            else:
                self.data[index] = indentation + line

        if len(self.data) >= 1:
            self.data[-1] += end_suffix


def split_lines(source: str) -> Lines:
    """Split the given source code into lines and
    return a list-like object (:py:class:`refactor.ast.Lines`)."""

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
    """A public :py:class:`ast._Unparser` API that can
    be used to customize the AST re-synthesis process."""

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
    """A more precise version of the default unparser,
    with various improvements such as comment handling
    for major statements and child node recovery."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._visited_comment_lines: Set[int] = set()
        super().__init__(*args, **kwargs)

    def traverse(self, node: Union[List[ast.AST], ast.AST]) -> None:
        if isinstance(node, list) or self.source is None:
            return super().traverse(node)

        did_retrieve = self.maybe_retrieve(node)
        if not did_retrieve:
            super().traverse(node)

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

    @contextmanager
    def _collect_stmt_comments(self, node: ast.AST) -> Iterator[None]:
        def _write_if_unseen_comment(
            line_no: int,
            line: str,
            comment_begin: int,
        ) -> None:
            if line_no in self._visited_comment_lines:
                # We have already written this comment as the
                # end of another node. No need to re-write it.
                return

            self.fill()
            self.write(line[comment_begin:])
            self._visited_comment_lines.add(line_no)

        assert self.source is not None
        lines = self.source.splitlines()
        node_start, node_end = node.lineno - 1, cast(int, node.end_lineno)

        # Collect comments in the reverse order, so we can properly
        # identify the end of the current comment block.
        preceding_comments = []
        for offset, line in enumerate(reversed(lines[:node_start])):
            comment_begin = line.find("#")
            if comment_begin == -1 or comment_begin != node.col_offset:
                break

            preceding_comments.append(
                (node_start - offset, line, comment_begin)
            )

        for comment_info in reversed(preceding_comments):
            _write_if_unseen_comment(*comment_info)

        yield

        for offset, line in enumerate(lines[node_end:], 1):
            comment_begin = line.find("#")
            if comment_begin == -1 or comment_begin != node.col_offset:
                break

            _write_if_unseen_comment(
                line_no=node_end + offset,
                line=line,
                comment_begin=comment_begin,
            )

    def collect_comments(self, node: ast.AST) -> ContextManager[None]:
        if isinstance(node, ast.stmt):
            return self._collect_stmt_comments(node)
        else:
            return nullcontext()

    def retrieve_segment(self, node: ast.AST, segment: str) -> None:
        with self.collect_comments(node):
            if isinstance(node, ast.stmt):
                self.fill()
            self.write(segment)


UNPARSER_BACKENDS = {"fast": BaseUnparser, "precise": PreciseUnparser}
