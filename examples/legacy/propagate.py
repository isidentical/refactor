from __future__ import annotations

import ast

import refactor
from refactor.context import Scope


class PropagateConstants(refactor.Rule):
    context_providers = (Scope,)

    def match(self, node):
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)

        current_scope = self.context["scope"].resolve(node)
        assert current_scope.defines(node.id)

        definitions = current_scope.definitions[node.id]

        assert len(definitions) == 1
        assert isinstance(definition := definitions[0], ast.Assign)
        assert isinstance(value := definition.value, ast.Constant)

        return refactor.Replace(node, value)


if __name__ == "__main__":
    refactor.run(rules=[PropagateConstants])
