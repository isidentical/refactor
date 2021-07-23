# python examples/replace_placeholders.py examples/test/placeholder.py

import ast

import refactor
from refactor import ReplacementAction, Rule


class ReplacePlaceholders(Rule):
    def match(self, node):
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)
        assert node.id == "placeholder"

        replacement = ast.Constant(42)
        return ReplacementAction(node, replacement)


if __name__ == "__main__":
    refactor.run(rules=[ReplacePlaceholders])
