from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass, field
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
            return self_type.__name__.lower()


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
