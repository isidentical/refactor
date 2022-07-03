import ast
import textwrap
import tokenize

import pytest

from refactor.ast import BaseUnparser, PreciseUnparser, split_lines


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

    base = BaseUnparser(source=source)

    assert base.unparse(right_node) == "c"
    assert tokenize.untokenize(base.tokens) == source


class CustomUnparser(BaseUnparser):
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

    base = CustomUnparser(source=source)
    assert base.unparse(tree) == textwrap.dedent(
        """\
        [
            1,
            2
        ]"""
    )


def test_precise_unparser():
    source = textwrap.dedent(
        """\
    def func():
        if something:
            print(
                call(.1),
                maybe+something_else,
                maybe / other,
                thing   . a
            )
    """
    )

    expected_src = textwrap.dedent(
        """\
    def func():
        if something:
            print(call(.1), maybe+something_else, maybe / other, thing   . a, 3)
    """
    )

    tree = ast.parse(source)
    tree.body[0].body[0].body[0].value.args.append(ast.Constant(3))

    base = PreciseUnparser(source=source)
    assert base.unparse(tree) + "\n" == expected_src


def test_precise_unparser_indented_literals():
    source = textwrap.dedent(
        """\
    def func():
        if something:
            print(
                "bleh"
                "zoom"
            )
    """
    )

    expected_src = textwrap.dedent(
        """\
    def func():
        if something:
            print("bleh"
                "zoom", 3)
    """
    )

    tree = ast.parse(source)
    tree.body[0].body[0].body[0].value.args.append(ast.Constant(3))

    base = PreciseUnparser(source=source)
    assert base.unparse(tree) + "\n" == expected_src
