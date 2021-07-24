from __future__ import annotations

import ast
import typing
from dataclasses import dataclass
from typing import Dict

import refactor
from refactor import common, context


class ImportFinder(refactor.Representative):
    def collect(
        self, name: str, scope: context.ScopeInfo
    ) -> Dict[str, ast.ImportFrom]:
        import_statents = [
            node
            for node in ast.walk(self.context.tree)
            if isinstance(node, ast.ImportFrom)
            if node.module == name
            if scope.can_reach(self.context["scope"].resolve(node))
        ]

        names = {}
        for import_statement in import_statents:
            for alias in import_statement.names:
                names[alias.name] = import_statement

        return names


@dataclass
class AddImportAction(refactor.Action):
    name: str

    def build(self) -> ast.AST:
        new_node = self.branch()
        new_node.names.append(ast.alias(self.name))
        return new_node


class TypingAutoImporter(refactor.Rule):

    context_providers = (ImportFinder, context.Scope)

    def match(self, node: ast.AST) -> refactor.Action:
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)
        assert hasattr(typing, node.id)
        assert not node.id.startswith("__")

        scope = self.context["scope"].resolve(node)
        typing_imports = self.context["import_finder"].collect(
            "typing", scope=scope
        )

        assert len(typing_imports) >= 1
        assert node.id not in typing_imports

        closest_import = common.find_closest(node, *typing_imports.values())
        return AddImportAction(closest_import, node.id)


if __name__ == "__main__":
    refactor.run(rules=[TypingAutoImporter])
