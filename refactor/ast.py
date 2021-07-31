import ast
import io
import tokenize
from collections import UserList
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from typing import Any, List, Protocol


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


class UnparserBase(ast._Unparser):  # type: ignore
    # Normally ast._Unparser is a private API
    # though since it doesn't tend to change
    # often, we could simply have a base class
    # which will act like a wrapper for backwards
    # incompatible changes and let the refactor
    # users to override it.

    def __init__(self, source: str, *args: Any, **kwargs: Any) -> None:
        self.source = source
        super().__init__(*args, **kwargs)

    def unparse(self, node: ast.AST) -> str:
        return self.visit(node)

    @cached_property
    def tokens(self):
        buffer = io.StringIO(self.source)
        token_stream = tokenize.generate_tokens(buffer.readline)
        return tuple(token_stream)

    @cached_property
    def token_map(self):
        return {(*token.start, *token.end): token for token in self.tokens}

    @contextmanager
    def indented(self):
        self._indent += 1
        yield
        self._indent -= 1
