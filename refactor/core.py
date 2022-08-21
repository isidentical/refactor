from __future__ import annotations

import ast
import tempfile
import tokenize
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    ClassVar,
    FrozenSet,
    Iterator,
    List,
    NoReturn,
    Optional,
    Tuple,
    Type,
)

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
    _resolve_dependencies,
)
from refactor.internal.action_optimizer import optimize


class MaybeOverlappingActions(Exception):
    pass


@dataclass
class Rule:
    context_providers: ClassVar[Tuple[Type[Representative], ...]] = ()

    context: Context

    def check_file(self, path: Optional[Path]) -> bool:
        """Check whether to process the given ``path``.

        By default it will always be `True` but can be overridden
        in subclasses.
        """
        return True

    def match(self, node: ast.AST) -> Optional[BaseAction]:
        """Match the given ``node`` against current rule's scope.

        On success, it will return a source code transformation action
        (an instance of :class:`refactor.actions.BaseAction`). On failure
        it might either raise an `AssertionError` or return `None`.
        """
        raise NotImplementedError


@dataclass
class Session:
    """A refactoring session that consists of a set of rules and a configuration.
    """

    rules: List[Type[Rule]] = field(default_factory=list)
    config: Configuration = field(default_factory=Configuration)

    def _initialize_rules(
        self, tree: ast.Module, source: str, file: Optional[Path]
    ) -> List[Rule]:
        context = Context._from_dependencies(
            _resolve_dependencies(self.rules),
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

    def _apply_single(
        self,
        rule: Rule,
        source_code: str,
        action: BaseAction,
        enable_optimizations: bool = True,
    ) -> str:
        if enable_optimizations:
            action = optimize(action, rule.context)
        return action.apply(rule.context, source_code)

    def _apply_multiple(
        self,
        rule: Rule,
        source_code: str,
        actions: Iterator[BaseAction],
    ) -> str:
        from refactor.actions import Replace
        from refactor.internal.graph_access import (
            AccessFailure,
            access,
            compute_accesses,
        )

        previous_tree = rule.context.tree
        for action in actions:
            if not isinstance(action, Replace):
                raise NotImplementedError(
                    "Chained actions are only implemented for `Replace`"
                    " action."
                )

            accesses = compute_accesses(rule.context, action.node)
            try:
                action.node = access(previous_tree, accesses)
            except AccessFailure:
                raise MaybeOverlappingActions(
                    "When using chained actions, individual actions should not"
                    " overlap with each other."
                ) from None

            # TODO: re-enable optimizations if it is viable to run
            # them on the new tree/source code.
            source_code = self._apply_single(
                rule, source_code, action, enable_optimizations=False
            )
            try:
                previous_tree = ast.parse(source_code)
            except SyntaxError as exc:
                return self._unparsable_source_code(source_code, exc)
        return source_code

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
            if not _changed:
                return source, _changed
            else:
                return self._unparsable_source_code(source, exc)

        _known_sources |= {source}
        rules = self._initialize_rules(tree, source, file)

        for node in ast.walk(tree):
            if not has_positions(type(node)):  # type: ignore
                continue

            for rule in rules:
                with suppress(AssertionError):
                    match = rule.match(node)
                    if match is None:
                        continue
                    elif isinstance(match, BaseAction):
                        new_source = self._apply_single(rule, source, match)
                    elif isinstance(match, Iterator):
                        new_source = self._apply_multiple(rule, source, match)
                    else:
                        raise TypeError(
                            f"Unexpected action type: {type(match).__name__}"
                        )

                    if new_source not in _known_sources:
                        return self._run(
                            new_source,
                            _changed=True,
                            file=file,
                            _known_sources=_known_sources,
                        )

        return source, _changed

    def _unparsable_source_code(
        self, source: str, exc: SyntaxError
    ) -> NoReturn:
        error_message = "Generated source is unparsable."

        if self.config.debug_mode:
            fd, file_name = tempfile.mkstemp(prefix="refactor", text=True)
            with open(fd, "w") as stream:
                stream.write(source)
            error_message += f"\nSee {file_name} for the generated source."

        raise ValueError(error_message) from exc

    def run(self, source: str, *, file: Optional[Path] = None) -> str:
        """Apply all the rules from this session to the given ``source``
        and return the transformed version.

        In case of the given `source` is not parsable, it will return
        it unchanged.
        """

        source, _ = self._run(source)
        return source

    def run_file(self, file: Path) -> Optional[Change]:
        """Apply all the rules from this session to the given ``file``
        and return a :class:`refactor.Change` if any changes were made.

        In case of the given file is not parsable, it will return `None`.
        """

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
