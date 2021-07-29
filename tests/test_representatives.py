import ast
import textwrap

import pytest

from refactor.context import (
    Ancestry,
    Context,
    CustomUnparser,
    Representative,
    Scope,
    resolve_dependencies,
)


def get_context(source, *representatives):
    tree = ast.parse(textwrap.dedent(source))
    return Context.from_dependencies(
        resolve_dependencies(representatives), tree=tree, source=source
    )


def find_calls(tree, func_name, scope):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == func_name
        ):
            yield node.args[0].id, scope.resolve(node.args[0])


def test_representative():
    context = get_context("hello", Representative)
    assert isinstance(context.metadata["<base>"], Representative)


def test_ancestry():
    context = get_context("2 + 3 + 4", Ancestry)
    tree = context.tree
    first_stmt = context.tree.body[0]

    ancestry = context.metadata["ancestry"]
    assert ancestry.get_parent(first_stmt) is tree
    assert (
        ancestry.get_parent(first_stmt.value.left.right)
        is first_stmt.value.left
    )


def test_scope():
    context = get_context(
        textwrap.dedent(
            """
    a = 5
    self_read(a)
    class B:
        b = 4
        self_read(b)
        def foo(self):
            c = 3
            self_read(c)
            def bar():
                d = 2
                self_read(d)
                return a, b, c, d
    
    out_read(b)
    out_read(c)
    out_read(d)
    def something():
        out_read(b)
        out_read(c)
        out_read(d)
    
        def something():
            out_read(b)
            out_read(c)
            out_read(d)
    """
        ),
        Scope,
    )
    tree = context.tree

    scope = context.metadata["scope"]

    return_tuple = tree.body[2].body[2].body[2].body[2].value
    assert isinstance(return_tuple, ast.Tuple)

    definitions = {
        node.targets[0].id: scope.resolve(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
    }

    cursors = {name.id: scope.resolve(name) for name in return_tuple.elts}

    # Can access global!
    assert cursors["a"].can_reach(definitions["a"])

    # Can't access class-local
    assert not cursors["b"].can_reach(definitions["b"])

    # Can access nonlocal variable
    assert cursors["c"].can_reach(definitions["c"])

    # Can access local variable
    assert cursors["d"].can_reach(definitions["d"])

    # Every variable can access the scope they are defined in
    for name, node_scope in find_calls(tree, "self_read", scope):
        assert node_scope.can_reach(definitions[name])

    # All reads from outside of those scope chain is forbidden
    for name, node_scope in find_calls(tree, "out_read", scope):
        assert not node_scope.can_reach(definitions[name])

    with pytest.raises(ValueError):
        scope.resolve(tree)


def test_custom_unparser():
    class StaticUnparser(CustomUnparser):
        def unparse(self, node):
            return "<chulak>"

    regular_context = get_context("hey")
    assert regular_context.unparse(ast.parse("hey")) == "hey"

    default_unparser = get_context("hey", CustomUnparser)
    assert default_unparser.unparse(ast.parse("hey")) == "hey"

    context = get_context("hey", StaticUnparser)
    assert context.unparse(ast.parse("hey")) == "<chulak>"
