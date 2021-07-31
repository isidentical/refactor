import ast
import textwrap

import pytest

from refactor.change import Change
from refactor.context import Context, Representative
from refactor.core import (
    Action,
    NewStatementAction,
    ReplacementAction,
    Rule,
    Session,
)

fake_ctx = Context(source="<test>", tree=ast.AST())


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
    assert action.apply(fake_ctx, source) == expected


def test_apply_new_statement():
    source = textwrap.dedent(
        """
    import x # comments
    print(x.y) # comments here
    def something(x, y):
        return x + y # comments"""
    )

    expected_source = textwrap.dedent(
        """
    import x # comments
    import x
    print(x.y) # comments here
    def something(x, y):
        return x + y # comments"""
    )

    tree = ast.parse(source)
    action = NewStatementAction(tree.body[0])
    assert action.apply(fake_ctx, source) == expected_source


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


def test_session_run_file(tmp_path):
    session = Session([PlaceholderReplacer])

    file_1 = tmp_path / "test.py"
    file_2 = tmp_path / "test2.py"
    file_3 = tmp_path / "test3.py"

    with open(file_1, "w") as handle:
        handle.write("something + something\n")

    assert session.run_file(file_1) is None

    with open(file_2, "w") as handle:
        handle.write("2 + placeholder + 3")

    change = session.run_file(file_2)
    assert change is not None
    assert isinstance(change, Change)
    assert change.original_source == "2 + placeholder + 3"
    assert change.refactored_source == "2 + 42 + 3"

    with open(file_3, "w") as handle:
        handle.write("syntax? error?")

    assert session.run_file(file_3) is None


class InvalidAction(Action):
    def apply(self, context, source):
        return "??"


class InvalidRule(Rule):
    def match(self, node):
        assert isinstance(node, ast.BinOp)
        assert isinstance(node.op, ast.Add)

        return InvalidAction(node)


def test_session_invalid_source_generated(tmp_path):
    session = Session([InvalidRule])

    with pytest.raises(ValueError):
        assert session.run("2 + 2")

    assert session.run("2 + ??") == "2 + ??"


class RecursiveRule(Rule):
    def match(self, node):
        return Action(node)


def test_session_run_deterministic():
    session = Session([RecursiveRule])

    refactored_source, changed = session._run("2 + 2 + 3 + 4")
    assert not changed
    assert refactored_source == "2 + 2 + 3 + 4"
