# Refactor

[![PyPI version](https://badge.fury.io/py/refactor.svg)](https://badge.fury.io/py/refactor)
[![Documentation](https://img.shields.io/badge/%3D%3E-Documentation-brightgreen)](https://refactor.readthedocs.io)

Simple, hassle-free, dependency-free, AST based fragmental source code refactoring
and transformation toolkit.

## Why?

Our framework is primarily built on the principle of "simple but effective
transformations". We focus on refactorings that target a small span of
source code, and work our way out from it. What this enables for us is
being able to operate directly on a single format for both analyses and
transformations. This is what we shine at compared to other similar tools.

## How?

Let's not get into too much details, but just to give a sneak peek we
can try to write a rule that would replace the identifier `placeholder`
with `42`.

```py
import ast
from refactor import Rule, Replace, run

# Each refactor transformer inherits from "refactor.Rule"
class FillPlaceholders(Rule):

    # And each rule implements a "match()" method, which would
    # receive every node in the tree in a breadth-first order.
    def match(self, node: ast.AST) -> Replace:
        # This is where things get interesting. Instead of just writing
        # filters with if statements, you can use the following assert
        # based approach (a contract of transformation).

        # For this case, our contract is going to be: if the given node
        # is an identifier with the name of "placeholder", it will be
        # replaced with literal "42".
        assert isinstance(node, ast.Name)
        assert node.id == "placeholder"

        # And this is where we choose what action we are taking for the
        # given node (which we have verified with our contract). There
        # are multiple transformation actions, but in this case what we
        # need is something that replaces a node with another one.
        replacement = ast.Constant(42)
        return Replace(node, replacement)

if __name__ == "__main__":
    # And finally in here, we just use the default CLI that comes
    # bundled with refactor. When provided with a bunch of rules,
    # it creates a simple interface that can process given files
    # show the diff for changes and even apply them.
    run(rules=[FillPlaceholders])
```

If we run the rule above on a file, we can see how it performs:

```diff
--- test_file.py
+++ test_file.py

@@ -1,11 +1,11 @@

def main():
-    print(placeholder * 3 + 2)
+    print(42 * 3 + 2)
-    print(2 +               placeholder      + 3)
+    print(2 +               42      + 3)
     # some comments
-    placeholder # maybe other comments
+    42 # maybe other comments
     if something:
         other_thing
-    print(placeholder)
+    print(42)

if __name__ == "__main__":
     main()
```

For learning more, check our [documentation](https://refactor.readthedocs.io/en/latest/) out!
