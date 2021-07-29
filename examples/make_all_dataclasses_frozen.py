import ast

from refactor import ReplacementAction, Rule, run


class FreezeDataclasses(Rule):
    def match(self, node: ast.AST) -> ReplacementAction:
        assert isinstance(node, ast.ClassDef)
        assert len(node.decorator_list) == 1
        assert isinstance(decorator := node.decorator_list[0], ast.Name)
        assert decorator.id == "dataclass"

        dataclass = ast.Call(
            decorator,
            args=[],
            keywords=[ast.keyword("frozen", ast.Constant(True))],
        )
        return ReplacementAction(decorator, dataclass)


if __name__ == "__main__":
    run(rules=[FreezeDataclasses])
