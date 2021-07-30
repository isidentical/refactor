```{toctree}
:hidden:
:maxdepth: 1

going-further
actions
api
changelog
```

# Refactor

Simple, hassle-free, dependency-free, AST based source code refactoring
toolkit.

## Why? How?

`refactor` is an end-to-end refactoring framework that is built on top
of the 'simple but effective refactorings' assumption. It is much easier
to write a simple script with it rather than trying to figure out what
sort of a regex you need in order to replace a pattern (if it is even
matchable with regexes).

Every refactoring rule offers a single entrypoint, `match()`, where they
accept an `AST` node (from the `ast` module in the standard library) and
respond with either returning an action to refactor or nothing. If the
rule succeeds on the input, then the returned action will build a
replacement node and `refactor` will simply replace the code segment
that belong to the input with the new version.

Here is a complete script that will replace every `placeholder` access
with `42` (not the definitions) on the given list of files:

```py
import ast
from refactor import Rule, ReplacementAction, run

class Replace(Rule):
    
    def match(self, node):
        assert isinstance(node, ast.Name)
        assert node.id == 'placeholder'
        
        replacement = ast.Constant(42)
        return ReplacementAction(node, replacement)
        
if __name__ == "__main__":
    run(rules=[Replace])
```

If we run this on a file, `refactor` will print the diff by default;

```diff
--- test_file.py
+++ test_file.py

@@ -1,11 +1,11 @@

 def main():
-    print(placeholder * 3 + 2)
-    print(2 +               placeholder      + 3)
+    print(42 * 3 + 2)
+    print(2 +               42      + 3)
     # some commments
-    placeholder # maybe other comments
+    42 # maybe other comments
     if something:
         other_thing
-    print(placeholder)
+    print(42)
 
 if __name__ == "__main__":
     main()
```

> As stated above, refactor's scope is usually small stuff, so if you
> want to do full program transformations we highly advise you to look
> at CST-based solutions like
> [parso](https://github.com/davidhalter/parso),
> [LibCST](https://github.com/Instagram/LibCST) and
> [Fixit](https://github.com/Instagram/Fixit)
