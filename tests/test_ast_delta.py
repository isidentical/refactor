import ast
from pathlib import Path

import pytest

import refactor
from refactor.internal.ast_delta import ChangeSet, ChangeType, ast_delta

SOURCE_DIR = Path(refactor.__file__).parent

TREE_1 = ast.parse(
    """\
def full_node_change():
    yield 1

def nested_full_node():
    print(a)

def double_nested_full_node():
    if something:
        return x()

def field_addition():
    raise

def double_field_addition():
    raise

def field_removal():
    raise something

def double_field_removal():
    raise something from something

def field_change():
    print(a)

def multiple_field_change():
    unsafe.function(3 + None)

def sequence_diff():
    a = 1
    b = 2

def nested_sequence_diff():
    if something:
        a = 1
        b = 2

def sequence_size_reduction():
    a = 1
    b = 2
    c = 3

def sequence_size_increase():
    b = 2

def sequence_weird():
    a = {a: b, **b, a: b, a: b, **b, a: b, **b}

def sequence_str():
    global a, x, c, d, y
"""
)

TREE_2 = ast.parse(
    """\
def full_node_change():
    return 1

def nested_full_node():
    print(a + b)

def double_nested_full_node():
    if something:
        return 3 + 5

def field_addition():
    raise something

def double_field_addition():
    raise something from something

def field_removal():
    raise

def double_field_removal():
    raise

def field_change():
    print(b)

def multiple_field_change():
    safe.method(8 + 9)

def sequence_diff():
    a = 1

def nested_sequence_diff():
    if something:
        a = 1
        b = 2
        c = 3

def sequence_size_reduction():
    a = 1
    c = 3

def sequence_size_increase():
    a = 1
    b = 2
    c = 3

def sequence_weird():
    a = {a: b, **b, **b, a: b, a: b, a: b, **b}

def sequence_str():
    global a, b, c, d, e
"""
)

FUNCTION_MAP = {
    function_1.name: (function_1, function_2)
    for function_1, function_2 in zip(TREE_1.body, TREE_2.body)
}


@pytest.fixture
def pack(request):
    function_name = request.node.name.removeprefix("test_")
    baseline, new = FUNCTION_MAP[function_name]
    assert baseline.name == new.name
    return baseline, new, list(ast_delta(baseline, new))


def test_full_node_change(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FULL,
            baseline.body[0],
            new.body[0],
        )
    ]


def test_nested_full_node(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FULL,
            baseline.body[0].value.args[0],
            new.body[0].value.args[0],
        )
    ]


def test_double_nested_full_node(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FULL,
            baseline.body[0].body[0].value,
            new.body[0].body[0].value,
        )
    ]


def test_field_addition(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FIELD_ADDITION,
            baseline.body[0],
            new.body[0],
            on_field="exc",
        )
    ]


def test_double_field_addition(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FIELD_ADDITION,
            baseline.body[0],
            new.body[0],
            on_field="exc",
        ),
        ChangeSet(
            ChangeType.FIELD_ADDITION,
            baseline.body[0],
            new.body[0],
            on_field="cause",
        ),
    ]


def test_field_removal(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FIELD_REMOVAL,
            baseline.body[0],
            new.body[0],
            on_field="exc",
        )
    ]


def test_double_field_removal(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FIELD_REMOVAL,
            baseline.body[0],
            new.body[0],
            on_field="exc",
        ),
        ChangeSet(
            ChangeType.FIELD_REMOVAL,
            baseline.body[0],
            new.body[0],
            on_field="cause",
        ),
    ]


def test_field_change(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FIELD_VALUE,
            baseline.body[0].value.args[0],
            new.body[0].value.args[0],
            on_field="id",
        )
    ]


def test_multiple_field_change(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FIELD_VALUE,
            baseline.body[0].value.func.value,
            new.body[0].value.func.value,
            on_field="id",
        ),
        ChangeSet(
            ChangeType.FIELD_VALUE,
            baseline.body[0].value.func,
            new.body[0].value.func,
            on_field="attr",
        ),
        ChangeSet(
            ChangeType.FIELD_VALUE,
            baseline.body[0].value.args[0].left,
            new.body[0].value.args[0].left,
            on_field="value",
        ),
        ChangeSet(
            ChangeType.FIELD_VALUE,
            baseline.body[0].value.args[0].right,
            new.body[0].value.args[0].right,
            on_field="value",
        ),
    ]


def test_sequence_diff(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(ChangeType.FIELD_SIZE, baseline, new, on_field="body")
    ]


def test_nested_sequence_diff(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FIELD_SIZE,
            baseline.body[0],
            new.body[0],
            on_field="body",
        )
    ]


def test_sequence_size_reduction(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(ChangeType.FIELD_SIZE, baseline, new, on_field="body")
    ]


def test_sequence_size_increase(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(ChangeType.FIELD_SIZE, baseline, new, on_field="body")
    ]


def test_sequence_weird(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.FULL,
            baseline.body[0].value,
            new.body[0].value,
            on_field="keys",
            on_index=2,
        ),
        ChangeSet(
            ChangeType.FULL,
            baseline.body[0].value,
            new.body[0].value,
            on_field="keys",
            on_index=4,
        ),
    ]


def test_sequence_str(pack):
    baseline, new, changes = pack
    assert changes == [
        ChangeSet(
            ChangeType.ITEM_VALUE,
            baseline.body[0],
            new.body[0],
            on_field="names",
            on_index=1,
        ),
        ChangeSet(
            ChangeType.ITEM_VALUE,
            baseline.body[0],
            new.body[0],
            on_field="names",
            on_index=4,
        ),
    ]


def test_no_delta():
    for file in SOURCE_DIR.rglob("*.py"):
        baseline = ast.parse(file.read_text())
        new = ast.parse(file.read_text())
        changes = list(ast_delta(baseline, new))
        if len(changes) > 0:
            pytest.fail(f"ast_delta failed on {file!s}")
