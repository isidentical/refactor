import ast
import io
import tokenize
from contextlib import contextmanager
from functools import cached_property
from typing import Any, List, Protocol


def split_lines(source: str) -> List[str]:
    # TODO: https://github.com/python/cpython/blob/83d1430ee5b8008631e7f2a75447e740eed065c1/Lib/ast.py#L299-L321
    return source.splitlines()


class Unparser(Protocol):
    def __init__(self, source: str, *args: Any, **kwargs: Any) -> None:
        ...

    def unparse(self, node: ast.AST) -> str:
        ...


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
