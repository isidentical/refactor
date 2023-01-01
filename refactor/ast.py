from __future__ import annotations

import ast
import io
import operator
import os
import re
import tokenize
from collections import UserList, UserString
from collections.abc import Generator, Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from functools import cached_property
from pprint import pprint
from typing import Any, ContextManager, Protocol, SupportsIndex, TypeVar, Union, cast, Tuple, Set, Dict, List, Callable

from refactor import common
from refactor.common import find_indent, extract_str_difference, find_indent_comments

DEFAULT_ENCODING = "utf-8"

AnyStringType = Union[str, "SourceSegment"]
StringType = TypeVar("StringType", bound=AnyStringType)


@dataclass
class Lines(UserList[StringType]):
    lines: list[StringType]

    def __post_init__(self) -> None:
        super().__init__(self.lines)
        self.lines = self.data
        self.best_matches: list[StringType] = []

    def join(self) -> str:
        """Return the combined source code."""
        return "".join(map(str, self.lines))

    @staticmethod
    def find_best_matching_source_line(line: str, source_lines: Lines, percentile: float = 10) -> Tuple[
        str | None, str, str]:
        """Finds the best matching line in a list of lines
        Returns the source line indentation and comments"""
        _line: str | None = None
        changes: List[Dict[str, Tuple[str, str, str] | Dict[str, str | float | Set[str]]]] = []
        for _l in source_lines.lines:
            _line: str = str(_l)
            # Estimate the changes between the two lines
            changes.append(extract_str_difference(_line, line, without_comments=True))
            indentation, _, comments = find_indent_comments(_line)
            changes[-1]['output'] = _line, indentation, "" if "#" in line else comments

        sort_key = lambda x: x['a']['percent'] + x['b']['percent']
        sorted_changes = sorted(changes, key=sort_key)
        for i, change in enumerate(sorted_changes):
            # There should be minimal changes to the original line - how to estimate that threshold?
            if change['a']['percent'] < percentile:
                return change['output']
        return None, "", ""

    def apply_source_formatting(
            self,
            source_lines: Lines,
            *,
            markers: Tuple[int, int, int | None] = None,
            comments_separator: str = " "
    ) -> None:
        """Apply the indentation from source_lines when the first several characters match

        :param source_lines: Original lines in source code
        :param markers: Indentation and prefix parameters. Tuple of (start line, col_offset, end_suffix | None)
        :param comments_separator: Separator for comments
        """

        block_indentation, start_prefix = find_indent(source_lines[markers[0]][:markers[1]])
        end_suffix = "" if markers[2] is None else source_lines[-1][markers[2]:]

        for index, line in enumerate(self.data):
            # Let's see if we find a matching original line using statistical change to original lines (default < 10%)
            (original_line,
             indentation,
             comments) = self.find_best_matching_source_line(line, source_lines[markers[0]:])

            print(f">{line[:-1]}<")
            if original_line is not None:
                # Remove the line indentation, collect comments
                _, line, new_comments = find_indent_comments(line)

                # Update for comments either on the 'line' or on the original line
                if new_comments and not new_comments.isspace():
                    # 'line' include comments, keep and implement 2 spaces separation
                    line = line + comments_separator + new_comments

                elif comments and not comments.isspace():
                    # Comments from original line may have end-of-line, using the 'line' terminator
                    comments = re.sub(self._newline_type, '', comments)
                    # If line has a return, insert the comments just before it
                    # Use 2 space separator as recommended by PyCharm (from PEP?)
                    if line and line[-1] == self._newline_type:
                        line = line[:-1] + comments_separator + comments + line[-1]
                    else:
                        line = line + comments_separator + comments

                self.data[index] = indentation + str(line)
            else:
                self.data[index] = block_indentation + str(line)

            if index == 0:
                self.data[index] = block_indentation + str(start_prefix) + str(line)

            if index == len(self.data) - 1:
                if original_line is None:
                    self.data[index] = self.data[index] + str(end_suffix)
                elif original_line[-1] == self._newline_type:
                    self.data[index] = self.data[index] + self._newline_type

    @cached_property
    def _newline_type(self) -> str:
        """Guess the used newline type."""
        return os.linesep if self.lines[-1].endswith(os.linesep) else "\n"


@dataclass
class SourceSegment(UserString):
    """Adapter for holding a line of source code that can be sliced
    with AST-native column offsets. Internally on every partitioning
    operation, the offsets will be assumed as UTF-8 encoded byte
    offsets (which is the default Refactor operates on)."""

    data: str
    encoding: str = DEFAULT_ENCODING

    def __getitem__(self, index: SupportsIndex | slice) -> SourceSegment:
        raw_line = self.encode(encoding=self.encoding)
        if isinstance(index, slice):
            view = raw_line[index].decode(encoding=self.encoding)
        else:
            # Using a direct index here (e.g. a[1]) would cause bytes to return an
            # integer (on some cases), but we want to deal with strings so this path
            # re-implements the direct indexing as slicing (e.g. a[1] is a[1:2], with
            # error handling).
            direct_index = operator.index(index)
            view = raw_line[direct_index: direct_index + 1].decode(
                encoding=self.encoding
            )
            if not view:
                raise IndexError("index out of range")

        return SourceSegment(view, encoding=self.encoding)


def split_lines(source: str, *, encoding: str | None = None) -> Lines:
    """Split the given source code into lines and
    return a list-like object (:py:class:`refactor.ast.Lines`)."""

    # TODO: https://github.com/python/cpython/blob/83d1430ee5b8008631e7f2a75447e740eed065c1/Lib/ast.py#L299-L321

    lines = source.splitlines(keepends=True)
    if encoding is not None:
        lines = [SourceSegment(line, encoding=encoding) for line in lines]  # type: ignore

    return Lines(lines)


class Unparser(Protocol):
    def __init__(self, source: str, *args: Any, **kwargs: Any) -> None:
        ...  # pragma: no cover

    def unparse(self, node: ast.AST) -> str:
        ...  # pragma: no cover


class BaseUnparser(ast._Unparser):  # type: ignore
    """A public :py:class:`ast._Unparser` API that can
    be used to customize the AST re-synthesis process."""

    source: str | None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.source = kwargs.pop("source", None)
        super().__init__(*args, **kwargs)

    def unparse(self, node: ast.AST) -> str:
        return self.visit(node)

    @cached_property
    def tokens(self) -> tuple[tokenize.TokenInfo, ...]:
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
        self._visited_comment_lines: set[int] = set()
        super().__init__(*args, **kwargs)

    def traverse(self, node: list[ast.AST] | ast.AST) -> None:
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

            preceding_comments.append((node_start - offset, line, comment_begin))

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
