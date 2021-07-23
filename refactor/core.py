from __future__ import annotations

import ast
import copy
import tokenize
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, cast

from refactor.ast import PositinalNode, split_lines
from refactor.change import Change


@dataclass
class Action:
    node: ast.AST

    def apply(self, source: str) -> str:
        """Refactor a source segment in the given string."""
        lines = split_lines(source)
        view = slice(self.node.lineno - 1, self.node.end_lineno)

        target_lines = lines[view]
        start_prefix = target_lines[0][: self.node.col_offset]
        end_prefix = target_lines[-1][self.node.end_col_offset :]

        replacement = ast.unparse(self.build()).splitlines()
        replacement[0] = start_prefix + replacement[0]
        replacement[-1] += end_prefix

        lines[view] = replacement
        return "\n".join(lines)

    def build(self) -> ast.AST:
        return self.node

    def branch(self) -> ast.AST:
        return copy.deepcopy(self.node)


class Rule:
    def match(self, node: ast.AST) -> Optional[Action]:
        """Match the node against the current refactoring rule.

        On success, it will return an `Action` instance. On fail
        it might either raise an `AssertionError` or return `None`.
        """


@dataclass
class Session:
    """A refactoring session."""

    rules: List[Rule] = field(default_factory=list)

    def _run(self, source: str, *, _changed: bool = False) -> Tuple[str, bool]:
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if not isinstance(node, PositinalNode):
                continue

            for rule in self.rules:
                with suppress(AssertionError):
                    if action := rule.match(node):
                        return self._run(action.apply(source), _changed=True)

        return source, _changed

    def run(self, source: str) -> str:
        """Refactor the given string with the rules bound to
        this session."""

        source, _ = self._run(source)
        return source

    def run_file(self, file: Path) -> Optional[Change]:
        """Refactor the given file, and return a Change object
        containing the refactored version. If nothing changes, return
        None."""

        with tokenize.open(file) as stream:
            source = stream.read()

        new_source, is_changed = self._run(source)

        if is_changed:
            return Change(file, source, new_source)
        else:
            return None
