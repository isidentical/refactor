# Refactor

Simple, dependency-free, AST based source code refactoring interface.

> :warning: **This project is still work-in-progress**: Be very careful with depending on the APIs!

## How

`refactor` is nothing more than a tiny wrapper around your AST processing code. Each refactor
operation is a rule (`refactor.Rule`) where they return either an action (`refactor.Action`) to
translate or None from their `match` method.

Here is an example rule that replaces all `placeholder`s with `42`. The `ReplacementAction` is
a subclass of `refactor.Action`, which takes the original node and the replacement node and
changes the segment belonging the initial node with the unparsed version of other.

```py
import ast
import refactor
from refactor import Rule, ReplacementAction

class ReplacePlaceholders(Rule):

    def match(self, node):
        assert isinstance(node, ast.Name)
        assert isinstance(node.ctx, ast.Load)
        assert node.id == "placeholder"

        replacement = ast.Constant(42)
        return ReplacementAction(node, replacement)

if __name__ == "__main__":
    refactor.run(rules=[ReplacePlaceholders])
```

The `refactor` package comes bundled with a simple entry point generator, which can
be used through simply running `refactor.run()` with the rules you want to apply. It will
create a CLI application which takes files and outputs diffs. Here is an example file that
we might test the following script;

```py
def test():
    print(placeholder)
    print( # complicated
        placeholder
    )
    if placeholder is placeholder or placeholder > 32:
        print(3  + placeholder)
```

And if we run the `refactor` script;

```diff
--- examples/test/placeholder.py

+++ examples/test/placeholder.py

@@ -1,8 +1,7 @@

 def test():
-    print(placeholder)
+    print(42)
     print( # complicated
-        placeholder
+        42
     )
-    if placeholder is placeholder or placeholder > 32:
-        print(3  + placeholder)
-
+    if 42 is 42 or 42 > 32:
+        print(3  + 42)
```
