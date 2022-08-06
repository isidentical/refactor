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
    Iterator,
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
    """Configuration settings for a refactoring session.

    unparser: precise, fast, or a `BaseUnparser` subclass.
    debug_mode: whether to output more debug information.
    """

    unparser: Union[str, Type[BaseUnparser]] = "precise"
    debug_mode: bool = False


class _Dependable(Protocol):
    context_providers: ClassVar[Tuple[Type[Representative], ...]]

    def __init__(self, context: Context) -> None:
        ...


def _resolve_dependencies(
    dependables: Iterable[Type[_Dependable]],
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
    """The knowledge base of the currently processed module. Includes
    the original source code, the full AST, as well as the all the representatives.
    """

    source: str
    tree: ast.AST

    file: Optional[Path] = None
    config: Configuration = field(default_factory=Configuration)
    metadata: Dict[str, Representative] = field(default_factory=dict)

    @classmethod
    def _from_dependencies(
        cls, dependencies: Iterable[Type[Representative]], **kwargs: Any
    ) -> Context:
        context = cls(**kwargs)
        context._import_dependencies(dependencies)
        return context

    def _import_dependencies(
        self, representatives: Iterable[Type[Representative]]
    ) -> None:
        for raw_representative in representatives:
            representative = raw_representative(self)
            self.metadata[representative.name] = representative

    def unparse(self, node: ast.AST) -> str:
        """Re-synthesize the source code for the given ``node``."""

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
        # For built-in representatives, we can automatically import them.
        if key in _BUILTIN_REPRESENTATIVES:
            self._import_dependencies(
                _resolve_dependencies([_BUILTIN_REPRESENTATIVES[key]])
            )

        if key not in self.metadata:
            raise ValueError(
                f"{key!r} provider is not available on this context "
                "since none of the rules from this session specified it "
                "in it's 'context_providers' tuple."
            )
        return self.metadata[key]

    def __getattr__(self, attr: str) -> Representative:
        try:
            return self[attr]
        except ValueError:
            raise AttributeError(f"{self!r} has no attribute {attr!r}")


@dataclass
class Representative:
    """A tree-scoped metadata collector."""

    context_providers: ClassVar[Tuple[Type[Representative], ...]] = ()

    context: Context

    @cached_property
    def name(self) -> str:
        """Name of the representative (to be used when accessing
        from the scope). By default, it is the snake case version
        of the class' name."""

        self_type = type(self)
        if self_type is Representative:
            return "<base>"
        else:
            return common.pascal_to_snake(self_type.__name__)


class Ancestry(Representative):
    """
    A context provider that helps you to backtrack nodes
    using their ancestral chain in AST.
    """

    def _marked(self, node: ast.AST) -> bool:
        return hasattr(node, "parent")

    def _mark(self, parent: ast.AST, field: str, node: Any) -> None:
        if isinstance(node, ast.AST):
            node.parent = parent
            node.parent_field = field

    def _annotate(self, node: ast.AST) -> None:
        if self._marked(node):
            return None

        node.parent = None
        node.parent_field = None
        for parent in ast.walk(node):
            for field, value in ast.iter_fields(parent):
                if isinstance(value, list):
                    for item in value:
                        self._mark(parent, field, item)
                else:
                    self._mark(parent, field, value)

    def _ensure_annotated(self) -> None:
        self._annotate(self.context.tree)

    def infer(self, node: ast.AST) -> Tuple[str, ast.AST]:
        """Return the given `node`'s parent field (the field
        name in parent which this node is stored in) and the
        parent."""
        self._ensure_annotated()
        return (node.parent_field, node.parent)

    def traverse(self, node: ast.AST) -> Iterable[Tuple[str, ast.AST]]:
        """Recursively infer a `node`'s parent field and parent."""
        cursor = node
        while True:
            field, parent = self.infer(cursor)
            if parent is None:
                break

            yield field, parent
            cursor = parent

    def get_parent(self, node: ast.AST) -> Optional[ast.AST]:
        """Return the parent AST node of the given `node`."""
        _, parent = self.infer(node)
        return parent

    def get_parents(self, node: ast.AST) -> Iterable[ast.AST]:
        """Recursively yield all the parent AST nodes of the given `node`."""
        for _, parent in self.traverse(node):
            yield parent


class ScopeType(Enum):
    GLOBAL = auto()
    CLASS = auto()
    FUNCTION = auto()
    COMPREHENSION = auto()


@dataclass(unsafe_hash=True)
class ScopeInfo(common._Singleton):
    node: ast.AST
    scope_type: ScopeType
    parent: Optional[ScopeInfo] = field(default=None, repr=False)

    def _iter_reachable_scopes(self) -> Iterator[ScopeInfo]:
        yield self

        cursor: ScopeInfo = self
        # TODO: implement a more fine grained scope resolution with support
        # for nested comprehensions.
        while cursor := cursor.parent:  # type: ignore
            if cursor.scope_type in (ScopeType.FUNCTION, ScopeType.GLOBAL):
                yield cursor

    def can_reach(self, other: ScopeInfo) -> bool:
        """Return whether this scope can access definitions
        from `other` scope."""
        for reachable_scope in self._iter_reachable_scopes():
            if reachable_scope is other:
                return True
        else:
            return False

    def get_definitions(self, name: str) -> Optional[List[ast.AST]]:
        """Return all the definitions of the given `name` that
        this scope can reach.

        Returns `None` if no definitions are found."""
        for reachable_scope in self._iter_reachable_scopes():
            if reachable_scope.defines(name):
                return reachable_scope.definitions[name]
        else:
            return None

    def defines(self, name: str) -> bool:
        """Return whether this scope defines the given `name`."""
        return name in self.definitions

    @cached_property
    def definitions(self) -> Dict[str, List[ast.AST]]:
        """Return all the definitions made inside this scope.

        .. note::
            It doesn't include definitions made in child scopes.
        """

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
        """Return the name of this scope."""
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
    """A context provider for working with semantical Python
    scopes."""

    context_providers = (Ancestry,)

    def resolve(self, node: ast.AST) -> ScopeInfo:
        """Return the scope record of the given `node`."""
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


_BUILTIN_REPRESENTATIVES = {
    "ancestry": Ancestry,
    "scope": Scope,
}
