from __future__ import annotations

import ast
from dataclasses import dataclass, field
from functools import cached_property
from typing import Dict, Iterable, Type


@dataclass
class Context:
    source: str
    tree: ast.AST
    metadata: Dict[str, Representative] = field(default_factory=dict)

    def __getitem__(self, key):
        return self.metadata[key]

    @classmethod
    def from_dependencies(
        cls, dependencies: Iterable[Type[Representative]], **kwargs
    ):
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
    context: Context

    @cached_property
    def name(self):
        self_type = type(self)
        if self_type is Representative:
            return "<base>"
        else:
            return self_type.__name__.lower()
