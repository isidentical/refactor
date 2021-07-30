# Going Further

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

def foo(d = 5):
    b = 4
    c = a + b
    return c + (b * 3) + d

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

def foo(d = 5):
    b = 4
    c = a + 4
    return c + (4 * 3) + d

class T:
    b = 2
    print(a + 2 + c)
    
    def foo():
        c = 3
        print(a + b + 3 + d)
```

Though for making such a change, we need to know where the definition is for a
particular `ast.Name` node. This is where `Representative`s comes to the play.
Let's create an observer which would offer a method called `collect()` where
you'd pass the scope you are in, and it would return a dictionary of all definitions.

```python
class Assignments(refactor.Representative):
    
    def collect(self, scope: ScopeInfo) -> DefaultDict[str, List[ast.Assign]]:
        ...
```

One thing that we need for a case like this is, we want to be able to infer
the scope of particular `AST` nodes, so we will declare a tuple of context providers
that we need in the class definition:

```python
from refactor.context import Scope

class Assignments(refactor.Representative):
    context_providers = (Scope,)
    
    def collect(self, scope: ScopeInfo) -> DefaultDict[str, List[ast.Assign]]:
        ...
```

If any rule uses our `Assignments` representative, the context object will also
search for any of the representatives that `Assignments` need in the `context_providers`
and prepare them. Next up, let's search for all definitions within the given scope;

```python
    def collect(self, scope: ScopeInfo) -> DefaultDict[str, List[ast.Assign]]:
        assignments = defaultdict(list)
        for node in ast.walk(scope.node):
            # Check whether this is a simple assignment to a name
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(target := node.targets[0], ast.Name)
            ):
```

This would find all assignments done by `a = b`, which is the simplest form
that we are accepting right now. Obviously there are many ways that a name
can be bound to a value in Python (e.g imports, with targets, for targets etc.)
but for the sake of simplicity. One thing to consider here is that, when we are
walking, it will also yield nodes from child contexts (e.g if you have another
function defined within this one, the assignments from that function will also
be yielded), for fixing this issue we can simply resolve the scope of this
assignment and check whether we can reach it or not;

```python
    def collect(self, scope: ScopeInfo) -> DefaultDict[str, List[ast.Assign]]:
        assignments = defaultdict(list)
        for node in ast.walk(scope.node):
            # Check whether this is a simple assignment to a name
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(target := node.targets[0], ast.Name)
            ):
                # Check whether we can reach this assignment or not.
                # For example there might be child functions where the
                # definition is unreachable for us.
                assignment_scope = self.context['scope'].resolve(node)
                if scope.can_reach(assignment_scope):
                    assignments[target.id].append(node)
        
        return assignments

```

If all goes fine, we'd return the dictionary we prepared. The next step is
writing the actual rule, which is going to be very simple;

```python
class PropagationRule(refactor.Rule):
    
    context_providers = (Assignments, Scope)
    
    def match(self, node: ast.AST) -> refactor.Action:
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)
            
```

We'll match against a simple name on a load context, we don't want to replace assignment
targets with the constant literals :) Now it's time to resolve the name we have and check
whether it is assigned only once, and whether the value it is bound to is a constant

```python
        # The name should be defined in the current scope
        # and there shouldn't be any overrides
        assert len(assignments) == 1

        # The value should be a constant, so that we can safely propagate
        [assignment] = assignments
        assert isinstance(value := assignment.value, ast.Constant)
```

And if that is the case, we can simply return a `ReplacementAction` which would replace
the `ast.Name` node with the `ast.Constant` node;

```python
        return refactor.ReplacementAction(node, value)
```

Let's give it a try:

```diff
 $ python examples/propagate.py test.py                  
--- test.py
+++ test.py

@@ -2,13 +2,13 @@

 def foo(d = 5):
     b = 4
-    c = a + b
-    return c + (b * 3) + d
+    c = a + 4
+    return c + (4 * 3) + d
 
 class T:
     b = 2
-    print(a + b + c)
+    print(a + 2 + c)
     
     def foo():
         c = 3
-        print(a + b + c + d)
+        print(a + b + 3 + d)
```
