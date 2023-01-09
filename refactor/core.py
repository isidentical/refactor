from __future__ import annotations

import ast
import tempfile
import tokenize
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass, field, astuple
from pathlib import Path
from typing import ClassVar, NoReturn, Tuple, Generator, Type, List

# TODO: remove the deprecated aliases on 1.0.0
from refactor.actions import (  # unimport:skip
    Action,
    BaseAction,
    NewStatementAction,
    ReplacementAction,
    TargetedNewStatementAction,
)
from refactor.change import Change
from refactor.common import _FileInfo, has_positions
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
    context_providers: ClassVar[tuple[type[Representative], ...]] = ()

    context: Context

    def check_file(self, path: Path | None) -> bool:
        """Check whether to process the given ``path``. If ``path`` is `None`,
        that means the user has submitted a string to be processed.

        By default it will always be `True` but can be overridden
        in subclasses.
        """
        return True

    def match(
            self,
            node: ast.AST,
    ) -> BaseAction | None | Iterator[BaseAction]:
        """Match the given ``node`` against current rule's scope.

        On success, it will return a source code transformation action
        (an instance of :class:`refactor.actions.BaseAction`). On failure
        it might either raise an `AssertionError` or return `None`.
        """
        raise NotImplementedError


class _IterableRuleCollection(type):
    def __iter__(cls):
        return iter(cls.rules)


class _RuleCollectionIterator:
    """This is a hack to make the RuleCollection work as a Rule (Copilot says it as it is :'("""

    def __init__(self, rules: List[Type[Rule]]) -> None:
        self.rules = rules
        self.index = 0

    def __next__(self) -> Type[Rule]:
        if self.index >= len(self.rules):
            raise StopIteration

        rule = self.rules[self.index]
        self.index += 1
        return rule


@dataclass
class RuleCollection(metaclass=_IterableRuleCollection):
    """Collects a set of Rule to be used as a standalone Rule in the Session's Rules"""
    # This is unused but needed for the context iterator
    context_providers: ClassVar[tuple[type[Representative], ...]] = ()

    # A rules attribute (same type as for Session) must be defined in the class
    # not sure whether to initialize it as empty here, would it overwrite the user-defined
    # at instantiation?
    # rules: List[Type[Rule]] = field(default_factory=list)

    rule_instances: list[Rule] = field(default_factory=list)

    def __iter__(self) -> _RuleCollectionIterator:
        return _RuleCollectionIterator(getattr(self, "rules"))
        return iter(getattr(self, "rules"))

    def initialize_rules(
            self,
            context: Context,
            path: Path | None,
    ):
        """Initialize all rules in the collection. Intended to be called by the Session"""
        self.rule_instances = [i for rule in self.rules if (i := rule(context)).check_file(path)]

    def check_file(self, path: Path | None) -> bool:
        """This should always be True. It is needed as we want to seamlessly iterate as if it was a Rule"""
        return True

    def match(
            self,
            node: ast.AST,
    ) -> Generator[Tuple[Rule, BaseAction | None | Iterator[BaseAction]]]:
        """Match the given ``node`` against all the rules in the collection.

        It yields tuples of all the Rule, BaseAction that match.
        """
        for rule in self.rule_instances:
            match = rule.match(node)
            if isinstance(match, BaseAction):
                yield rule, match
            elif isinstance(match, Iterator):
                yield rule, next(match)
        return


