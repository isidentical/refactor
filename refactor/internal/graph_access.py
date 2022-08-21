from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Iterator, List, Type

from refactor.context import Context


class AccessFailure(Exception):
    pass


@dataclass
class Access:
    expected_type: Type[ast.AST]

    def _check(self, condition: bool) -> None:
        if not condition:
            raise AccessFailure

    def execute(self, node: ast.AST) -> ast.AST:
        raise NotImplementedError


@dataclass
class FieldAccess(Access):
    field: str

    def execute(self, node: ast.AST) -> ast.AST:
        accessed_node = getattr(node, self.field)
        self._check(type(accessed_node) is self.expected_type)
        return accessed_node


@dataclass
class IndexAccess(FieldAccess):
    index: int

    def execute(self, node: ast.AST) -> ast.AST:
        accessed_field = getattr(node, self.field)
        self._check(isinstance(accessed_field, list))
        self._check(len(accessed_field) > self.index)
        accessed_node = accessed_field[self.index]
        self._check(type(accessed_node) is self.expected_type)
        return accessed_node


def _backtrack_node(context: Context, node: ast.AST) -> Iterator[Access]:
    cursor = node
    for ancestor_field, ancestor in context.ancestry.traverse(node):
        ancestor_field_value = getattr(ancestor, ancestor_field)
        if isinstance(ancestor_field_value, list):
            yield IndexAccess(
                type(cursor),
                ancestor_field,
                ancestor_field_value.index(cursor),
            )
        elif isinstance(ancestor_field_value, ast.AST):
            yield FieldAccess(type(cursor), ancestor_field)
        else:
            raise TypeError(
                "Unexpeced ancestor field type:"
                f" {type(ancestor_field_value).__name__}"
            )

        cursor = ancestor


@dataclass
class AccessManager:
    accesses: List[Access]

    @classmethod
    def backtrack_from(cls, context: Context, node: ast.AST) -> AccessManager:
        accesses = list(_backtrack_node(context, node))
        accesses.reverse()
        return cls(accesses)

    def execute_on(self, node: ast.AST) -> ast.AST:
        for access in self.accesses:
            node = access.execute(node)
        return node
