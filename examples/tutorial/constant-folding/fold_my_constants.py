import ast

import refactor
from refactor.context import Scope


class FoldMyConstants(refactor.Rule):
    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.BinOp)
        assert isinstance(op := node.op, (ast.Add, ast.Sub))
        assert isinstance(left := node.left, ast.Constant)
        assert isinstance(right := node.right, ast.Constant)
        assert isinstance(l_val := left.value, (int, float))
        assert isinstance(r_val := right.value, (int, float))

        if isinstance(op, ast.Add):
            result = ast.Constant(l_val + r_val)
        else:
            result = ast.Constant(l_val - r_val)
        return refactor.Replace(node, result)


class PropagateMyConstants(refactor.Rule):
    context_providers = (Scope,)

    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)

        scope = self.context.scope.resolve(node)
        definitions = scope.get_definitions(node.id) or []
        assert len(definitions) == 1

        definition = definitions[0]
        assert isinstance(definition, ast.Assign)
        assert isinstance(defined_value := definition.value, ast.Constant)
        return refactor.Replace(node, defined_value)


if __name__ == "__main__":
    refactor.run(rules=[FoldMyConstants, PropagateMyConstants])
