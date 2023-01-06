from __future__ import annotations

import ast
import textwrap
from pathlib import Path
from typing import Iterator, cast

import pytest
from refactor.ast import DEFAULT_ENCODING

from refactor import Session, common
from refactor.actions import Erase, InvalidActionError, InsertAfter, Replace, InsertBefore
from refactor.common import clone
from refactor.context import Context
from refactor.core import Rule

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


class TestInsertAfterBottom(Rule):
    INPUT_SOURCE = """
        def undecorated():
            test_this()"""

    EXPECTED_SOURCE = """
        async def undecorated():
            test_this()
        await async_test()"""

    def match(self, node: ast.AST) -> Iterator[InsertAfter]:
        assert isinstance(node, ast.FunctionDef)

        await_st = ast.parse("await async_test()")
        yield InsertAfter(node, cast(ast.stmt, await_st))
        new_node = clone(node)
        new_node.__class__ = ast.AsyncFunctionDef
        yield Replace(node, new_node)


class TestInsertBeforeTop(Rule):
    INPUT_SOURCE = """
        def undecorated():
            test_this()"""

    EXPECTED_SOURCE = """
        await async_test()
        async def undecorated():
            test_this()"""

    def match(self, node: ast.AST) -> Iterator[InsertBefore]:
        assert isinstance(node, ast.FunctionDef)

        await_st = ast.parse("await async_test()")
        yield InsertBefore(node, cast(ast.stmt, await_st))
        new_node = clone(node)
        new_node.__class__ = ast.AsyncFunctionDef
        yield Replace(node, new_node)


class TestInsertBeforeDecoratedFunction(Rule):
    INPUT_SOURCE = """
        @decorate
        def decorated():
            test_this()"""

    EXPECTED_SOURCE = """
        await async_test()
        @decorate
        async def decorated():
            test_this()"""

    def match(self, node: ast.AST) -> Iterator[InsertBefore]:
        assert isinstance(node, ast.FunctionDef)

        await_st = ast.parse("await async_test()")
        yield InsertBefore(node, cast(ast.stmt, await_st))
        new_node = clone(node)
        new_node.__class__ = ast.AsyncFunctionDef
        yield Replace(node, new_node)


class TestInsertAfter(Rule):
    INPUT_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
            second_tree = get_tree(second_tree, module_name)
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            base_tree = get_tree(base_file, module_name)
            active_tree = get_tree(active_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    EXPECTED_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            second_tree = get_tree(second_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            active_tree = get_tree(active_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    def match(self, node: ast.AST) -> Iterator[InsertAfter]:
        assert isinstance(node, ast.Try)
        assert len(node.body) >= 2

        new_trys = []
        for stmt in node.body:
            new_try = common.clone(node)
            new_try.body = [stmt]
            new_trys.append(new_try)

        first_try, *remaining_trys = new_trys
        yield Replace(node, first_try)
        for remaining_try in reversed(remaining_trys):
            yield InsertAfter(node, remaining_try)


class TestInsertBefore(Rule):
    INPUT_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
            second_tree = get_tree(second_tree, module_name)
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            base_tree = get_tree(base_file, module_name)
            active_tree = get_tree(active_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    EXPECTED_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            second_tree = get_tree(second_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            active_tree = get_tree(active_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    def match(self, node: ast.AST) -> Iterator[InsertBefore]:
        assert isinstance(node, ast.Try)
        assert len(node.body) >= 2

        new_trys = []
        for stmt in node.body:
            new_try = common.clone(node)
            new_try.body = [stmt]
            new_trys.append(new_try)

        first_try, *remaining_trys = new_trys
        yield Replace(node, first_try)
        for remaining_try in remaining_trys:
            yield InsertBefore(node, remaining_try)


class TestInsertAfterThenBefore(Rule):
    INPUT_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
            second_tree = get_tree(second_tree, module_name)
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    EXPECTED_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            second_tree = get_tree(second_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            second_tree = get_tree(second_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    def match(self, node: ast.AST) -> Iterator[Replace | InsertAfter | InsertBefore]:
        assert isinstance(node, ast.Try)
        assert len(node.body) >= 2

        new_trys = []
        for stmt in node.body:
            new_try = common.clone(node)
            new_try.body = [stmt]
            new_trys.append(new_try)

        first_try, *remaining_trys = new_trys
        yield Replace(node, first_try)
        for remaining_try in reversed(remaining_trys):
            yield InsertAfter(node, remaining_try)
        for remaining_try in remaining_trys:
            yield InsertBefore(node, remaining_try)


class TestInsertBeforeThenAfterBothReversed(Rule):
    INPUT_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
            second_tree = get_tree(second_tree, module_name)
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    EXPECTED_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            second_tree = get_tree(second_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            second_tree = get_tree(second_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    def match(self, node: ast.AST) -> Iterator[Replace | InsertAfter | InsertBefore]:
        assert isinstance(node, ast.Try)
        assert len(node.body) >= 2

        new_trys = []
        for stmt in node.body:
            new_try = common.clone(node)
            new_try.body = [stmt]
            new_trys.append(new_try)

        first_try, *remaining_trys = new_trys
        yield Replace(node, first_try)
        for remaining_try in reversed(remaining_trys):
            yield InsertBefore(node, remaining_try)
        for remaining_try in reversed(remaining_trys):
            yield InsertAfter(node, remaining_try)


class TestInsertAfterBeforeRepeat(Rule):
    INPUT_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
            second_tree = get_tree(second_tree, module_name)
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            base_tree = get_tree(base_file, module_name)
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    EXPECTED_SOURCE = """
    def generate_index(base_path, active_path):
        try:
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            second_tree = get_tree(second_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            second_tree = get_tree(second_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            third_tree = get_tree(third_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue

        print('processing ', module_name)
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            base_tree = get_tree(base_file, module_name)
        except (SyntaxError, FileNotFoundError):
            continue
        try:
            first_tree = get_tree(first_tree, module_name)
        except (SyntaxError, FileNotFoundError):
            continue"""

    def match(self, node: ast.AST) -> Iterator[Replace | InsertAfter | InsertBefore]:
        assert isinstance(node, ast.Try)
        assert len(node.body) >= 2

        new_trys = []
        for stmt in node.body:
            new_try = common.clone(node)
            new_try.body = [stmt]
            new_trys.append(new_try)

        first_try, *remaining_trys = new_trys
        yield Replace(node, first_try)
        # It is important to note that we reversed the changes
        # This can have a counter-intuitive expectation of the results
        # Possibly, a less confusing testcase could be implemented ;P
        for remaining_try in reversed(remaining_trys[:3]):
            yield InsertBefore(node, remaining_try)
            yield InsertAfter(node, remaining_try)


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
        TestInsertBeforeDecoratedFunction,
        TestInsertAfterBottom,
        TestInsertBeforeTop,
        TestInsertAfter,
        TestInsertBefore,
        TestInsertAfterThenBefore,
        TestInsertBeforeThenAfterBothReversed,
        TestInsertAfterBeforeRepeat,
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
