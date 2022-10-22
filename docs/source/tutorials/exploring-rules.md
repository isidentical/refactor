# Your first Refactor rule

If you have already read [what is Refactor](what_is_refactor) and curious to learn
more about how to actually use it, this is where you should start. In this example,
we'll be building our own little tool to analyze bad code patterns that are nearly
impossible to locate with common text-processing tools and we will write a program
that can automatically fix them!

(specification)=

## Our first transformation

As for our first ever transformation, we want to write a simple program that
would find all additions and subtractions, and if both sides are {term}`constant` it
would transform that operation into its result.

```{code-block} python
---
name: tutorial-program
emphasize-lines: 10, 14, 16
caption: Our example program (with highlighted lines showing what parts we can transform)
---
PI = 3.14
TAU = PI + PI

# This is a very interesting constant that can
# solve world's all problems.
WEIRD_MATH_CONSTANT = PI + TAU

def make_computation(x: int, y: int, z: int) -> float:
    result = (
        WEIRD_MATH_CONSTANT * 2 + (5 + 3) # A very complex math equation
    ) + 8 # Don't forget the 8 here

    # This would help us find the point of origin
    result += 2 + 1

    return 3.14 - 6.28 + result + z * 2
```

(what_is_a_rule)=

### "contract" + "transformation" = "rule"

Each separate analyzer in Refactor corresponds to a ["rule"](refactor.core.Rule), an abstract
component that would structurally hold the information regarding what we are looking for
(e.g., an addition operation) and how we would transform the source code if we find what
we are looking for.

```py
import ast
import refactor
```

Every rule starts with creating a class that inherits from [`refactor.Rule`](refactor.core.Rule)
and defines a custom [`match()`](refactor.core.Rule.match) method. The `match()` method is the
only entry-point to the rule, and it will be called with every node of the tree during the
traversal (in a breadth-first order).

