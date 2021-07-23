import ast
from dataclasses import dataclass

import pytest

from refactor.ast import Node
from refactor.core import Action


@dataclass
class TargetedAction(Action):
    replacement: Node

    def build(self):
        return self.replacement


@pytest.mark.parametrize(
    "source, target_func, replacement, expected",
    [
        (
            "2 + 2 == 4",
            lambda mod: mod.body[0].value.comparators[0],
            ast.Constant(5),
            "2 + 2 == 5",
        )
    ],
)
def test_apply_basic(source, target_func, replacement, expected):
    tree = ast.parse(source)
    action = TargetedAction(target_func(tree), replacement)
    assert action.apply(source) == expected
