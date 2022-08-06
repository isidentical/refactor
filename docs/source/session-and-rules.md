# Tutorial

If you have already read [what is Refactor](what_is_refactor) and curious to learn
more about how to actually use it, this is where you should start. In this example,
we'll be building our own little tool to analyze bad code patterns that are nearly
impossible to locate with common text-processing tools and we will write a tool
that automatically fixes them!

(specification)=

## Our first "rule"

As for our first ever "rule" (will come to that), we want to write a simple program that
would find all additions and subtractions, and if both sides are constants it would transform
that operation into its result.

```py
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

### "contract" + "transformation" = "rule"

Each transformation in Refactor corresponds to a [rule](refactor.core.Rule), an abstract
component that would structurally hold the information regarding what we are looking for
(e.g., an addition operation) and how we would transform the source code if we find what
we are looking for.

```py
import ast
import refactor
```

We can start defining a new rule by simply inheriting from [`refactor.Rule`](refactor.core.Rule).

```py
class FoldMyConstants(refactor.Rule):
```

Every rule is responsible for implementing a single API: [`match()`](refactor.core.Rule.match). This
method will be the only way for us to interact with Refactor's engine, it will call us on each node of
the tree (while traversing) and if it gives us a `node` that fits our criteria we'll return a source
transformation action.

```py
    def match(self, node: ast.AST) -> refactor.BaseAction:
```

As the section's header suggests, a "rule" consist of two parts. The "contract" is where we define
what we are looking for. In general, you can write this section however you'd like but the Refactor-way
of doing this is using `assert`'s to guide matcher through.

```py
        assert isinstance(node, ast.BinOp)
```

Any `AssertionError` will be automatically caught by Refactor, and it will signal to the engine that given node
does not satisfy this rule's contract. Of course you can also use `if` statements (or even `match`
statements) and a return of `None` from `match()` would also mean to skip this rule on this node. The primary
advantage of `assert`'s is that, they linearize and clearly lay out what you are looking for like a contract.

Let's start verifying the `node` as per our [specification](specification). We want to ensure that both
sides of the node are constants, and the operator for this binary operation is either an `ast.Add` or an
`ast.Sub`.

```py
        assert isinstance(op := node.op, (ast.Add, ast.Sub))
        assert isinstance(left := node.left, ast.Constant)
        assert isinstance(right := node.right, ast.Constant)
        assert isinstance(l_val := left.value, (int, float))
        assert isinstance(r_val := right.value, (int, float))
```

If all the checks pass, we'll proceed to the second step: "transformation". There are different ways in Refactor on
how you could transform a piece of code, but the most used one is [`Replace`](refactor.actions.Replace). It is also
what we need here, since we want to create a replacement node and then replace the original node with our result node.

```py
        if isinstance(op, ast.Add):
            result = ast.Constant(l_val + r_val)
        else:
            result = ast.Constant(l_val - r_val)
        return refactor.Replace(node, result)
```

And yes, this is it! Now it is time for us to test our first rule and see how it performs. For more advanced use cases,
we'll show how you can build your own CLI with a [`session`](%60refactor.core.Session%60) but for simple programs like the
one above Refactor itself offers a very convient mechanism to directly convert your rule into its own CLI.

```py
if __name__ == "__main__":
    refactor.run(rules=[FoldMyConstants])
```

And with this here, we can execute our Python script and pass it any file we would like. By default
the CLI will display the diff, but you can also pass `-a` to apply it in-place. Let's test this on
our [example program](#specification).

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
emphasize-lines: 2,6
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
to infer. This is called [constant propagation](constant_propagation), and I think it will play nicely
with our [constant folding](specification) from the first example.

```{code-block} python
---
emphasize-lines: 1,4
---
from refactor.context import Scope

class PropagateMyConstants(refactor.Rule):
    context_providers = (Scope,)
```

We started as usual, by inheriting from [`Rule`](refactor.core.Rule), but this time we have a new
keyword: `context_providers`. Each rule in refactor has a shared state / knowledge base of the current
file. It is accessible by the `context` attribute, and contains stuff like the source code, tree, and
most importantly context providers.

Context providers operate on the module-level, unlike to node-level rules, and they are really useful
for gathering knowledge from surroundings and sharing them with rules to do more precise analyses. There
are a bunch of built-in ones, like [`Ancestry`](refactor.context.Ancestry) which can help you to backtrack
a node to its parents. But what what need today is [`Scope`](refactor.context.Scope). It allows you to learn
under which semantic scope a node is located, and where it can reach from there.

Let's see how scope works in a practical way by initially laying out our contract for an `ast.Name`:

```py
    def match(self, node: ast.AST) -> refactor.BaseAction:
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)
```

Once we have pass the initial checks, we'll ask [`Scope`](refactor.context.Scope) to resolve our semantical
scope. All initialized context providers can be accessed by their name (actually their name's snake case
version, so `Scope` is `scope` and `SomethingProvider` is `something_provider`):

```py
        scope = self.context.scope.resolve()
```

The `scope` here is a [`ScopeInfo`](refactor.context.ScopeInfo) and it looks like this:

```py
>>> ScopeInfo(node=<ast.Module object at 0x7fc8dcd0bfd0>, scope_type=<ScopeType.GLOBAL: 1>)
```

It holds the encapsulating `node` (it might be a function, a class, etc.) and the `scope_type`. But what
we are currently interesting in is a method called [`get_definitions`](refactor.context.ScopeInfo.get_definitions). It
checks all the accessible scopes (like if you are in a function, it also goes to the global scope to check for it) and
scans the identifier name you passed. It might return multiple nodes if there are multiple definitions of the same thing
(like two assignments to the same name under an if/else statement) so we have to be delicate and only process the cases
where we know there is a single source.

```py
        definitions = scope.get_definitions(node.id) or []
        assert len(definitions) == 1
```

And then the rest is just ensuring that the definition we have is from an assignment (e.g., if we look
for `PI` we'll get `PI = 3.14`), and that the assignment's value is a constant.

```py
        definition = definitions[0]
        assert isinstance(definition, ast.Assign)
        assert isinstance(defined_value := definition.value, ast.Constant)
```

If this is the case, we'll go ahead and replace it with it's actual value.

```py
        return refactor.Replace(node, defined_value)
```

Let's only run this rule (by passing `run(rules=[PropagateMyConstants])`) for the first time:

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

It works pretty well, but not as well as the combined version:

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

As you can see, now even `WEIRD_MATH_CONSTANT` inside `make_computation` is replaced. This is done because:

- `PI` values in `TAU` is propagated, and then `TAU` is constant folded.
- Since both `TAU` and `PI` are now just constants, they are both propagated to `WEIRD_MATH_CONSTANT` which is now open for a folding by itself
- And when it is folded, its value is propagated inside `make_computation`

```{tip}
Pretty crazy, huh? This is just the beginning of auto transformation tools can do. Follow our documentation to learn more
```

```{note}
The full code for this example is available at our [GitHub repo](https://github.com/isidentical/refactor/tree/master/examples/tutorial/constant-folding)
```
