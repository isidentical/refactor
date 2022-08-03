import ast
import textwrap

import pytest

from refactor.ast import BaseUnparser
from refactor.context import (
    Ancestry,
    Configuration,
    Context,
    Representative,
    Scope,
    resolve_dependencies,
)
from refactor.core import Rule


def get_context(source, *representatives, **kwargs):
    tree = ast.parse(textwrap.dedent(source))
    config = Configuration(**kwargs)
    return Context.from_dependencies(
        resolve_dependencies(representatives),
        config=config,
        tree=tree,
        source=source,
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
    assert definitions["a"].definitions.keys() == {"a", "B", "something"}

    # Can't access class-local
    assert not cursors["b"].can_reach(definitions["b"])
    assert definitions["b"].definitions.keys() == {"b", "foo"}

    # Can access nonlocal variable
    assert cursors["c"].can_reach(definitions["c"])
    assert definitions["c"].definitions.keys() == {"self", "c", "bar"}

    # Can access local variable
    assert cursors["d"].can_reach(definitions["d"])
    assert definitions["d"].definitions.keys() == {"d"}

    # Every variable can access the scope they are defined in
    for name, node_scope in find_calls(tree, "self_read", scope):
        assert node_scope.can_reach(definitions[name])

    # All reads from outside of those scope chain is forbidden
    for name, node_scope in find_calls(tree, "out_read", scope):
        assert not node_scope.can_reach(definitions[name])

    with pytest.raises(ValueError):
        scope.resolve(tree)


def test_scope_definitions():
    context = get_context(
        textwrap.dedent(
            """
            import g_i
            import g_i_1, g_i.d

            from fi import g_fi_1
            from fi.d import g_fi_2, g_fi_3

            g_a = 1
            g_a_1 = g_a_2 = 2
            g_a_2 = 3
            accessor()

            def g_f(f_arg, *, f_arg1 = (g_a_4 := something)) -> (g_a_5 := other):
                object.d = 1
                f_loc, f_loc_1 = (1, 2)
                f_loc_2 = lambda: (l_loc := 1) and accessor()

                import f_i
                accessor()

                return [accessor() for comp_1 in y for comp_2 in z]

            class g_c:
                c_a = 1
                c_a_1, c_a_2 = meth_factory(c_a_3 := d)

                accessor()

                def c_f():
                    c_f.d = 3
                    for f_for_a, f_for_b in c:
                        with x as (f_a.d, f_a.d.d1.d2):
                            pass
                        accessor()
            """
        ),
        Scope,
    )

    tree = context.tree
    scope = context.metadata["scope"]

    accessors = [
        node for node in ast.walk(tree) if ast.unparse(node) == "accessor()"
    ]

    scopes = {
        scope_info.name: scope_info
        for scope_info in map(scope.resolve, accessors)
    }

    assert scopes.keys() == {
        "<global>",
        "g_f",
        "g_c",
        "g_c.c_f",
        "g_f.<locals>.<lambda>",
        "g_f.<locals>.<listcomp>",
    }

    assert scopes["<global>"].definitions.keys() == {
        "g_i",
        "g_i_1",
        "g_i.d",
        "g_fi_1",
        "g_fi_2",
        "g_fi_3",
        "g_a",
        "g_a_1",
        "g_a_2",
        "g_f",
        "g_c",
        "g_a_4",
        "g_a_5",
    }
    assert scopes["g_f"].definitions.keys() == {
        "object.d",
        "f_loc",
        "f_loc_1",
        "f_loc_2",
        "f_i",
        "f_arg",
        "f_arg1",
    }
    assert scopes["g_c"].definitions.keys() == {
        "c_a",
        "c_a_1",
        "c_a_2",
        "c_f",
        "c_a_3",
    }
    assert scopes["g_c.c_f"].definitions.keys() == {
        "c_f.d",
        "f_for_a",
        "f_for_b",
        "f_a.d",
        "f_a.d.d1.d2",
    }
    assert scopes["g_f.<locals>.<lambda>"].definitions.keys() == {"l_loc"}
    assert scopes["g_f.<locals>.<listcomp>"].definitions.keys() == {
        "comp_1",
        "comp_2",
    }

    [g_a_1] = scopes["<global>"].definitions["g_a_1"]
    g_a_2 = scopes["<global>"].definitions["g_a_2"]

    assert isinstance(g_a_1, ast.Assign)
    assert ast.unparse(g_a_1.value) == "2"

    assert isinstance(g_a_2, list) and len(g_a_2) == 2
    assert [ast.unparse(definition.value) for definition in g_a_2] == [
        "2",
        "3",
    ]


def test_custom_unparser():
    class StaticUnparser(BaseUnparser):
        def unparse(self, node):
            return "<chulak>"

    regular_context = get_context("hey")
    assert regular_context.unparse(ast.parse("hey")) == "hey"

    default_unparser = get_context("hey", unparser="fast")
    assert default_unparser.unparse(ast.parse("hey")) == "hey"

    context = get_context("hey", unparser=StaticUnparser)
    assert context.unparse(ast.parse("hey")) == "<chulak>"


def test_dependency_resolver():
    class Rep1(Representative):
        pass

    class Rep2(Representative):
        context_providers = (Rep1,)

    class Rep3(Representative):
        context_providers = (Rep2,)

    class Rule1(Rule):
        pass

    class Rule2(Rule):
        context_providers = (Rep1,)

    class Rule3(Rule):
        context_providers = (Rep1,)

    class Rule4(Rule):
        context_providers = (Rep1, Rep2)

    class Rule5(Rule):
        context_providers = (Rep2,)

    class Rule6(Rule):
        context_providers = (Rep3,)

    assert resolve_dependencies([Rule1]) == set()
    assert resolve_dependencies([Rule2]) == {Rep1}
    assert resolve_dependencies([Rule3]) == {Rep1}
    assert resolve_dependencies([Rule4]) == {Rep1, Rep2}
    assert resolve_dependencies([Rule5]) == {Rep1, Rep2}
    assert resolve_dependencies([Rule6]) == {Rep1, Rep2, Rep3}

    assert resolve_dependencies([Rule1, Rule2]) == {Rep1}
    assert resolve_dependencies([Rule2, Rule3]) == {Rep1}
    assert resolve_dependencies([Rule1, Rule2, Rule3]) == {Rep1}
    assert resolve_dependencies([Rule1, Rule2, Rule4]) == {Rep1, Rep2}
    assert resolve_dependencies([Rule1, Rule5]) == {Rep1, Rep2}
    assert resolve_dependencies([Rule1, Rule6]) == {Rep1, Rep2, Rep3}
    assert resolve_dependencies([Rule1, Rule2, Rule5, Rule6]) == {
        Rep1,
        Rep2,
        Rep3,
    }


def test_dependency_resolver_recursion():
    class Rep1(Representative):
        pass

    Rep1.context_providers = (Rep1,)

    class Rep2(Representative):
        pass

    class Rep3(Representative):
        pass

    Rep2.context_providers = (Rep3,)
    Rep3.context_providers = (Rep2,)

    class Rep4(Representative):
        context_providers = (Rep2, Rep1)

    class Rule1(Rule):
        context_providers = (Rep1,)

    class Rule2(Rule):
        context_providers = (Rep2,)

    class Rule3(Rule):
        context_providers = (Rep3,)

    class Rule4(Rule):
        context_providers = (Rep4,)

    assert resolve_dependencies([Rule1]) == {Rep1}
    assert resolve_dependencies([Rule2]) == {Rep2, Rep3}
    assert resolve_dependencies([Rule3]) == {Rep2, Rep3}
    assert resolve_dependencies([Rule4]) == {Rep1, Rep2, Rep3, Rep4}
