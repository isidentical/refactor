"""An example refactoring rule to demonstrate `refactor` module.

Example effect:
```
 $ python examples/type_literals.py ~/cpython/cpython/Tools/scripts
--- /home/isidentical/cpython/cpython/Tools/scripts/mailerdaemon.py
+++ /home/isidentical/cpython/cpython/Tools/scripts/mailerdaemon.py
@@ -70,7 +70,7 @@
 # compile the re's in the list and store them in-place.
 for i in range(len(emparse_list_list)):
     x = emparse_list_list[i]
-    if type(x) is type(''):
+    if isinstance(x, str):
         x = re.compile(x, re.MULTILINE)
     else:
         xl = []
@@ -134,7 +134,7 @@
         if reason[:15] == 'returned mail: ':
             reason = reason[15:]
         for regexp in emparse_list_reason:
-            if type(regexp) is type(''):
+            if isinstance(regexp, str):
                 for i in range(len(emails)-1,-1,-1):
                     email = emails[i]
                     exp = re.compile(re.escape(email).join(regexp.split('<>')), re.MULTILINE)
```
"""

import ast
from dataclasses import dataclass

import refactor
from refactor import common


@dataclass
class Action(refactor.Action):
    arg: ast.expr
    base_type_name: str
    negate: bool = False

    def build(self) -> ast.expr:
        node = ast.Call(
            ast.Name("isinstance", ast.Load()),
            args=[self.arg, ast.Name(self.base_type_name, ast.Load())],
            keywords=[],
        )
        return common.apply_condition(self.negate, node)


class TypeLiteralRule(refactor.Rule):
    """
    Convert `type(something) is type('')` comparisons
    into a simple `isinstance(something, str)` call.
    """

    def fetch_arg(self, node: ast.expr) -> ast.expr:
        """Get the first argument from a `type()` call"""

        assert isinstance(node, ast.Call)
        assert isinstance(node.func, ast.Name)
        assert node.func.id == "type"
        assert len(node.args) == 1
        return node.args[0]

    def match(self, node: ast.AST) -> Action:
        # Ensure is a ast.Compare node
        assert isinstance(node, ast.Compare)

        # Ensure this is not a chained comparison (a is b == c)
        assert len(node.comparators) == len(node.ops) == 1

        # Ensure the operator is either `is` or `is not`
        assert isinstance(operator := node.ops[0], (ast.Is, ast.IsNot))

        arg = self.fetch_arg(node.left)
        base_type_node = self.fetch_arg(node.comparators[0])

        # Ensure the type() call on the right side uses a literal
        # as the argument.
        assert isinstance(base_type_node, ast.Constant)
        base_type_name = type(base_type_node.value).__name__

        return Action(
            node, arg, base_type_name, negate=common.is_truthy(operator)
        )


if __name__ == "__main__":
    exit(refactor.run(rules=[TypeLiteralRule]))
