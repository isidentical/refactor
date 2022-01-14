from __future__ import annotations

import ast
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cached_property
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    DefaultDict,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

import refactor.common as common
from refactor.ast import UNPARSER_BACKENDS, BaseUnparser


@dataclass
class Configuration:
    """Configuration settings for refactor.

    unparser: precise, fast, or a `BaseUnparser` subclass.
    """

    unparser: Union[str, Type[BaseUnparser]] = "precise"


class Dependable(Protocol):
    context_providers: ClassVar[Tuple[Type[Representative], ...]]


def resolve_dependencies(
    dependables: Iterable[Type[Dependable]],
) -> Set[Type[Representative]]:
    dependencies: Set[Type[Representative]] = set()

    pool = deque(dependables)
    while pool:
        dependable = pool.pop()
        pool.extendleft(
            dependency
            for dependency in dependable.context_providers
            if dependency not in dependencies
        )

        if issubclass(dependable, Representative):
            dependencies.add(cast(Type[Representative], dependable))

    return dependencies


@dataclass
class Context:
    source: str
    tree: ast.AST

    file: Optional[Path] = None
    config: Configuration = field(default_factory=Configuration)
    metadata: Dict[str, Representative] = field(default_factory=dict)

    def unparse(self, node: ast.AST) -> str:
        unparser_backend = self.config.unparser
        if isinstance(unparser_backend, str):
            if unparser_backend not in UNPARSER_BACKENDS:
                raise ValueError(
                    "'unparser_backend' must be one of "
                    f"these: {', '.join(UNPARSER_BACKENDS)}"
                )
            backend_cls = UNPARSER_BACKENDS[unparser_backend]
        elif isinstance(unparser_backend, type):
            if not issubclass(unparser_backend, BaseUnparser):
                raise ValueError(
                    "'unparser_backend' must inherit from 'BaseUnparser'"
                )
            backend_cls = unparser_backend
        else:
            raise ValueError(
                "'unparser_backend' must be either a string or a type"
            )

        unparser = backend_cls(source=self.source)
        return unparser.unparse(node)  # type: ignore

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

    def mark(self, parent: ast.AST, field: str, node: Any) -> None:
        if isinstance(node, ast.AST):
            node.parent = parent
            node.parent_field = field

    def annotate(self, node: ast.AST) -> None:
        if self.marked(node):
            return None

        node.parent = None
        node.parent_field = None
        for parent in ast.walk(node):
            for field, value in ast.iter_fields(parent):
                if isinstance(value, list):
                    for item in value:
                        self.mark(parent, field, item)
                else:
                    self.mark(parent, field, value)

    def ensure_annotated(self) -> None:
        self.annotate(self.context.tree)

    def infer(self, node: ast.AST) -> Tuple[str, ast.AST]:
        self.ensure_annotated()
        return (node.parent_field, node.parent)

    def traverse(self, node: ast.AST) -> Iterable[Tuple[str, ast.AST]]:
        cursor = node
        while True:
            field, parent = self.infer(cursor)
            if parent is None:
                break

            yield field, parent
            cursor = parent

    def get_parent(self, node: ast.AST) -> Optional[ast.AST]:
        _, parent = self.infer(node)
        return parent

    def get_parents(self, node: ast.AST) -> Iterable[ast.AST]:
        for _, parent in self.traverse(node):
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
    parent: Optional[ScopeInfo] = field(default=None, repr=False)

    def can_reach(self, other: ScopeInfo) -> bool:
        if other.scope_type is ScopeType.GLOBAL:
            return True
        elif self is other:
            return True

        cursor = self
        while cursor := cursor.parent:  # type: ignore
            if cursor is other:
                if other.scope_type is ScopeType.FUNCTION:
                    return True
        else:
            return False

    def defines(self, name: str) -> bool:
        return name in self.definitions

    @cached_property
    def definitions(self) -> Dict[str, List[ast.AST]]:
        local_definitions: DefaultDict[str, List[ast.AST]] = defaultdict(list)
        for node in common.walk_scope(self.node):
            if isinstance(node, ast.Assign):
                # a, b = c = 1
                for target in node.targets:
                    for identifier in common.unpack_lhs(target):
                        local_definitions[identifier].append(node)
            elif isinstance(node, ast.NamedExpr):
                # (a := b)
                local_definitions[node.target.id].append(node)
            elif isinstance(node, ast.excepthandler):
                # except Something as err: ...
                if node.name is not None:
                    local_definitions[node.name].append(node)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                # import something
                for alias in node.names:
                    local_definitions[alias.name].append(node)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                # with x as (y, z): ...
                for item in node.items:
                    if item.optional_vars:
                        for identifier in common.unpack_lhs(
                            item.optional_vars
                        ):
                            local_definitions[identifier].append(node)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                # for a, b in c: ...
                for identifier in common.unpack_lhs(node.target):
                    local_definitions[identifier].append(node)
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                # def something(): ...
                local_definitions[node.name].append(node)
            elif isinstance(node, ast.arg):
                local_definitions[node.arg].append(node)

        return dict(local_definitions)

    @cached_property
    def name(self) -> str:
        if self.scope_type is ScopeType.GLOBAL:
            return "<global>"

        parts = []

        if hasattr(self.node, "name"):
            parts.append(self.node.name)
        elif isinstance(self.node, ast.Lambda):
            parts.append("<lambda>")
        else:
            parts.append("<" + type(self.node).__name__.lower() + ">")

        if (
            self.parent is not None
            and self.parent.scope_type is not ScopeType.GLOBAL
        ):
            if self.parent.scope_type is ScopeType.FUNCTION:
                parts.append("<locals>")
            parts.append(self.parent.name)

        return ".".join(reversed(parts))


class Scope(Representative):

    context_providers = (Ancestry,)

    def resolve(self, node: ast.AST) -> ScopeInfo:
        if isinstance(node, ast.Module):
            raise ValueError("Can't resolve Module")

        parents = [
            parent
            for field, parent in self.context["ancestry"].traverse(node)
            if common.is_contextful(parent)
            if field == "body" or common.is_comprehension(parent)
        ]

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
