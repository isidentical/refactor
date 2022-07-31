from __future__ import annotations

import ast
import tempfile
import tokenize
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, FrozenSet, List, Optional, Tuple, Type

# TODO: remove the deprecated aliases on 1.0.0
from refactor.actions import (  # unimport:skip
    Action,
    BaseAction,
    NewStatementAction,
    ReplacementAction,
    TargetedNewStatementAction,
)
from refactor.change import Change
from refactor.common import has_positions
from refactor.context import (
    Configuration,
    Context,
    Representative,
    resolve_dependencies,
)


@dataclass
class Rule:
    context_providers: ClassVar[Tuple[Type[Representative], ...]] = ()

    context: Context

    def check_file(self, path: Optional[Path]) -> bool:
        """Check whether to process this file or not. If returned
        a false value, the rule will be deactivated for this file."""
        return True

    def match(self, node: ast.AST) -> Optional[BaseAction]:
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
            return self._delegate_syntax_errors(source, _changed, exc)

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
                                file=file,
                                _known_sources=_known_sources,
                            )

        return source, _changed

    def _delegate_syntax_errors(
        self, source: str, changed: bool, exc: SyntaxError
    ) -> Tuple[str, bool]:
        if not changed:
            return source, changed

        error_message = "Generated source is unparsable."

        if self.config.debug_mode:
            fd, file_name = tempfile.mkstemp(prefix="refactor", text=True)
            with open(fd, "w") as stream:
                stream.write(source)
            error_message += f"\nSee {file_name} for the generated source."

        raise ValueError(error_message) from exc

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
