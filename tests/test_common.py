import ast
import textwrap

import pytest

from refactor.common import (
    Singleton,
    apply_condition,
    find_closest,
    find_indent,
    has_positions,
    is_contextful,
    is_truthy,
    negate,
    pascal_to_snake,
    position_for,
)


def test_negate():
    source = ast.parse("foo")
    source.body[0].value = negate(source.body[0].value)
    assert ast.unparse(source) == "not foo"


@pytest.mark.parametrize(
    "condition, expected_source", [(True, "foo"), (False, "not foo")]
)
def test_apply_condition(condition, expected_source):
    source = ast.parse("foo")
    source.body[0].value = apply_condition(condition, source.body[0].value)
    assert ast.unparse(source) == expected_source


@pytest.mark.parametrize(
    "operator, expected",
    [
        (ast.Eq(), True),
        (ast.NotEq(), False),
        (ast.In(), True),
        (ast.NotIn(), False),
        (ast.Is(), True),
        (ast.IsNot(), False),
        (ast.Lt(), None),
        (ast.Gt(), None),
        (ast.GtE(), None),
        (ast.LtE(), None),
    ],
)
def test_is_truthy(operator, expected):
    assert is_truthy(operator) is expected


@pytest.mark.parametrize(
    "node, expected",
    [
        (ast.Module(), True),
        (ast.FunctionDef(), True),
        (ast.AsyncFunctionDef(), True),
        (ast.ClassDef(), True),
        (ast.Lambda(), True),
        (ast.BinOp(), False),
        (ast.Constant(), False),
        (ast.If(), False),
    ],
)
def test_is_contextful(node, expected):
    assert is_contextful(node) is expected


@pytest.mark.parametrize(
    "original, expected",
    [
        (str(), str()),
        ("rule", "rule"),
        ("Rule", "rule"),
        ("SomeRule", "some_rule"),
        ("LiteralToConstantRule", "literal_to_constant_rule"),
    ],
)
def test_pascal_to_snake(original, expected):
    assert pascal_to_snake(original) == expected


@pytest.mark.parametrize(
    "original, indent, prefix",
    [
        (str(), str(), str()),
        (" ", " ", str()),
        ("x", "", "x"),
        (" x", " ", "x"),
        ("  x", "  ", "x"),
        ("   x", "   ", "x"),
        ("    ", "    ", ""),
        ("x    ", "", "x    "),
        ("  x    ", "  ", "x    "),
    ],
)
def test_find_indent(original, indent, prefix):
    assert find_indent(original) == (indent, prefix)


def test_find_closest():
    source = textwrap.dedent(
        """\
    def func():
        if a > 5:
            return 5 + 3 + 2
        elif b > 10:
            return 1 + 3 + 5 + 7
    """
    )
    tree = ast.parse(source)
    right_node = tree.body[0].body[0].body[0].value.right
    target_nodes = [
        node
        for node in ast.walk(tree)
        if has_positions(node)
        if node is not right_node
    ]

    closest_node = find_closest(right_node, *target_nodes)
    assert ast.unparse(closest_node) == "3"


def test_get_positions():
    source = textwrap.dedent(
        """\
    def func():
        if a > 5:
            return 5 + 3 + 25
        elif b > 10:
            return 1 + 3 + 5 + 7
    """
    )
    tree = ast.parse(source)
    right_node = tree.body[0].body[0].body[0].value.right
    assert position_for(right_node) == (3, 23, 3, 25)


def test_singleton():
    from dataclasses import dataclass

    @dataclass
    class Point(Singleton):
        x: int
        y: int
        z: int

    p1 = Point(1, 2, 3)
    p2 = Point(1, 2, 3)
    p3 = Point(0, 1, 2)

    assert p1 is p2
    assert p1 is not p3
    assert p2 is not p3
