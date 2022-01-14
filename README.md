# Refactor

[![PyPI version](https://badge.fury.io/py/refactor.svg)](https://badge.fury.io/py/refactor)

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

### CST vs AST

It is a common misconception that AST *should not* be used for source code refactorings since
it doesn't preserve any of the stylings about the code that is visible to humans. Even though
this statement is partially true, it is wrong on the point of "we can't/shouldn't do any transformations
through AST". As explained above, we aim to tackle the smaller and simpler problems (e.g refactoring
simple expressions statements) and while doing that we preserve all details about the surrounding code. And
even for the stuff in the same line, we preserve as much as we can (e.g refactoring a simple name between 2 different
operations won't change any style). It is obviously possible to abuse this and do full source refactors, in that case,
you will lose most of the information, which even though is not preferred, might apply to some use cases (e.g
feeding the output directly to the interpreter).

We have some great CST implementations ([parso](https://github.com/davidhalter/parso),
[LibCST](https://github.com/Instagram/LibCST)) and even though they are pretty useful for
doing major transformations, they can't be expected to keep up with the latest syntax updates
on the upstream python. It is also an extra layer of indirection in some cases, considering that
it is a general practice to do analysis on the AST and refactoring on the CST and for most of the
cases these would be interchangeable through `refactor`. In any scenario, I'd highly recommend you
to check out these libraries (as well as some tools like [Fixit](https://github.com/Instagram/Fixit))
if you are interested in doing a considerable amount of source code processing.
