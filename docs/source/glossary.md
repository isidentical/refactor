# Glossary

::::{glossary}
constant
    An `ast.Constant` object that represents a hard-coded literal in the source code.

engine
    Engine is the core transformation loop that resides within a [session](refactor.core.Session). It
    is responsible for traversing the AST, managing rules and their context as well as running them
    on each node and continuously transform the source code until nothing more can be done with it.

rule
    A rule is a static analyzing component that holds the information about an analysis's {term}`contract`
    and {term}`transformation`. A more concrete definition includes every class that inherits from [`Rule`](refactor.core.Rule)
    and implements a [`match()`](refactor.core.Rule.match) method.

    :::{code-block} python
    class DummyRule(refactor.Rule):

        def match(self, node):
            assert isinstance(node, ast.Name)
            assert node.id != "dummy"
            return Replace(node, ast.Name("dummy", ctx=node.ctx))
    :::

contract
    A contract is an informal section of a {term}`rule`'s `match()` method that filters the nodes.

    :::{code-block} python
    ---
    emphasize-lines: 4, 5
    ---
    class DummyRule(refactor.Rule):

        def match(self, node):
            assert isinstance(node, ast.Name)
            assert node.id != "dummy"
            return Replace(node, ast.Name("dummy", ctx=node.ctx))
    :::

transformation
    A transformation is an informal section of a {term}`rule`'s `match()` method that prepares the
    {term}`action` for source transformation.

    :::{code-block} python
    ---
    emphasize-lines: 6
    ---
    class DummyRule(refactor.Rule):

        def match(self, node):
            assert isinstance(node, ast.Name)
            assert node.id != "dummy"
            return Replace(node, ast.Name("dummy", ctx=node.ctx))
    :::

action
    An action, or a source transformation action, is an object that implements the [`BaseAction`](refactor.actions.BaseAction)
    protocol. There are multiple built-in ones, like [`Replace`](refactor.actions.Replace) or [`InsertAfter`](refactor.actions.InsertAfter),
    in addition to the ones that the user can write.

    :::{code-block} python
    ---
    emphasize-lines: 1, 2, 3, 9
    ---
    class DummyAction(LazyReplace):
        def build(self):
            return ast.Name("dummy", ctx=self.nod.ctx)

    class DummyRule(Rule):
        def match(self, node):
            assert isinstance(node, ast.Name)
            assert node.id != "dummy"
            return DummyAction(node)
    :::

context
    A [Context](refactor.context.Context) object that represents the state of the current processed module (including the
    raw source code, full tree, as well as all the initialized context providers). Shared between all {term}`rule`s in the
    same {term}`session`.

session
    A [Session](refactor.core.Session) object that represents a collection of {term}`rule`s to run together.
::::
