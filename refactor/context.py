from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cached_property
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    cast,
)

import refactor.common as common
from refactor.ast import Unparser, UnparserBase


class Dependable(Protocol):
    context_providers: ClassVar[Tuple[Type[Representative], ...]]


def resolve_dependencies(
    dependables: Iterable[Type[Dependable]],
) -> Set[Type[Representative]]:
    dependencies: Set[Type[Representative]] = set()

    pool = deque(dependables)
    while pool:
        dependable = pool.pop()
        pool.extendleft(dependable.context_providers)

        if issubclass(dependable, Representative):
            dependencies.add(cast(Type[Representative], dependable))

    return dependencies


@dataclass
class Context:
    source: str
    tree: ast.AST
    metadata: Dict[str, Representative] = field(default_factory=dict)

    def unparse(self, node: ast.AST) -> str:
        if rep := self.metadata.get("unparse"):
            unparser = rep.unparse
        else:
            unparser = ast.unparse

        return unparser(node)

    def __getitem__(self, key: str) -> Representative:
        if key not in self.metadata:
            raise ValueError(
                f"{key!r} provider is not available on this context "
                "since none of the rules from this session specified it "
                "in it's 'context_providers' tuple."
            )
        return self.metadata[key]

    @classmethod
    def from_dependencies(
        cls, dependencies: Iterable[Type[Representative]], **kwargs: Any
    ) -> Context:
        context = cls(**kwargs)
        representatives = [dependency(context) for dependency in dependencies]
        context.metadata.update(
            {
                representative.name: representative
                for representative in representatives
            }
        )
        return context


@dataclass
class Representative:
    context_providers: ClassVar[Tuple[Type[Representative], ...]] = ()

    context: Context

    @cached_property
    def name(self) -> str:
        self_type = type(self)
        if self_type is Representative:
            return "<base>"
        else:
            return common.pascal_to_snake(self_type.__name__)


class Ancestry(Representative):
    def marked(self, node: ast.AST) -> bool:
        return hasattr(node, "parent")

    def annotate(self, node: ast.AST) -> None:
        if self.marked(node):
            return None

        node.parent = None
        for parent in ast.walk(node):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent

    def ensure_annotated(self) -> None:
        self.annotate(self.context.tree)

    def get_parent(self, node: ast.AST) -> Optional[ast.AST]:
        self.ensure_annotated()

        return node.parent

    def get_parents(self, node: ast.AST) -> Iterable[ast.AST]:
        self.ensure_annotated()

        parent = node
        while parent := parent.parent:
            yield parent


class ScopeType(Enum):
    GLOBAL = auto()
    CLASS = auto()
    FUNCTION = auto()
    COMPREHENSION = auto()


@dataclass(unsafe_hash=True)
class ScopeInfo(common.Singleton):
    node: ast.AST
    scope_type: ScopeType
    parent_scope: Optional[ScopeInfo] = field(default=None, repr=False)

    def can_reach(self, other: ScopeInfo) -> bool:
        if other.scope_type is ScopeType.GLOBAL:
            return True
        elif self is other:
            return True

        cursor = self
        while cursor := cursor.parent_scope:  # type: ignore
            if cursor is other:
                if other.scope_type is ScopeType.FUNCTION:
                    return True
        else:
            return False

    @cached_property
    def definitions(self):
        local_definitions = {}
        for node in common.walk_scope(self.node):
            if isinstance(node, ast.Assign):
                # a, b = c = 1
                for target in node.targets:
                    for identifier in common.unpack_lhs(target):
                        local_definitions[identifier] = node
            elif isinstance(node, ast.NamedExpr):
                # (a := b)
                local_definitions[node.target.id] == node
            elif isinstance(node, ast.excepthandler):
                # except Something as err: ...
                if node.name is not None:
                    local_definitions[node.name] = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                # import something
                for alias in node.names:
                    local_definitions[alias.name] = node
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                # with x as (y, z): ...
                for item in node.items:
                    if item.optional_vars:
                        for identifier in common.unpack_lhs(item):
                            local_definitions[identifier] = node
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                # for a, b in c: ...
                for identifier in common.unpack_lhs(node.target):
                    local_definitions[identifier] = node
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                # def something(): ...
                local_definitions[node.name] = node

        if isinstance(node, ast.arg):
            local_definitions[node.arg] = node

        return local_definitions


class Scope(Representative):

    context_providers = (Ancestry,)

    def resolve(self, node: ast.AST) -> ScopeInfo:
        if isinstance(node, ast.Module):
            raise ValueError("Can't resolve Module")

        parents = tuple(
            filter(
                common.is_contextful,
                self.context["ancestry"].get_parents(node),
            )
        )

        scope = None
        for parent in reversed(parents):
            if isinstance(parent, ast.Module):
                scope_type = ScopeType.GLOBAL
            elif isinstance(parent, ast.ClassDef):
                scope_type = ScopeType.CLASS
            elif isinstance(
                parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            ):
                scope_type = ScopeType.FUNCTION
            elif common.is_comprehension(parent):
                scope_type = ScopeType.COMPREHENSION

            scope = ScopeInfo(parent, scope_type, scope)

        assert scope is not None
        return scope


class CustomUnparser(Representative):

    unparser: ClassVar[Type[Unparser]] = UnparserBase

    @property
    def name(self):
        return "unparse"

    def unparse(self, node: ast.AST) -> str:
        unparser = self.unparser(source=self.context.source)
        return unparser.unparse(node)
