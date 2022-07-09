from __future__ import annotations

import ast
import copy
import tokenize
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, FrozenSet, List, Optional, Tuple, Type, cast

from refactor.ast import split_lines
from refactor.change import Change
from refactor.common import find_indent, has_positions
from refactor.context import (
    Configuration,
    Context,
    Representative,
    resolve_dependencies,
)


@dataclass
class Action:
    """Base class for all actions.

    Override the `build()` method to programmatically build
    the replacement nodes.
    """

    node: ast.AST

    def apply(self, context: Context, source: str) -> str:
        """Refactor a source segment in the given string."""
        lines = split_lines(source)
        view = slice(self.node.lineno - 1, self.node.end_lineno)

        target_lines = lines[view]
        indentation, start_prefix = find_indent(
            target_lines[0][: self.node.col_offset]
        )
        end_prefix = target_lines[-1][self.node.end_col_offset :]

        replacement = split_lines(context.unparse(self.build()))
        replacement.apply_indentation(
            indentation, start_prefix=start_prefix, end_suffix=end_prefix
        )

        lines[view] = replacement
        return lines.join()

    def build(self) -> ast.AST:
        """Create the replacement node."""
        raise NotImplementedError

    def branch(self) -> ast.AST:
        """Return a copy view of the original node."""
        return copy.deepcopy(self.node)


@dataclass
class ReplacementAction(Action):
    """An action for replacing the `node` with
    the given `target` node."""

    node: ast.AST
    target: ast.AST

    def build(self) -> ast.AST:
        return self.target


class NewStatementAction(Action):
    """An action base for adding a new statement right after
    the given `node`."""

    def apply(self, context: Context, source: str) -> str:
        lines = split_lines(source)

        start_line = lines[self.node.lineno - 1]
        indentation, start_prefix = find_indent(
            start_line[: self.node.col_offset]
        )

        replacement = split_lines(context.unparse(self.build()))
        replacement.apply_indentation(indentation, start_prefix=start_prefix)

        end_line = cast(int, self.node.end_lineno)
        for line in reversed(replacement):
            lines.insert(end_line, line)

        return lines.join()


class TargetedNewStatementAction(ReplacementAction, NewStatementAction):
    """An action for appending the given `target` node
    right after the `node`."""


@dataclass
class Rule:
    context_providers: ClassVar[Tuple[Type[Representative], ...]] = ()

    context: Context

    def check_file(self, path: Optional[Path]) -> bool:
        """Check whether to process this file or not. If returned
        a false value, the rule will be deactivated for this file."""
        return True

    def match(self, node: ast.AST) -> Optional[Action]:
        """Match the node against the current refactoring rule.

        On success, it will return an `Action` instance. On fail
        it might either raise an `AssertionError` or return `None`.
        """
        raise NotImplementedError


@dataclass
class Session:
    """A refactoring session."""

    rules: List[Type[Rule]] = field(default_factory=list)
    config: Configuration = field(default_factory=Configuration)

    def _initialize_rules(
        self, tree: ast.Module, source: str, file: Optional[Path]
    ) -> List[Rule]:
        context = Context.from_dependencies(
            resolve_dependencies(self.rules),
            tree=tree,
            source=source,
            file=file,
            config=self.config,
        )
        return [
            instance
            for rule in self.rules
            if (instance := rule(context)).check_file(file)
        ]

    def _run(
        self,
        source: str,
        file: Optional[Path] = None,
        *,
        _changed: bool = False,
        _known_sources: FrozenSet[str] = frozenset(),
    ) -> Tuple[str, bool]:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            if _changed is False:
                return source, _changed
            else:
                raise ValueError("Generated source is unparsable") from exc

        _known_sources |= {source}
        rules = self._initialize_rules(tree, source, file)

        for node in ast.walk(tree):
            if not has_positions(type(node)):  # type: ignore
                continue

            for rule in rules:
                with suppress(AssertionError):
                    if action := rule.match(node):
                        new_source = action.apply(rule.context, source)
                        if new_source not in _known_sources:
                            return self._run(
                                new_source,
                                _changed=True,
                                _known_sources=_known_sources,
                            )

        return source, _changed

    def run(self, source: str, *, file: Optional[Path] = None) -> str:
        """Refactor the given string with the rules bound to
        this session."""

        source, _ = self._run(source)
        return source

    def run_file(self, file: Path) -> Optional[Change]:
        """Refactor the given file, and return a Change object
        containing the refactored version. If nothing changes, return
        None."""

        try:
            with tokenize.open(file) as stream:
                source = stream.read()
        except (SyntaxError, UnicodeDecodeError):
            return None

        new_source, is_changed = self._run(source, file=file)

        if is_changed:
            return Change(file, source, new_source)
        else:
            return None