@dataclass
class Session:
    """A refactoring session that consists of a set of rules and a configuration."""

    rules: list[type[Rule] | RuleCollection] = field(default_factory=list)
    config: Configuration = field(default_factory=Configuration)

    def _initialize_rules(
            self,
            tree: ast.Module,
            source: str,
            file_info: _FileInfo,
    ) -> list[Rule]:
        context = Context._from_dependencies(
            _resolve_dependencies(self.rules),
            tree=tree,
            source=source,
            file_info=file_info,
            config=self.config,
        )
        instances: list[Rule | RuleCollection] = []
        for rule_or_collection in self.rules:
            if issubclass(rule_or_collection, RuleCollection):
                # We want to initialize the rules, but keep the rules grouped for intermediate tree update
                (collection := rule_or_collection()).initialize_rules(context, file_info.path)
                if collection.rule_instances and len(collection.rule_instances) > 0:
                    instances.append(collection)
            else:
                instances.append(rule_or_collection(context))
        return [i for i in instances if i.check_file(file_info.path)]

    def _apply_single(
            self,
            context: Context,
            source_code: str,
            action: BaseAction,
            enable_optimizations: bool = True,
    ) -> str:
        if enable_optimizations:
            action = optimize(action, context)
        return action.apply(context, source_code)

    def _apply_multiple(
            self,
            rule: Rule,
            source_code: str,
            actions: Iterator[BaseAction],
    ) -> str:
        # Compute the path of the current node (against the starting tree).
        #
        # Adjust this path with the knowledge from the previously applied
        # actions.
        #
        # Use the path to find the correct node in the new tree.

        from refactor.internal.graph_access import AccessFailure, GraphPath

        shifts: list[tuple[GraphPath, int]] = []
        previous_tree = rule.context.tree
        for action in actions:
            input_node, stack_effect = action._stack_effect()

            # We compute each path against the initial revision of the tree
            # since the rule who is producing them doesn't have access to the
            # temporary trees we generate on the fly.
            path = GraphPath.backtrack_from(rule.context, input_node)

            # And due to this, some actions might have altered the tree in a
            # way that makes the path as is invalid. For ensuring that the path
            # now reflects the current state of the tree, we apply all the shifts
            # that the previous actions have caused.
            path = path.shift(shifts)

            # With the updated path, we can now find the same node in the new
            # tree. This allows us to know the exact position of the node.
            try:
                updated_input = path.execute(previous_tree)
            except AccessFailure:
                raise MaybeOverlappingActions(
                    "When using chained actions, individual actions should not"
                    " overlap with each other."
                    f"\n   Action attempted: {action} for node: {ast.unparse(action.node)}"
                    f"\n               Path: {path}"
                ) from None
            else:
                shifts.append((path, stack_effect))

            updated_action = action._replace_input(updated_input)
            updated_context = rule.context.replace(
                source=source_code, tree=previous_tree
            )

            # TODO: re-enable optimizations if it is viable to run
            # them on the new tree/source code.
            source_code = self._apply_single(
                updated_context,
                source_code,
                updated_action,
                enable_optimizations=False,
            )
            try:
                previous_tree = ast.parse(source_code)
            except SyntaxError as exc:
                return self._unparsable_source_code(source_code, exc)
        return source_code

    def _run_collection(
            self,
            node,
            source: str,
            collection: RuleCollection,
    ) -> str:
        """Run the given collection of rules against the given node"""
        with suppress(AssertionError):
            for rule, match in collection.match(node):
                if match is None:
                    continue
                if isinstance(match, BaseAction):
                    new_source = self._apply_single(rule.context, source, match)
                elif isinstance(match, Iterator):
                    new_source = self._apply_multiple(rule, source, match)
                else:
                    raise TypeError(
                        f"Unexpected action type: {type(match).__name__}"
                    )
                return new_source
        return source

    def _run(
            self,
            source: str,
            file_info: _FileInfo,
            *,
            _changed: bool = False,
            _known_sources: frozenset[str] = frozenset(),
    ) -> tuple[str, bool]:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            if not _changed:
                return source, _changed
            else:
                return self._unparsable_source_code(source, exc)

        _known_sources |= {source}
        rules = self._initialize_rules(tree, source, file_info)

        for node in ast.walk(tree):
            if not has_positions(type(node)):  # type: ignore
                continue

            for rule in rules:
                with suppress(AssertionError):
                    if isinstance(rule, RuleCollection):
                        new_source = self._run_collection(
                            node,
                            source,
                            rule,
                        )
                    else:
                        match = rule.match(node)
                        if match is None:
                            continue
                        elif isinstance(match, BaseAction):
                            new_source = self._apply_single(rule.context, source, match)
                        elif isinstance(match, Iterator):
                            new_source = self._apply_multiple(rule, source, match)
                        else:
                            raise TypeError(
                                f"Unexpected action type: {type(match).__name__}"
                            )

                    if new_source not in _known_sources:
                        return self._run(
                            new_source,
                            file_info,
                            _changed=True,
                            _known_sources=_known_sources,
                        )

        return source, _changed

    def _unparsable_source_code(self, source: str, exc: SyntaxError) -> NoReturn:
        error_message = "Generated source is unparsable."

        if self.config.debug_mode:
            fd, file_name = tempfile.mkstemp(prefix="refactor", text=True)
            with open(fd, "w") as stream:
                stream.write(source)
            error_message += f"\nSee {file_name} for the generated source."

        raise ValueError(error_message) from exc

    def run(self, source: str) -> str:
        """Apply all the rules from this session to the given ``source``
        and return the transformed version.

        In case of the given `source` is not parsable, it will return
        it unchanged.
        """

        source, _ = self._run(source, file_info=_FileInfo())
        return source

    def run_file(self, file: Path) -> Change | None:
        """Apply all the rules from this session to the given ``file``
        and return a :class:`refactor.Change` if any changes were made.

        In case of the given file is not parsable, it will return `None`.
        """

        try:
            with tokenize.open(file) as stream:
                source = stream.read()
                encoding = stream.encoding
        except (SyntaxError, UnicodeDecodeError):
            return None

        file_info = _FileInfo(file, encoding)
        new_source, is_changed = self._run(source, file_info)

        if is_changed:
            return Change(file_info, source, new_source)
