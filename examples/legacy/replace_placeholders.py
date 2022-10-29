# python examples/replace_placeholders.py examples/test/placeholder.py

from __future__ import annotations

import ast

import refactor
from refactor import Rule
from refactor.actions import Replace


class ReplacePlaceholders(Rule):
    def match(self, node):
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)
        assert node.id == "placeholder"

        replacement = ast.Constant(42)
        return Replace(node, replacement)


if __name__ == "__main__":
    refactor.run(rules=[ReplacePlaceholders])
