from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List, Optional, cast

from refactor.ast import Node


@dataclass
class Action:
    node: Node

    def apply(self, source: str) -> str:
        """Refactor a source segment in the given string."""
        lines = source.splitlines()
        view = slice(self.node.lineno - 1, self.node.end_lineno)

        target_lines = lines[view]
        start_prefix = target_lines[0][: self.node.col_offset]
        end_prefix = target_lines[-1][self.node.end_col_offset :]

        replacement_node = cast(ast.AST, self.build())
        replacement = ast.unparse(replacement_node).splitlines()
        replacement[0] = start_prefix + replacement[0]
        replacement[-1] += end_prefix

        lines[view] = replacement
        return "\n".join(lines)

    def build(self) -> Node:
        return self.node


class Unit:
    def match(self, node: Node) -> Optional[Action]:
        """Match the node against the current refactoring rule.

        On success, it will return an `Action` instance. On fail
        it might either raise an `AssertionError` or return `None`.
        """


@dataclass
class Session:
    """A refactoring session."""

    rules: List[Unit] = field(default_factory=list)

    def run(self, source: str) -> str:
        """Refactor the given string with the rules bound to
        this session."""

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if not isinstance(node, Node):
                continue

            for rule in self.rules:
                if action := rule.match(node):
                    return self.run(action.apply(source))

        return source
