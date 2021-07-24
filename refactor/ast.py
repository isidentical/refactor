from typing import List, Protocol, runtime_checkable


@runtime_checkable
class PositionalNode(Protocol):
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int


def split_lines(source: str) -> List[str]:
    # TODO: https://github.com/python/cpython/blob/83d1430ee5b8008631e7f2a75447e740eed065c1/Lib/ast.py#L299-L321
    return source.splitlines()
