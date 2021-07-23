import ast
import textwrap
from dataclasses import dataclass

import pytest

from refactor.ast import Node
from refactor.core import Action, Rule, Session


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
        ),
        (
            "2       + 2 == 4",
            lambda mod: mod.body[0].value.comparators[0],
            ast.Constant(5),
            "2       + 2 == 5",
        ),
        (
            "2 + 2 == 4 # :)",
            lambda mod: mod.body[0].value.comparators[0],
            ast.Constant(5),
            "2 + 2 == 5 # :)",
        ),
    ],
)
def test_apply_simple(source, target_func, replacement, expected):
    tree = ast.parse(source)
    action = TargetedAction(target_func(tree), replacement)
    assert action.apply(source) == expected


class SimpleAction(Action):
    def build(self):
        node = self.branch()
        node.op = ast.Sub()
        return node


class PlusToMinusRule(Rule):
    def match(self, node):
        assert isinstance(node, ast.BinOp)
        assert isinstance(node.op, ast.Add)

        return SimpleAction(node)


@pytest.mark.parametrize(
    "source, rules, expected_source",
    [
        ("1+1", [PlusToMinusRule()], "1 - 1"),
        ("print(1 + 1)", [PlusToMinusRule()], "print(1 - 1)"),
        (
            "print(1 + 1, some_other_stuff) and 2 + 2",
            [PlusToMinusRule()],
            "print(1 - 1, some_other_stuff) and 2 - 2",
        ),
        (
            """
        print(
            1 +
            2
        )""",
            [PlusToMinusRule()],
            """
        print(
            1 - 2
        )""",
        ),
    ]
    + [
        ("1*1", [PlusToMinusRule()], "1*1"),
        (
            "print(no,change,style)",
            [PlusToMinusRule()],
            "print(no,change,style)",
        ),
    ],
)
def test_session_simple(source, rules, expected_source):
    source, expected_source = textwrap.dedent(source), textwrap.dedent(
        expected_source
    )

    session = Session(rules)
    assert session.run(source) == expected_source
