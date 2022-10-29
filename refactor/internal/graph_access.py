from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace
from typing import Any, Generic, TypeVar, Union

from refactor import common
from refactor.context import Context

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class AccessFailure(Exception):
    pass


@dataclass
class Access(Generic[InputType, OutputType]):
    """Represents a generic access on a node's field."""

    expected_type: type[Any]

    def __repr__(self) -> str:
        raise NotImplementedError

    def _check(self, condition: bool) -> None:
        if not condition:
            raise AccessFailure

    def execute(self, input: InputType) -> OutputType:
        raise NotImplementedError

    replace = replace


@dataclass
class FieldAccess(Access[ast.AST, Union[ast.AST, list[ast.AST]]]):
    """A single-node field access."""

    field: str

    def __repr__(self):
        return f".{self.field}"

    def execute(self, input: ast.AST) -> ast.AST | list[ast.AST]:
        accessed_node = getattr(input, self.field)
        self._check(type(accessed_node) is self.expected_type)
        return accessed_node


@dataclass
class IndexAccess(Access[list[ast.AST], ast.AST]):
    """Access to a sequence of nodes by an index."""

    index: int

    def __repr__(self):
        return f"[{self.index}]"

    def execute(self, input: list[ast.AST]) -> ast.AST:
        self._check(isinstance(input, list))
        self._check(len(input) > self.index)
        accessed_node = input[self.index]
        self._check(type(accessed_node) is self.expected_type)
        return accessed_node


@dataclass
class GraphPath:
    parts: list[Access] = field(default_factory=list)

    @classmethod
    def backtrack_from(cls, context: Context, node: ast.AST) -> GraphPath:
        """Calculate a path back to the node from the start of the tree. For example
        in the tree below:

        def foo():
            if name == "foo":
                call()
                return 1

        the path for the '1' would be: .body[0].body[1].value
        """

        parts: list[Access] = []
        cursor = node
        for ancestor_field, ancestor in context.ancestry.traverse(node):
            ancestor_field_value = getattr(ancestor, ancestor_field)
            if isinstance(ancestor_field_value, list):
                parts.append(
                    IndexAccess(type(cursor), ancestor_field_value.index(cursor))
                )
                parts.append(FieldAccess(list, ancestor_field))
            elif isinstance(ancestor_field_value, ast.AST):
                parts.append(FieldAccess(type(cursor), ancestor_field))
            else:
                raise TypeError(
                    "Unexpeced ancestor field type:"
                    f" {type(ancestor_field_value).__name__}"
                )

            cursor = ancestor

        parts.reverse()
        return GraphPath(parts)

    @common._allow_asserts
    def shift(self, shifts: list[tuple[GraphPath, int]]) -> GraphPath:
        """Apply the offsets from the preceding operations on this path. The offsets
        must be shifted as well.

        For example, if we have the following list of shifts:
            - (.body[2], 1)
            - (.body[5].body[3], 1)
            - (.body[5].orelse[2], -1)
            - (.body[6], -1)

        Applying them to .body[4].orelse[4] would result in:
            - .body[5].orelse[4] (increased .body index by 1)
            - .body[5].orelse[4] (-- pass --)
            - .body[5].orelse[3] (decreased .orelse index by 1)
            - .body[5].orelse[3] (-- pass --)
        """
        parts = self.parts.copy()
        for shift, shift_offset in shifts:
            *shift_parent, shifter = shift.parts
            *common_parts, target_access = parts[: len(shift.parts)]

            # This change does not affect us at all.
            if shift_parent != common_parts or not shift_offset:
                continue

            assert isinstance(shifter, IndexAccess)
            assert isinstance(target_access, IndexAccess)

            # This change might affect the future nodes in this path
            # but not us.
            if shifter.index >= target_access.index:
                continue

            parts[parts.index(target_access)] = target_access.replace(
                index=target_access.index + shift_offset
            )

        return GraphPath(parts)

    def execute(self, node: ast.AST) -> ast.AST:
        """Retrieve the node staying the current path from the given tree."""

        cursor = node
        for access in self.parts:
            cursor = access.execute(cursor)
        return cursor

    def __repr__(self):
        return "".join(map(repr, self.parts))
