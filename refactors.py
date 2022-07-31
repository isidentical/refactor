import ast
from pathlib import Path
from typing import Optional

import refactor
from refactor import InsertAfter, Replace
from refactor.context import Scope


class RefactorAsserts(refactor.Rule):
    FILES = frozenset(["refactor/common.py"])

    def check_file(self, file: Optional[Path]) -> bool:
        return str(file) in self.FILES

    def match(self, node: ast.AST) -> Replace:
        assert isinstance(node, ast.Assert)

        replacement = ast.Raise(
            exc=ast.Call(
                ast.Name("ValueError", ast.Load()),
                args=[
                    ast.Constant(f"condition failed: {ast.unparse(node.test)}")
                ],
                keywords=[],
            )
        )
        guard = ast.If(
            test=ast.UnaryOp(op=ast.Not(), operand=node.test),
            body=[replacement],
            orelse=[],
        )
        return Replace(node, guard)


def _is_hinted_with(node: ast.AST, name: str) -> bool:
    return (
        len(node.decorator_list) >= 1
        and isinstance(node.decorator_list[0], ast.Call)
        and isinstance(node.decorator_list[0].func, ast.Name)
        and node.decorator_list[0].func.id == "_hint"
        and node.decorator_list[0].args[0].value == name
    )


class RefactorDeprecatedAliases(refactor.Rule):
    FILES = frozenset(["refactor/actions.py"])
    context_providers = (Scope,)

    def check_file(self, file: Optional[Path]) -> bool:
        return str(file) in self.FILES

    def match(self, node: ast.AST) -> Optional[InsertAfter]:
        assert isinstance(node, ast.ClassDef)
        assert _is_hinted_with(node, "deprecated_alias")

        alias_name = node.decorator_list[0].args[1].value

        # If we already have the alias, then we can pass
        # this check.
        global_scope = self.context.metadata["scope"].resolve(node)
        if global_scope.defines(alias_name):
            return None

        replacement = ast.ClassDef(
            name=alias_name,
            bases=[ast.Name(node.name), ast.Name("_DeprecatedAliasMixin")],
            keywords=[],
            body=[ast.Expr(ast.Constant(...))],
            decorator_list=[ast.Name("dataclass")],
        )
        return InsertAfter(node, replacement)


if __name__ == "__main__":
    refactor.run([RefactorAsserts, RefactorDeprecatedAliases])
