from __future__ import annotations

import ast
import textwrap
import tokenize

import pytest

from refactor import common, Context
from refactor.ast import BaseUnparser, PreciseUnparser, split_lines
from refactor.common import position_for, clone


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
        "1 + 2\n",
        "print(foo)\n",
        "if not (\n",
        "    bar\n",
        "):\n",
        "    print(z)\n",
    ]


@pytest.mark.parametrize(
    "case",
    [
        """
            print(normal)
            print('🚀 🚀 🚀')
            print(
                '🚀 🚀 🚀 $$ '
                ' $$ 🚀 🚀 🚀'
            )
            print('天 小 末')
            末 = '🚀 🚀 🚀' * 4
        """
    ],
)
def test_split_lines_with_encoding(case):
    case = textwrap.dedent(case)
    lines = split_lines(case, encoding="utf-8")
    assert lines.join() == case

    for node in ast.walk(ast.parse(case)):
        if not common.has_positions(type(node)):
            continue

        (
            lineno,
            col_offset,
            end_lineno,
            end_col_offset,
        ) = common.position_for(node)
        lineno, end_lineno = lineno - 1, end_lineno - 1

        if end_lineno == lineno:
            match = lines[lineno][col_offset:end_col_offset]
        else:
            start_line = lines[lineno][col_offset:]
            end_line = lines[end_lineno][:end_col_offset]
            match = start_line + lines[lineno + 1 : end_lineno].join() + end_line

        assert str(match) == ast.get_source_segment(case, node)


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
        "x\n\r\nxx\r\n\r\n",
        "x\n\r\n\nx\r\n\r\n\r\n",
        "x\n\r\n\nx\r\n\r\r",
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
            # On change, comments are removed
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


def test_precise_unparser_comments():
    source = textwrap.dedent(
        """\
    def foo():
    # unindented comment
        # indented but not connected comment

        # a
        # a1
        print()
        # a2
        print()
        # b

        # b2
        print(
            c # e
        )
        # c
        print(d)
        # final comment
    """
    )

    expected_src = textwrap.dedent(
        """\
    def foo():
        # a
        # a1
        print()
        # a2
        print()
        # b
        # b2
        print(
            c # e
        )
        # c
    """
    )

    tree = ast.parse(source)

    # # Remove the print(d)
    tree.body[0].body.pop()

    base = PreciseUnparser(source=source)
    assert base.unparse(tree) + "\n" == expected_src


def test_precise_unparser_custom_indent_no_changes():
    source = """def func():
    if something:
        # Arguments have custom indentation
        print(call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        )
"""

    expected_src = """def func():
    if something:
        # Arguments have custom indentation
        print(call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        )
"""

    tree = ast.parse(source)

    base = PreciseUnparser(source=source)
    assert base.unparse(tree) + "\n" == expected_src


def test_precise_unparser_custom_indent_del():
    source = """def func():
    if something:
        # Arguments have custom indentation
        print(call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        )
"""

    expected_src = """def func():
    if something:
        print(call(.1), maybe+something_else_that_is_very_very_very_long, thing   . a)
"""

    tree = ast.parse(source)
    del tree.body[0].body[0].body[0].value.args[2]

    base = PreciseUnparser(source=source)
    assert base.unparse(tree) + "\n" == expected_src


def test_apply_source_formatting_maintains_with_await_0():
    source = """def func():
    if something:
        # Comments are retrieved
        print(
              call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        )
"""

    expected_src = """def func():
    if something:
        # Comments are retrieved
        await print(
              call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        )
"""
    source_tree = ast.parse(source)
    context = Context(source, source_tree)

    node_to_replace = source_tree.body[0].body[0].body[0].value

    (lineno, col_offset, end_lineno, end_col_offset) = position_for(node_to_replace)
    view = slice(lineno - 1, end_lineno)

    lines = split_lines(source)
    source_lines = lines[view]

    new_node = ast.Await(node_to_replace)
    replacement = split_lines(context.unparse(new_node))
    replacement.apply_source_formatting(
        source_lines=source_lines,
        markers=(0, col_offset, end_col_offset),
    )
    lines[view] = replacement
    assert lines.join() == expected_src


