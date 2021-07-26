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

from refactor.ast import Unparser, UnparserBase
from refactor.common import Singleton, is_contextful, pascal_to_snake


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
            return pascal_to_snake(self_type.__name__)


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


@dataclass(unsafe_hash=True)
class ScopeInfo(Singleton):
    node: ast.AST
    scope_type: ScopeType
    parent_scope: Optional[ScopeInfo] = None

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


class Scope(Representative):

    context_providers = (Ancestry,)

    def resolve(self, node: ast.AST) -> ScopeInfo:
        if isinstance(node, ast.Module):
            raise ValueError("Can't resolve Module")

        parents = tuple(
            filter(is_contextful, self.context["ancestry"].get_parents(node))
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
