import ast

import pytest

from refactor.actions import Erase, InvalidActionError
from refactor.context import Context

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


@pytest.mark.parametrize(
    "invalid_node",
    [
        node
        for node in ast.walk(INVALID_ERASES_TREE)
        if isinstance(node, ast.Assert)
    ],
)
def test_erase_invalid(invalid_node):
    context = Context(INVALID_ERASES, INVALID_ERASES_TREE)
    with pytest.raises(InvalidActionError):
        Erase(invalid_node).apply(context, INVALID_ERASES)
