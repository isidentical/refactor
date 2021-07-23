import ast
import textwrap

import pytest

from refactor.context import Representative
from refactor.core import Action, ReplacementAction, Rule, Session


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
    action = ReplacementAction(target_func(tree), replacement)
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


class SimpleRepresentative(Representative):
    name = "simple"

    def infer_value(self, node):
        return ast.Constant(42)


class PlaceholderReplacer(Rule):

    context_providers = (SimpleRepresentative,)

    def match(self, node):
        assert isinstance(node, ast.Name)
        assert node.id == "placeholder"

        return ReplacementAction(
            node, self.context["simple"].infer_value(node)
        )


@pytest.mark.parametrize(
    "source, rules, expected_source",
    [
        ("1+1", PlusToMinusRule, "1 - 1"),
        ("print(1 + 1)", PlusToMinusRule, "print(1 - 1)"),
        (
            "print(1 + 1, some_other_stuff) and 2 + 2",
            PlusToMinusRule,
            "print(1 - 1, some_other_stuff) and 2 - 2",
        ),
        (
            """
        print(
            1 +
            2
        )""",
            PlusToMinusRule,
            """
        print(
            1 - 2
        )""",
        ),
        (
            "print(x, y, placeholder, z)",
            PlaceholderReplacer,
            "print(x, y, 42, z)",
        ),
    ]
    + [
        ("1*1", PlusToMinusRule, "1*1"),
        (
            "print(no,change,style)",
            PlusToMinusRule,
            "print(no,change,style)",
        ),
    ],
)
def test_session_simple(source, rules, expected_source):
    if isinstance(rules, type):
        rules = [rules]

    source, expected_source = textwrap.dedent(source), textwrap.dedent(
        expected_source
    )

    session = Session(rules)
    assert session.run(source) == expected_source
