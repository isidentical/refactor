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

### Erase / EraseOrReplace

If you are interested in erasing a statement completely out of the source code, you can use [`Erase`](refactor.actions.Erase)
{term}`action`. It takes a statement, and if that statement's removal won't create any problems (e.g. removing the only child
statement under a block, like in the **invalid** case below) it will remove it completely.

```{code-block} python
---
emphasize-lines: 3, 8
---
import ast
from refactor import Rule, Session
from refactor.actions import Erase

class EraseAsserts(Rule):
    def match(self, node):
        assert isinstance(node, ast.Assert)
        return Erase(node)
```

::::{tab-set}

:::{tab-item} Valid Case

```python
def main(x, y):
    assert x >= 5
    if y <= 3:
        y += 5
        assert y > 3
    assert x + y > 8
    return x + y
```

```py
def main(x, y):
    if y <= 3:
        y += 5
    return x + y
```

:::

:::{tab-item} Invalid Case

```python
def main(x, y):
    if x is not None:
        assert x >= 5
    else:
        x = 3
    return x + y
```

Running the `EraseAsserts` rule on this case would result with an [`InvalidActionError`](refactor.actions.InvalidActionError)
since the removal of `assert x >= 5` would have resulted with the generation of an unparsable version of the source code (empty if block).

:::

::::

If you don't want to worry about whether a statement is required or not by yourself and leave it to Refactor, you can
use [`EraseOrReplace`](refactor.actions.EraseOrReplace) which would end up replacing all required statements with `pass`
statement (or any other statement that you'd pass).


```{code-block} python
---
emphasize-lines: 3, 8
---
import ast
from refactor import Rule, Session, common
from refactor.actions import EraseOrReplace

class EliminateDeadCode(Rule):
    def match(self, node):
        assert isinstance(node, ast.If)
        assert isinstance(node.test, ast.Constant)
        assert isinstance(node.test.value, bool)
        assert not node.test.value
        assert not node.orelse
        return EraseOrReplace(node)

session = Session(rules=[EliminateDeadCode])
print(session.run("""
def something():
    if False:
        print("something!")
        if False:
            print("hello")

def another():
    if False:
        print("another")
    return "not eliminated"
"""))
```

::::{tab-set}

:::{tab-item} First iteration

```python
def something():
    if False:
        print("something!")

def another():
    if False:
        print("another")
    return "not eliminated"
```

:::

:::{tab-item} Second iteration

```python
def something():
    pass

def another():
    if False:
        print("another")
    return "not eliminated"
```

:::

:::{tab-item} Third iteration

```python
def something():
    pass

def another():
    return "not eliminated"
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
