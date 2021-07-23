import ast

from refactor.common import negate


def test_negate():
    source = ast.parse("foo")
    source.body[0].value = negate(source.body[0].value)
    assert ast.unparse(source) == "not foo"
