import ast
from pathlib import Path
from typing import Optional

import refactor
from refactor import Action, ReplacementAction


class RefactorAsserts(refactor.Rule):
    FILES = frozenset(["refactor/common.py"])

    def check_file(self, file: Optional[Path]) -> bool:
        return str(file) in self.FILES

    def match(self, node: ast.AST) -> Action:
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
        return ReplacementAction(node, guard)


if __name__ == "__main__":
    refactor.run([RefactorAsserts])
