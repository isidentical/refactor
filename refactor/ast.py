import ast
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class Node(Protocol):
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
