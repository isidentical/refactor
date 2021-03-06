# Replace calls like type('') or type({}) with the actual
# types like str or dict.

import ast

import refactor
from refactor import ReplacementAction, Rule
from refactor.context import Scope


class ReplaceTypeLiterals(Rule):

    context_providers = (Scope,)

    def match(self, node):
        assert isinstance(node, ast.Call)
        assert isinstance(func := node.func, ast.Name)
        assert func.id == "type"

        assert len(node.args) == 1
        assert type(arg := node.args[0]) in (
            ast.Constant,
            ast.List,
            ast.Tuple,
            ast.Dict,
        )

        match arg:
            case ast.Constant(value) if arg.value not in (None, Ellipsis):
                type_name = type(value).__name__
            case ast.List():
                type_name = "list"
            case ast.Tuple():
                type_name = "tuple"
            case ast.Dict():
                type_name = "dict"
            case _:
                return None

        scope = self.context["scope"].resolve(node)

        for name, reason in [
            (type_name, "arg-name-already-defined"),
            ("type", "type-function-redefined"),
        ]:
            if name in scope.definitions:
                definition = scope.definitions[name]
                if isinstance(definition, list):
                    definition = definition[0]

                line = definition.lineno
                print(f"skipping: {reason} (on line {line})")
                return None

        return ReplacementAction(node, ast.Name(type_name, ast.Load()))


if __name__ == "__main__":
    refactor.run(rules=[ReplaceTypeLiterals])