def test_apply_source_formatting_maintains_with_await_1():
    source = """def func():
    if something:
        # Comments are retrieved
        print(call(.1), # Comments are retrieved. separation can be updated to x spaces (1 default)
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,# Comments are retrieved. separation can be updated to x spaces (1 default)
              thing   . a
        )
"""

    expected_src = """def func():
    if something:
        # Comments are retrieved
        await print(call(.1), # Comments are retrieved. separation can be updated to x spaces (1 default)
              maybe+something_else_that_is_very_very_very_long,
              maybe / other, # Comments are retrieved. separation can be updated to x spaces (1 default)
              thing   . a
        )
"""
    source_tree = ast.parse(source)
    context = Context(source, source_tree)

    node_to_replace = source_tree.body[0].body[0].body[0].value

    (lineno, col_offset, end_lineno, end_col_offset) = position_for(node_to_replace)
    view = slice(lineno - 1, end_lineno)

    lines = split_lines(source)
    source_lines = lines[view]

    new_node = ast.Await(node_to_replace)
    replacement = split_lines(context.unparse(new_node))
    replacement.apply_source_formatting(
        source_lines=source_lines,
        markers=(0, col_offset, end_col_offset),
    )
    lines[view] = replacement
    assert lines.join() == expected_src


def test_apply_source_formatting_maintains_with_call():
    source = """def func():
    if something:
        # Comments are retrieved
        print(call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        )
"""

    expected_src = """def func():
    if something:
        # Comments are retrieved
        call_instead(print(call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        ))
"""
    source_tree = ast.parse(source)
    context = Context(source, source_tree)

    node_to_replace = source_tree.body[0].body[0].body[0].value

    (lineno, col_offset, end_lineno, end_col_offset) = position_for(node_to_replace)
    view = slice(lineno - 1, end_lineno)

    lines = split_lines(source)
    source_lines = lines[view]

    new_node = ast.Call(func=ast.Name(id="call_instead"), args=[node_to_replace], keywords=[])
    replacement = split_lines(context.unparse(new_node))
    replacement.apply_source_formatting(
        source_lines=source_lines,
        markers=(0, col_offset, end_col_offset),
    )
    lines[view] = replacement
    assert lines.join() == expected_src


def test_apply_source_formatting_maintains_with_call_on_closing_parens():
    source = """def func():
    if something:
        # Comments are retrieved
        print(call(.1), # Comments are retrieved, spacing of x spaces (1 default)
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,     # Comments are retrieved, spacing of x spaces (1 default)
              thing   . a
          ) # Non-standard indent is conserved and comments, spacing of x spaces (1 default)
"""

    expected_src = """def func():
    if something:
        # Comments are retrieved
        call_instead(print(call(.1), # Comments are retrieved, spacing of x spaces (1 default)
              maybe+something_else_that_is_very_very_very_long,
              maybe / other, # Comments are retrieved, spacing of x spaces (1 default)
              thing   . a
          )) # Non-standard indent is conserved and comments, spacing of x spaces (1 default)
"""
    source_tree = ast.parse(source)
    context = Context(source, source_tree)

    node_to_replace = source_tree.body[0].body[0].body[0].value

    (lineno, col_offset, end_lineno, end_col_offset) = position_for(node_to_replace)
    view = slice(lineno - 1, end_lineno)

    lines = split_lines(source)
    source_lines = lines[view]

    new_node = ast.Call(func=ast.Name(id="call_instead"), args=[node_to_replace], keywords=[])
    replacement = split_lines(context.unparse(new_node))
    replacement.apply_source_formatting(
        source_lines=source_lines,
        markers=(0, col_offset, end_col_offset),
    )
    lines[view] = replacement
    assert lines.join() == expected_src