If the given `node` satisfies the criteria of the rule, then `match()` method can return a
source code transformation action (which we'll talk about more the next section) and the
action will be executed immediately.

```{code-block} python
---
emphasize-lines: 4, 5
---
import ast
import refactor

class FoldMyConstants(refactor.Rule):
    def match(self, node: ast.AST) -> refactor.BaseAction:
```

As the section header implies, a rule consist of two parts: "contract" and "transformation". Let's dive in
to the first part.

#### "contract"

There isn't a formal definition of "contract", but it is generally the name we use for the part inside `match()`
that does the filtering on a sea of AST nodes to find something that fits the rule's criteria. Let's write our
contract as per our [specification](specification). We want to ensure that the given `node` is a binary operation
where both sides are {term}`constant`s, and the operator of this operation is either an addition or a subtraction.

::::{tab-set}
:::{tab-item} Trying out assertion based contracts

```{code-block} python
---
emphasize-lines: 6, 7, 8, 9, 10, 11
---
import ast
import refactor

class FoldMyConstants(refactor.Rule):
    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.BinOp)
        assert isinstance(op := node.op, (ast.Add, ast.Sub))
        assert isinstance(left := node.left, ast.Constant)
        assert isinstance(right := node.right, ast.Constant)
        assert isinstance(l_val := left.value, (int, float))
        assert isinstance(r_val := right.value, (int, float))
```

:::

:::{tab-item} Filtering with if statements

```{code-block} python
---
emphasize-lines: 8, 9, 10, 11, 12, 13
---
import ast
import refactor
from typing import Optional

class FoldMyConstants(refactor.Rule):
    def match(self, node: ast.AST) -> Optional[refactor.BaseAction]:
        if not (
            isinstance(node, ast.BinOp)
            and isinstance(op := node.op, (ast.Add, ast.Sub))
            and isinstance(left := node.left, ast.Constant)
            and isinstance(right := node.right, ast.Constant)
            and isinstance(l_val := left.value, (int, float))
            and isinstance(r_val := right.value, (int, float))
        ):
            return None
```

:::
::::

As you might have noticed, we offer two different ways of filtering nodes. The first one, assertion based contracts, is
the recommended way of laying out the conditions in a linearized fashion that is easy to read and operate on. Any `AssertionError`
that might happen on `match()` would be a skip signal, so the {term}`engine` can proceed forward. It is also possible to do
this without assertions (the second way), and just use good old if statements (or even match statements) but don't forget to return
`None` if the given node doesn't fit your rule's criteria.

```{tip}
Our recommendation is using the assertion based contracts for filtering as much as possible, due to their
flexibility (you can have an assertion in anywhere in your code, so instead of handling error paths recursively
you can just depend on an assert to fail) and how readable they are with the linearized writing model
```

#### "transformation"

If our contract is validated (or if all the conditions are met), we'll proceed to the second step: "transformation". This
is where we decide what sort of action we are going to take on top of the source code. It is possible to write your own
actions, but for most of the use cases you should be able to simply use a built-in one.

What we need in our example is an action called [`Replace`](refactor.actions.Replace) which takes a node and a target, and
changes the code belonging to the given node with the re-synthesized version of the target. We'll use it to replace the whole
binary operation with just its result.

```{code-block} python
---
name: tutorial-constant-folding-impl
emphasize-lines: 13, 14, 15, 16, 17
---
import ast
import refactor

class FoldMyConstants(refactor.Rule):
    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.BinOp)
        assert isinstance(op := node.op, (ast.Add, ast.Sub))
        assert isinstance(left := node.left, ast.Constant)
        assert isinstance(right := node.right, ast.Constant)
        assert isinstance(l_val := left.value, (int, float))
        assert isinstance(r_val := right.value, (int, float))

        if isinstance(op, ast.Add):
            result = ast.Constant(l_val + r_val)
        else:
            result = ast.Constant(l_val - r_val)
        return refactor.Replace(node, result)
```

And yes, this is it!

#### Bonus: running the rules

Now it is time for us to test our first rule and see how it performs. For more advanced use cases,
we'll show how you can build your own CLI with a [`session`](refactor.core.Session) but for simple programs
like the one above Refactor itself offers a very convenient mechanism to directly convert your rules into
their own CLI tool.

```{code-block} python
---
emphasize-lines: 20, 21
---
import ast
import refactor

class FoldMyConstants(refactor.Rule):
    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.BinOp)
        assert isinstance(op := node.op, (ast.Add, ast.Sub))
        assert isinstance(left := node.left, ast.Constant)
        assert isinstance(right := node.right, ast.Constant)
        assert isinstance(l_val := left.value, (int, float))
        assert isinstance(r_val := right.value, (int, float))

        if isinstance(op, ast.Add):
            result = ast.Constant(l_val + r_val)
        else:
            result = ast.Constant(l_val - r_val)
        return refactor.Replace(node, result)


if __name__ == "__main__":
    refactor.run(rules=[FoldMyConstants])
```

And with this here, we can execute our Python script and pass it any file we would like. By default
the CLI program will display the diff, but you can also pass `-a` to apply it in-place. Let's test this on
our [example program](#tutorial-program).

```diff
--- program.py
+++ program.py

@@ -7,10 +7,10 @@


 def make_computation(x: int, y: int, z: int) -> float:
     result = (
-        WEIRD_MATH_CONSTANT * 2 + (5 + 3) # A very complex math equation
+        WEIRD_MATH_CONSTANT * 2 + (8) # A very complex math equation
     ) + 8 # Don't forget the 8 here

     # This would help us find the point of origin
-    result += 2 + 1
+    result += 3

-    return 3.14 - 6.28 + result + z * 2
+    return -3.14 + result + z * 2
```

As you can see from the diff, it handled the transformation very delicately and
changed only what it needed to change.

## Going further

Fortunately in the snippet above, there are still some stuff left that we can work on.
The one that hits to me in the first glance is, both `TAU` and `WEIRD_MATH_CONSTANT` could have
been folded if they were used as constants instead of names.

```{code-block} python
---
emphasize-lines: 2, 6
---
PI = 3.14
TAU = PI + PI

# This is a very interesting constant that can
# solve world's all problems.
WEIRD_MATH_CONSTANT = PI + TAU

def make_computation(x: int, y: int, z: int) -> float:
    result = (
        WEIRD_MATH_CONSTANT * 2 + (5 + 3) # A very complex math equation
    ) + 8 # Don't forget the 8 here
```

So why don't we start writing a new rule that would resolve all the names with a value that is easy
to infer. This is called [constant propagation](https://en.wikipedia.org/wiki/Constant_folding#Constant_propagation), and I think it will play nicely
with our [constant folding](https://en.wikipedia.org/wiki/Constant_folding) implementation in the [first rule](tutorial-constant-folding-impl).

```{code-block} python
---
emphasize-lines: 1, 4
---
from refactor.context import Scope

class PropagateMyConstants(refactor.Rule):
    context_providers = (Scope,)
```

We started as usual, by inheriting from [`Rule`](refactor.core.Rule), but this time we have a new
keyword: `context_providers`. Each rule in Refactor has a shared state / knowledge base of the current
file. It is accessible by the `context` attribute, and contains stuff like the source code, tree, and
most importantly context providers.

Context providers operate on the module-level, unlike to rules which operate on the node-level, and they are really useful
for gathering knowledge from surroundings and sharing them with rules to do more precise analyses. There
are a bunch of built-in ones, like [`Ancestry`](refactor.context.Ancestry) which can help you to backtrack
a node to its parents. But what what need today is [`Scope`](refactor.context.Scope). It allows you to learn
which semantical scope a node belongs to, and where it can access from it.

```{code-block} python
---
emphasize-lines: 10
---
from refactor.context import Scope

class PropagateMyConstants(refactor.Rule):
    context_providers = (Scope,)

    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)

        scope = self.context.scope.resolve(node)
```

As you can see, once we are in a spot on our contract where we need scope information to decide
further we access it directly under `self.context`. After accessing to it, we call [`resolve()`](refactor.context.Scope.resolve)
with the node we want to learn more and it returns a [`ScopeInfo`](refactor.context.ScopeInfo) record.

```{tip}
All initialized context providers can be accessed by their name (actually their name's snake case
version, so `Scope` is `scope` and `SomethingProvider` is `something_provider`) so we can simply say
`self.context.scope`
```

The record contains information about your current scope, the node that encloses you (semantically), all
the definitions that are made inside your scope and a very important method: [`get_definitions()`](refactor.context.ScopeInfo.get_definitions).
It is how we ask Refactor to tell us where a given name (like `PI`, or `TAU`) is defined. It goes back in all reachable
scopes (like if you are inside a top-level function, and if the name you are accessing is not defined in there then it will check
the global scope) until it finds a set of definitions.

Let's retrieve the definitions and check if the assigned value is a {term}`constant`. Also for keeping this example simple, we won't be considering
names that are defined multiple times (e.g., conditionally by an if statement or overwritten in some part of the program) so we want the number
of definitions to be only one. And if all of our checks pass, we'll return an action to replace it.

```{code-block} python
---
emphasize-lines: 11, 12, 17, 18, 19
---
from refactor.context import Scope

class PropagateMyConstants(refactor.Rule):
    context_providers = (Scope,)

    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)

        scope = self.context.scope.resolve(node)
        definitions = scope.get_definitions(node.id)
        assert len(definitions) == 1

        # The definition might be anything, it might be coming
        # from an import or it might be function. So we'll only
        # allow assignments.
        [definition] = definitions
        assert isinstance(definition, ast.Assign)
        assert isinstance(defined_value := definition.value, ast.Constant)
        return refactor.Replace(node, defined_value)
```

Let's test out how our rules now perform in three different ways:

::::{tab-set}

:::{tab-item} Only propagation

```diff
--- program.py
+++ program.py

@@ -1,9 +1,9 @@

 PI = 3.14
-TAU = PI + PI
+TAU = 3.14 + 3.14

 # This is a very interesting constant that can
 # solve world's all problems.
-WEIRD_MATH_CONSTANT = PI + TAU
+WEIRD_MATH_CONSTANT = 3.14 + TAU
```

:::

:::{tab-item} Only folding

```diff
--- program.py
+++ program.py

@@ -7,10 +7,10 @@


 def make_computation(x: int, y: int, z: int) -> float:
     result = (
-        WEIRD_MATH_CONSTANT * 2 + (5 + 3) # A very complex math equation
+        WEIRD_MATH_CONSTANT * 2 + (8) # A very complex math equation
     ) + 8 # Don't forget the 8 here

     # This would help us find the point of origin
-    result += 2 + 1
+    result += 3

-    return 3.14 - 6.28 + result + z * 2
+    return -3.14 + result + z * 2
```

:::

:::{tab-item} Running both

As you can see, this is where the main difference comes from.

```diff
--- program.py
+++ program.py

@@ -1,16 +1,16 @@

 PI = 3.14
-TAU = PI + PI
+TAU = 6.28

 # This is a very interesting constant that can
 # solve world's all problems.
-WEIRD_MATH_CONSTANT = PI + TAU
+WEIRD_MATH_CONSTANT = 9.42

 def make_computation(x: int, y: int, z: int) -> float:
     result = (
-        WEIRD_MATH_CONSTANT * 2 + (5 + 3) # A very complex math equation
+        9.42 * 2 + (8) # A very complex math equation
     ) + 8 # Don't forget the 8 here

     # This would help us find the point of origin
-    result += 2 + 1
+    result += 3

-    return 3.14 - 6.28 + result + z * 2
+    return -3.14 + result + z * 2
```

:::
::::

```{note}
The full code for this example is available at our [GitHub repo](https://github.com/isidentical/refactor/tree/master/examples/tutorial/constant-folding)
```
