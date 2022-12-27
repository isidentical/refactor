from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import cast, Iterator

import pytest

from refactor import common
from refactor.ast import DEFAULT_ENCODING

from refactor.actions import Erase, InvalidActionError, InsertAfter, Replace, LazyInsertAfter
from refactor.context import Context
from refactor.core import Rule, Session

INVALID_ERASES = """
def foo():
    assert 1

if something:
    assert 1
elif something:
    assert 1
else:
    assert 1

try:
    assert 1
except Exception:
    assert 1
else:
    assert 1

for x in y:
    assert 1
else:
    assert 1

while True:
    assert 1
else:
    assert 1

with x as y:
    assert 1
"""

INVALID_ERASES_TREE = ast.parse(INVALID_ERASES)


@dataclass
class BuildInsertAfterBottom(LazyInsertAfter):
    separator: bool
    def build(self) -> ast.Await:
        await_st = ast.parse("await async_test()")
        return await_st


class TestInsertAfterBottom(Rule):
    INPUT_SOURCE = """
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
            second_tree = get_tree(second_tree, module_name)
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    EXPECTED_SOURCE = """
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        await async_test()"""

    def match(self, node: ast.AST) -> Iterator[InsertAfter]:
        assert isinstance(node, ast.Try)
        assert len(node.body) >= 2

        await_st = ast.parse("await async_test()")
        yield InsertAfter(node, cast(ast.stmt, await_st))
        new_try = common.clone(node)
        new_try.body = [node.body[0]]
        yield Replace(node, cast(ast.AST, new_try))


class TestInsertAfterBottomWithBuild(Rule):
    INPUT_SOURCE = """
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
            second_tree = get_tree(second_tree, module_name)
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    EXPECTED_SOURCE = """
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        await async_test()"""

    def match(self, node: ast.AST) -> Iterator[InsertAfter]:
        assert isinstance(node, ast.Try)
        assert len(node.body) >= 2

        yield BuildInsertAfterBottom(node, separator=False)
        new_try = common.clone(node)
        new_try.body = [node.body[0]]
        yield Replace(node, cast(ast.AST, new_try))


@pytest.mark.parametrize(
    "invalid_node",
    [node for node in ast.walk(INVALID_ERASES_TREE) if isinstance(node, ast.Assert)],
)
def test_erase_invalid(invalid_node):
    context = Context(INVALID_ERASES, INVALID_ERASES_TREE)
    with pytest.raises(InvalidActionError):
        Erase(invalid_node).apply(context, INVALID_ERASES)

@pytest.mark.parametrize(
    "rule",
    [
        TestInsertAfterBottom,
        TestInsertAfterBottomWithBuild,
    ],
)
def test_rules(rule, tmp_path):
    session = Session([rule])

    source_code = textwrap.dedent(rule.INPUT_SOURCE)
    try:
        ast.parse(source_code)
    except SyntaxError:
        pytest.fail("Input source is not valid Python code")

    assert session.run(source_code) == textwrap.dedent(rule.EXPECTED_SOURCE)

    src_file_path = Path(tmp_path / rule.__name__.lower()).with_suffix(".py")
    src_file_path.write_text(source_code, encoding=DEFAULT_ENCODING)

    change = session.run_file(src_file_path)
    assert change is not None

    change.apply_diff()
    assert src_file_path.read_text(encoding=DEFAULT_ENCODING) == textwrap.dedent(
        rule.EXPECTED_SOURCE
    )
