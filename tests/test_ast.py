import ast
import textwrap
import tokenize

import pytest

from refactor.ast import UnparserBase, split_lines
from refactor.common import position_for


def test_split_lines():
    source = textwrap.dedent(
        """\
        1 + 2
        print(foo)
        if not (
            bar
        ):
            print(z)
    """
    )

    assert list(split_lines(source)) == [
        "1 + 2",
        "print(foo)",
        "if not (",
        "    bar",
        "):",
        "    print(z)",
    ]


@pytest.mark.parametrize(
    "source",
    [
        "",
        "\n",
        "\n\n",
        "\n\n\n",
        "\t\n \n \n",
        "x",
        "x\n",
        "x\n\n",
        "x\n\n\n",
        "x\n\nxx\n\n",
    ],
)
def test_split_lines_variations(source):
    lines = split_lines(source)
    assert lines.join() == source


def test_unparser_base():

    source = "a +      b + c # comment"
    tree = ast.parse(source)
    right_node = tree.body[0].value.right

    base = UnparserBase(source)

    assert base.unparse(right_node) == "c"
    assert tokenize.untokenize(base.tokens) == source

    assert base.token_map[position_for(right_node)].string == "c"


class CustomUnparser(UnparserBase):
    def visit_List(self, node):
        with self.delimit("[", "]"):
            with self.indented():
                self.fill()
                self.interleave(
                    lambda: self.write(",") or self.fill(),
                    self.traverse,
                    node.elts,
                )
            self.maybe_newline()


def test_unparser_functions():

    source = "[1, 2]"
    tree = ast.parse(source)

    base = CustomUnparser(source)
    assert base.unparse(tree) == textwrap.dedent(
        """\
    [
        1,
        2
    ]"""
    )
