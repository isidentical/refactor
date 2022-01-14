# Representatives

For more complicated refactoring rules, sometimes you need to
collect more information about the surrounding code. Rules have
access to this information via their `context` attribute. It will
return an instance of the `refactor.context.Context` which basically
serves for these 3 needs:

- Getting the source code of the current module
- Getting the AST of the code module
- Accessing to enabled representatives

Each representative is an observer that interacts with the whole
tree rather than the particular node. There are also some builtin
ones that serve for common utilities, including `Ancestry` (for
backtracking a single node and it's parents) and `Scope` (for basic
scope management).

## Example: Constant propagation

We can write a simple rule which would replace all variables with
their values if they are binded to a literal.

For example;

```python
a = 1


def main(d=5):
    b = 4
    c = a + b
    e = 3
    e = 4
    return c + (b * 3) + d + e


class T:
    b = 2
    print(a + b + c)

    def foo():
        c = 3
        print(a + b + c + d)
```

The code above can be transformed to this;

```python
a = 1


def main(d=5):
    b = 4
    c = a + 4
    e = 3
    e = 4
    return c + (4 * 3) + d + e


class T:
    b = 2
    print(a + 2 + c)

    def foo():
        c = 3
        print(a + b + 3 + d)
```

There are a few points we need to make sure though. First, we need a way of collecting variables
that we only have access from their usage site (e.g we can't reach the `c` in `T.foo` from `main`). Second
we need to make sure that the variables we are using don't get changed during the function's life time (e.g
`e` is first set to `3` but then it becomes `4`).

Luckily basic scope management operations comes as one of the builtin representatives (`refactor.context.Scope`).
We could simply plug it in by adding it to a tuple called `context_providers` on the rules we need them;

```py
import ast

import refactor
from refactor.context import Scope

class PropagateConstants(refactor.Rule):
    
    context_providers = (Scope,)
```

Let's write the matcher for this. We are going to look for name loads (so that we won't replace the left hand side
for assignments);

```py
    def match(self, node):
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)
```

Then we will get the current `scope` (`refactor.context.ScopeInfo`) from the `Scope` provider. We can access it through
`context`:

```py
        current_scope = self.context['scope'].resolve(node)
```

The convention for representatives is that, unless they define a custom `name` descriptor, it is the snake case format
of their type name. For example `Scope` is `'scope'`, `ImportFinder` is `'import_finder'` and so on. The `Scope` representative
offers a method called `resolve()` which basically takes the node and returns `ScopeInfo`. With looking that `ScopeInfo`, we can
check whether the name we are looking for defined in that scope

```py
        assert current_scope.defines(node.id)
```

And if it is, we can get the definition

```py
        definitions = current_scope.definitions[node.id]
```

Obviously a name can be defined muliplte times, so `definitions` is always a list. We need to ensure it a list of a single
assignment

```py
        assert len(definitions) == 1
        assert isinstance(
            definition := definitions[0],
            ast.Assign
        )
```

And finally we need to check whether the value for this assignment is a constant, and if it is return a `ReplacementAction`;

```py
        assert isinstance(value := definition.value, ast.Constant)

        return refactor.ReplacementAction(node, value)
```

### Appendix A: Full Script

```py
import ast

import refactor
from refactor.context import Scope

class PropagateConstants(refactor.Rule):

    context_providers = (Scope,)

    def match(self, node):
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)

        current_scope = self.context['scope'].resolve(node)
        assert current_scope.defines(node.id)

        definitions = current_scope.definitions[node.id]

        assert len(definitions) == 1
        assert isinstance(
            definition := definitions[0],
            ast.Assign
        )
        assert isinstance(value := definition.value, ast.Constant)

        return refactor.ReplacementAction(node, value)

if __name__ == "__main__":
    refactor.run(rules=[PropagateConstants])
```