def test_apply_source_formatting_maintains_with_async_complex():
    source = """def func():
    if something:
        # Comments are retrieved
        with print(call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        ) as p:
            do_something()
"""

    expected_src = """def func():
    if something:
        # Comments are retrieved
        async with print(call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        ) as p:
            do_something()
"""
    source_tree = ast.parse(source)
    context = Context(source, source_tree)

    node_to_replace = source_tree.body[0].body[0].body[0]

    (lineno, col_offset, end_lineno, end_col_offset) = position_for(node_to_replace)
    view = slice(lineno - 1, end_lineno)

    lines = split_lines(source)
    source_lines = lines[view]

    new_node = clone(node_to_replace)
    new_node.__class__ = ast.AsyncWith
    replacement = split_lines(context.unparse(new_node))
    replacement.apply_source_formatting(
        source_lines=source_lines,
        markers=(0, col_offset, end_col_offset),
    )
    lines[view] = replacement
    assert lines.join() == expected_src


def test_apply_source_formatting_maintains_with_async():
    source = """def func():
    if something:
        # Comments are retrieved
        with something: # comment2, spacing of x spaces (1 default)
             a = 1 # Non-standard indent is conserved, spacing of x spaces (1 default)
             b = 2 # Non-standard indent is conserved, spacing of x spaces (1 default)
"""

    expected_src = """def func():
    if something:
        # Comments are retrieved
        async with something: # comment2, spacing of x spaces (1 default)
             a = 1 # Non-standard indent is conserved, spacing of x spaces (1 default)
             b = 2 # Non-standard indent is conserved, spacing of x spaces (1 default)
"""
    source_tree = ast.parse(source)
    context = Context(source, source_tree)

    node_to_replace = source_tree.body[0].body[0].body[0]

    (lineno, col_offset, end_lineno, end_col_offset) = position_for(node_to_replace)
    view = slice(lineno - 1, end_lineno)

    lines = split_lines(source)
    source_lines = lines[view]

    new_node = clone(node_to_replace)
    new_node.__class__ = ast.AsyncWith
    replacement = split_lines(context.unparse(new_node))
    replacement.apply_source_formatting(
        source_lines=source_lines,
        markers=(0, col_offset, end_col_offset),
    )
    lines[view] = replacement
    assert lines.join() == expected_src


def test_apply_source_formatting_maintains_with_fstring():
    source = '''def f():
    return """
a
"""
'''

    expected_src = '''def f():
    return F("""
a
""")
'''

    source_tree = ast.parse(source)
    context = Context(source, source_tree)

    node_to_replace = source_tree.body[0].body[0].value

    (lineno, col_offset, end_lineno, end_col_offset) = position_for(node_to_replace)
    view = slice(lineno - 1, end_lineno)

    lines = split_lines(source)
    source_lines = lines[view]

    new_node = ast.Call(func=ast.Name(id="F"), args=[node_to_replace], keywords=[])
    replacement = split_lines(context.unparse(new_node))
    replacement.apply_source_formatting(
        source_lines=source_lines,
        markers=(0, col_offset, end_col_offset),
    )
    lines[view] = replacement
    assert lines.join() == expected_src


def test_apply_source_formatting_does_not_with_change():
    source = """def func():
    if something:
        # Comments are retrieved
        print(call(.1),
              maybe+something_else_that_is_very_very_very_long,
              maybe / other,
              thing   . a
        )
"""

    expected_src = """def func():
    if something:
        # Comments are retrieved
        await print(call(.1), maybe+something_else_that_is_very_very_very_long, thing   . a)
"""

    source_tree = ast.parse(source)
    context = Context(source, source_tree)

    node_to_replace = source_tree.body[0].body[0].body[0].value

    (lineno, col_offset, end_lineno, end_col_offset) = position_for(node_to_replace)
    view = slice(lineno - 1, end_lineno)

    lines = split_lines(source)
    source_lines = lines[view]

    del node_to_replace.args[2]
    new_node = ast.Await(node_to_replace)
    replacement = split_lines(context.unparse(new_node))
    replacement.apply_source_formatting(
        source_lines=source_lines,
        markers=(0, col_offset, end_col_offset),
    )
    lines[view] = replacement
    assert lines.join() == expected_src
