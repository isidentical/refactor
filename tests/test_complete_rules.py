import ast
import textwrap

import refactor
from refactor import ReplacementAction


class ReplaceNexts(refactor.Rule):
    def match(self, node):
        # We need a call
        assert isinstance(node, ast.Call)

        # on an attribute (inputs.xxx)
        assert isinstance(node.func, ast.Attribute)

        # where the name for attribute is `inputs`
        assert isinstance(node.func.value, ast.Name)
        assert node.func.value.id == "inputs"

        target_func_name = node.func.attr.removeprefix("next_")

        # make a call to target_func_name (e.g int) with input()
        target_func = ast.Call(
            ast.Name(target_func_name),
            args=[
                ast.Call(ast.Name("input"), args=[], keywords=[]),
            ],
            keywords=[],
        )
        return ReplacementAction(node, target_func)


def test_replace_nexts():

    session = refactor.Session([ReplaceNexts])
    source = textwrap.dedent(
        """\
    def solution(Nexter: inputs):
        # blahblah some code here and there
        n = inputs.next_int()
        sub_process(inputs)
        st = inputs.next_str()
        sub_process(st)"""
    )
    assert session.run(source) == textwrap.dedent(
        """\
    def solution(Nexter: inputs):
        # blahblah some code here and there
        n = int(input())
        sub_process(inputs)
        st = str(input())
        sub_process(st)"""
    )
