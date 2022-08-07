# Source Transformation Actions

As the [previous tutorial](what_is_a_rule) mentioned; a {term}`rule` consists of two parts, a {term}`contract` and a {term}`transformation`. In this document, we are going
to dive in to existing transformation actions to see how Refactor can help you modify
source code.

## What is an action?

An action is a way of signalling to the Refactor's {term}`engine` with the
expected transformation operation. A more formal definition is an object
that implements the [`BaseAction`](refactor.actions.BaseAction) protocol.

```{tip}
In general, you won't be needing to implement your own action classes since most
of the use cases already come built-in to Refactor; but if you are an advanced user
and want to learn more about custom actions, we can happily refer you to our API
documentation of [`apply()`](refactor.actions.BaseAction.apply).
```

Let's start from exploring the actions.

### Replace

[`Replace`](refactor.actions.Replace) is an {term}`Action` that takes two nodes, and
replaces them directly in the source code. Let's see an example:

```{code-block} python
---
emphasize-lines: 3, 9
---
import ast
from refactor import Rule, Session
from refactor.actions import Replace

class DummyRule(Rule):
    def match(self, node):
        assert isinstance(node, ast.Name)
        assert node.id != "dummy"
        return Replace(node, ast.Name("dummy", ctx=node.ctx))

session = Session(rules=[DummyRule])
print(session.run("result = sum([test1])"))
```

::::{tab-set}

:::{tab-item} First iteration

```python
dummy = sum([test1])
```

:::

:::{tab-item} Second iteration

```python
dummy = dummy([test1])
```

:::

:::{tab-item} Third iteration

```python
dummy = dummy([dummy])
```

:::
::::

### InsertAfter

If you want to insert a new statement, right after a given anchor, this is where [`InsertAfter`](refactor.actions.InsertAfter) comes in. Let's write a rule which
would add a success assertion after every call to a dangerous `run()` function.

```{code-block} python
---
emphasize-lines: 3, 34
---
import ast
from refactor import Rule, Session, common
from refactor.actions import InsertAfter

class DummyRule(Rule):
    def match(self, node):
        # We are looking for
        # $result = run(...)
        assert isinstance(node, ast.Assign)

        # Check for = run(...)
        assert isinstance(call := node.value, ast.Call)
        assert isinstance(func := call.func, ast.Name)
        assert func.id == "run"

        # Ensure that we are only dealing with a simple target
        assert len(targets := node.targets) == 1
        assert isinstance(target := targets[0], ast.Name)

        # IMPORTANT: Ensure that the next statement is not
        # an assert already.
        next_statement = common.next_statement_of(node, context=self.context)
        assert next_statement is None or not isinstance(next_statement, ast.Assert)

        # assert $result != -1
        sanity_check = ast.Assert(
            test=ast.Compare(
                left=target,
                ops=[ast.NotEq()],
                comparators=[ast.Constant(-1)]
            )
        )

        return InsertAfter(node, sanity_check)

session = Session(rules=[DummyRule])
print(session.run("""
from very_dangerous import run

def main():
    result = run("very very problematic")
    do_something(result) # assumes result is good

result = run("something else")
do_something(result)
"""))
```

::::{tab-set}

:::{tab-item} First iteration

```python
from very_dangerous import run


def main():
    result = run("very very problematic")
    assert result != -1
    do_something(result)  # assumes result is good


result = run("something else")
do_something(result)
```

:::

:::{tab-item} Second iteration

```python
from very_dangerous import run


def main():
    result = run("very very problematic")
    assert result != -1
    do_something(result)  # assumes result is good


result = run("something else")
assert result != -1
do_something(result)
```

:::
::::

### Lazy Variants

Some actions have lazy variants, which allow you to shift building of the new
nodes to the actions from rules and use those actions multiple times in your
code without duplicating yourself.

Here are the same rules, but this time with using their lazy counterparts:

::::{tab-set}

:::{tab-item} LazyReplace

```{code-block} python
---
emphasize-lines: 3, 5, 6, 7, 13
---
import ast
from refactor import Rule, Session
from refactor.actions import LazyReplace

class DummyAction(LazyReplace):
    def build(self):
        return ast.Name("dummy", ctx=self.node.ctx)

class DummyRule(Rule):
    def match(self, node):
        assert isinstance(node, ast.Name)
        assert node.id != "dummy"
        return DummyAction(node)
```

:::

:::{tab-item} LazyInsertAfter

```{code-block} python
---
emphasize-lines: 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 39
---
import ast
from dataclasses import dataclass
from refactor import Rule, Session, common
from refactor.actions import LazyInsertAfter

@dataclass
class AddSanityCheck(LazyInsertAfter):
    target: ast.Name

    def build(self):
        return ast.Assert(
            test=ast.Compare(
                left=target,
                ops=[ast.NotEq()],
                comparators=[ast.Constant(-1)]
            )
        )

class DummyRule(Rule):
    def match(self, node):
        # We are looking for
        # $result = run(...)
        assert isinstance(node, ast.Assign)

        # Check for = run(...)
        assert isinstance(call := node.value, ast.Call)
        assert isinstance(func := call.func, ast.Name)
        assert func.id == "run"

        # Ensure that we are only dealing with a simple target
        assert len(targets := node.targets) == 1
        assert isinstance(target := targets[0], ast.Name)

        # IMPORTANT: Ensure that the next statement is not
        # an assert already.
        next_statement = common.next_statement_of(node, context=self.context)
        assert next_statement is None or not isinstance(next_statement, ast.Assert)

        return AddSanityCheck(node, target)
```

:::
::::
