import ast

from refactor.context import Ancestry, Context


def get_context(representative, source):
    tree = ast.parse(source)
    return Context.from_dependencies(
        [representative], tree=tree, source=source
    )


def test_ancestry():
    context = get_context(Ancestry, "2 + 3 + 4")
    tree = context.tree
    first_stmt = context.tree.body[0]

    ancestry = context.metadata["ancestry"]
    assert ancestry.get_parent(first_stmt) is tree
    assert (
        ancestry.get_parent(first_stmt.value.left.right)
        is first_stmt.value.left
    )
